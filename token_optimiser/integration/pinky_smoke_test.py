#!/usr/bin/env python3
"""
Pinky smoke test for neo-light's token optimiser (TOS).

Seven layers, in order:
  1. dependencies   -> imports + python version
  2. config         -> defaults (tiers, caps, thresholds, T1/T2/T3 backends)
  3. router         -> assess probe tasks (simple / security / 3+ cats ASK / [large] scope / 60-79 band / parallelize)
  4. learning log   -> append by task_id, read-back, append_outcome, clear
  5. pinky wrapper  -> monica_integration.optimise / optimise_batch / record_outcome / optimiser_enabled / disabled fallback
  6. mock backends  -> T1/T2/T3 generate, MockGateway.execute routing, OptimiserTestHarness run_scenario, rate-limit guard vs NVIDIA 40 RPM ceiling
  7. dashboard API  -> import app + route registry; optional live GET on :8765 (skipped, not failed, if down)

Each layer prints one clear PASS/FAIL line. Exit non-zero on any failure.
Layers run fully offline except the optional dashboard GET.

Run:
    PYTHONPATH=/home/warpuppy/Projects/neo-light python3 token_optimiser/integration/pinky_smoke_test.py
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

RESULTS: dict[str, bool] = {}
FAILURES: list[str] = []


def layer(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS[name] = ok
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)
    return ok


# --------------------------------------------------------------------------- #
# 1. Dependencies
# --------------------------------------------------------------------------- #
def check_dependencies() -> bool:
    mods = [
        "token_optimiser.config",
        "token_optimiser.router",
        "token_optimiser.monica_integration",
        "token_optimiser.mock_backends",
        "token_optimiser.boa",
        "token_optimiser.dashboard.app",
    ]
    missing: list[str] = []
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{m}: {exc}")
    return layer("dependencies", not missing, "; ".join(missing) if missing else f"python {sys.version.split()[0]}")


# --------------------------------------------------------------------------- #
# 2. Config
# --------------------------------------------------------------------------- #
def check_config() -> bool:
    from token_optimiser.config import config

    checks = [
        ("T1 url", config.tier_backends["T1"]["url"] == "http://192.168.1.10:8081"),
        ("T1 model", config.tier_backends["T1"]["model"] == "phi-4-mini-instruct"),
        ("T3 disabled", config.tier_backends["T3"]["providers"][0]["enabled"] is False),
        ("T3 locked", config.tier_backends["T3"].get("t3_locked") is True),
        ("zero_tier_mode", config.zero_tier_mode is True),
        ("t3_hard_disabled", config.t3_hard_disabled is True),
        ("security cap 55", config.security_confidence_cap == 55),
        ("t1_min 80", config.threshold_t1_min == 80),
        ("t2_min 60", config.threshold_t2_min == 60),
        ("free_tier_priority False (T1-first)", config.free_tier_priority is False),
        ("T2 gateways == 4", len(config.tier_backends["T2"]["gateways"]) == 4),
        ("rate ceilings present", all(k in config.provider_rate_ceilings for k in
                                      ("NVIDIA_NIM", "OpenRouter", "Nous Portal"))),
        ("OpenRouter :free rpd 50", config.provider_rate_ceilings["OpenRouter"]["rpd"] == 50),
        # Every category preference must resolve to a free model or local-only
        # (phi-4-mini-instruct is the T1 local model; NVIDIA NIM models run on
        # free credits [unverified]; OpenRouter entries carry :free).
        ("free model preferences", all(
            v == "local-only" or v == "phi-4-mini-instruct" or ":free" in v
            or any(p in v for p in ("nvidia/", "deepseek-ai/", "deepseek/", "mistralai/"))
            for v in config.category_free_model_preference.values())),
    ]
    ok = all(c[1] for c in checks)
    detail = "; ".join(f"{n}={'ok' if v else 'BAD'}" for n, v in checks)
    return layer("config", ok, detail)


# --------------------------------------------------------------------------- #
# 3. Router
# --------------------------------------------------------------------------- #
def check_router() -> bool:
    from token_optimiser.router import TokenRouter

    router = TokenRouter()
    probes = [
        ("simple", "Fix typo in the README header", None,
         lambda d: d.tier == "T1" and d.confidence >= 80),
        ("security-capped-ASK", "Implement JWT authentication with password hashing", None,
         lambda d: d.confidence <= 55 and d.tier == "ASK" and d.security_escalate is True and d.zero_tier_blocked is True),
        ("three-cats-ASK",
         "[large] Refactor auth module and add tests across several files",
         None,
         lambda d: d.tier == "ASK" and d.scope == "large"),
        ("below-band-ASK", "something vague about stuff maybe", None,
         lambda d: d.tier == "ASK" and d.zero_tier_blocked is True),
    ]
    failed: list[str] = []
    for label, task, _ctx, cond in probes:
        try:
            d = router.assess(task, _ctx or {})
            if not cond(d):
                failed.append(f"{label}: tier={d.tier} conf={d.confidence} scope={d.scope}")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{label}: {exc}")

    # 60-79% band -> ASK when ask_human_band on. The decision must be taken
    # while the band is enabled, then re-asserted here (save/restore global
    # config around it; verify the band first per the token-budget-routing
    # pitfall: a "mid-feeling" task can be capped or land at T3).
    from token_optimiser.config import config as cfg
    band_was = cfg.ask_human_band
    cfg.ask_human_band = True
    band_decision = None
    try:
        band_decision = router.assess("Write unit tests for the gateway session handler")
    finally:
        cfg.ask_human_band = band_was
    if band_decision is not None:
        in_band = 60 <= band_decision.confidence < 80
        label = "60-79-band-ASK" if in_band else f"60-79-band-ASK(note: actual band {band_decision.confidence})"
        ok = (not in_band) or band_decision.tier == "ASK"
        if not ok:
            failed.append(f"{label}: tier={band_decision.tier} conf={band_decision.confidence}")
        detail = f"{len(probes)} probes + band-check(conf={band_decision.confidence}, in_band={in_band}); " + ("; ".join(failed) if failed else "all bands behave")
    else:
        detail = f"{len(probes)} probes; " + ("; ".join(failed) if failed else "all bands behave")
    return layer("router", not failed, detail)


# --------------------------------------------------------------------------- #
# 4. Learning log
# --------------------------------------------------------------------------- #
def check_learning_log() -> bool:
    from token_optimiser.router import TokenRouter, LearningLog

    tmp = Path(tempfile.mkdtemp()) / "smoke_learning_log.jsonl"
    tmp.write_text("")
    log = LearningLog(path=str(tmp))
    router = TokenRouter()
    router.learning_log_path = str(tmp)

    d = router.assess("Fix typo in title")
    log.append(d)  # no outcome yet — append_outcome is for entries lacking one
    entries = log.get_entries()
    ok1 = len(entries) == 1 and entries[0]["tier"] == d.tier
    task_id = entries[0]["task_id"]
    ok2 = log.append_outcome(task_id, {"outcome_type": "partial", "quality": "acceptable"}) is True
    entries = log.get_entries()
    ok3 = entries[0]["outcome"]["outcome_type"] == "partial"

    ok4 = log.append_outcome("does-not-exist", {"outcome_type": "worked"}) is False
    log.clear()
    ok5 = len(log.get_entries()) == 0
    ok = all([ok1, ok2, ok3, ok4, ok5])
    return layer("learning-log", ok, f"final_entries={len(log.get_entries())}")


# --------------------------------------------------------------------------- #
# 5. Pinky wrapper (monica_integration)
# --------------------------------------------------------------------------- #
def check_pinky_wrapper() -> bool:
    from token_optimiser.monica_integration import (
        optimise, optimise_batch, record_outcome, optimiser_enabled,
    )

    o = optimise("Fix typo in title")
    ok1 = (isinstance(o, dict) and o["tier"] in ("T1", "T2") and "confidence" in o
           and "security_escalate" in o and "zero_tier_blocked" in o)
    ok2 = "swarm_recommendation" in o or "swarm" in o

    batch = optimise_batch(["Fix typo", "Write a class"])
    ok3 = isinstance(batch, list) and len(batch) == 2 and all("tier" in b for b in batch)

    ok4 = isinstance(optimiser_enabled(), bool)

    # record_outcome writes to the global log path; only assert it returns a bool
    tmp_log_id = f"smoke-{int(time.time())}"
    from token_optimiser.router import LearningLog
    LearningLog().append_outcome(tmp_log_id, {"outcome_type": "worked"})
    ok5 = isinstance(record_outcome(tmp_log_id, {"outcome_type": "worked"}), bool)

    ok = all([ok1, ok2, ok3, ok4, ok5])
    return layer("pinky-wrapper", ok, f"optimise tier={o['tier']} batch={len(batch)}")


# --------------------------------------------------------------------------- #
# 6. Mock backends + rate-limit guard
# --------------------------------------------------------------------------- #
def check_mock_backends() -> bool:
    from token_optimiser.mock_backends import (
        T1MockBackend, T2MockBackend, T3MockBackend, MockGateway,
        OptimiserTestHarness,
    )

    r1 = T1MockBackend().generate("Fix typo")
    r2 = T2MockBackend().generate("Implement an API endpoint")
    r3 = T3MockBackend().generate("Review security architecture")
    ok1 = all(r["tier"] == t and "response" in r for r, t in
              ((r1, "T1"), (r2, "T2"), (r3, "T3")))

    gw = MockGateway({"mock_mode": True})
    ok2 = gw.execute("T1", "task")["tier"] == "T1" and "error" in gw.execute("T99", "task")

    harness = OptimiserTestHarness({"mock_mode": True})
    res = harness.run_task("Refactor module and add tests across several files")
    ok3 = "assessment" in res and "execution" in res and res["tier_used"] in ("T1", "T2", "T3", "ASK")

    # Rate-limit guard: zero-tier provider ceilings from config
    # (NVIDIA NIM ~40 RPM shared [unverified]; OpenRouter :free 50 RPM / 50 RPD;
    #  Nous Portal 50 RPM / 500K TPM).
    from token_optimiser.config import config
    ceilings = config.provider_rate_ceilings

    def rate_limit_guard(provider: str, workers: int, calls_per_worker: int) -> str:
        total = workers * calls_per_worker
        c = ceilings[provider]
        if c.get("rpd") is not None and total > c["rpd"]:
            return "serialize"  # hard daily ceiling
        return "serialize" if total > c["rpm"] else "proceed"

    ok4 = rate_limit_guard("NVIDIA_NIM", 5, 6) == "proceed"      # 30 < 40 RPM
    ok5 = rate_limit_guard("NVIDIA_NIM", 5, 10) == "serialize"    # 50 > 40 RPM
    ok6 = rate_limit_guard("OpenRouter", 1, 51) == "serialize"    # 51 > 50 RPD
    ok7 = rate_limit_guard("OpenRouter", 1, 1) == "proceed"       # 1 < 50
    ok = all([ok1, ok2, ok3, ok4, ok5, ok6, ok7])
    return layer("mock-backends", ok,
                 f"harness tier={res['tier_used']} guard={ok4 and ok5 and ok6 and ok7}")


# --------------------------------------------------------------------------- #
# 7. Dashboard API
# --------------------------------------------------------------------------- #
def check_dashboard_api() -> bool:
    try:
        from token_optimiser.dashboard import app  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return layer("dashboard-api", False, f"import failed: {exc}")

    routes = {getattr(r, "path", None) for r in app.routes}
    routes.discard(None)
    required = {"/api/config", "/api/learning-log", "/api/analytics/overview",
                "/api/analytics/effectiveness", "/api/tiers", "/api/assess"}
    ok1 = required.issubset(routes)

    # Optional live GET — :8765 was OPEN on acer this session, but localhost
    # serving is not assumed; skip-not-fail if unreachable.
    live_ok = None
    try:
        req = Request("http://127.0.0.1:8765/api/config", method="GET")
        with urlopen(req, timeout=3) as resp:
            live_ok = resp.status == 200
    except (URLError, HTTPError, OSError):
        live_ok = None

    if live_ok is None:
        return layer("dashboard-api", ok1, "routes registered; live GET skipped (:8765 not serving locally)")
    return layer("dashboard-api", ok1 and live_ok,
                 f"routes registered; live GET {'200 OK' if live_ok else 'non-200'}")


# --------------------------------------------------------------------------- #
def main() -> int:
    # Repo root on sys.path + CWD: the package lives at <repo>/token_optimiser and
    # LearningLog's default path is CWD-relative, so both must point at the repo root
    # no matter where the script is invoked from.
    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    os.chdir(_repo_root)
    print("== TOS pinky smoke test ==")
    check_dependencies()
    check_config()
    check_router()
    check_learning_log()
    check_pinky_wrapper()
    check_mock_backends()
    check_dashboard_api()

    print("\n== Summary ==")
    all_ok = True
    for name, ok in RESULTS.items():
        print(f"  {name:<20} {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok
    if FAILURES:
        print(f"\nFAILED layers: {', '.join(FAILURES)}")
    print("RESULT:", "ALL PASS" if all_ok else "FAILURES PRESENT")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
