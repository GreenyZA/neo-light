# TOS Zero-Tier Redesign — Exclusive $0 Free Tier (neo-light)

**Status:** design + code enforcement (this document + patches to `token_optimiser/config.py`, `router.py`, `boa.py`, `integration/pinky_smoke_test.py`).
**Supersedes:** the paid-tier sections of `docs/TOKEN-OPTIMISER-SWARM-DESIGN.md` (T1→T2→T3 with NVIDIA NIM primary / OpenRouter $10 top-up / Nous fallback). That mixed design is retired; this is the $0-only replacement.

## 0. Binding constraints (exclusive $0)

| # | Constraint | Source |
|---|-----------|--------|
| C1 | $0 total spend. No paid tiers, no top-ups, ever. | User |
| C2 | T3 disabled — hard lock, no enable toggle in dashboard, no paid provider entries usable. | User |
| C3 | Router order: T1 local → T2 free cloud only → T3 (disabled, never reached). | User |
| C4 | Confidence bands: T1 ≥ 80, T2 ≥ 60; ASK on 3+ matched categories or 60–79% band. | User |
| C5 | Security/safety cap 55%. If a security call cannot clear 55%, escalate to James with a flag — never silently downgrade. | User / AGENTS.md |
| C6 | Sub-60% with T3 disabled → ASK ("no $0 tier cleared"), never silent paid escalation. | Derived from C2/C4 |
| C7 | T1: llama-server `http://192.168.1.10:8081`, `phi-4-mini-instruct` Q4_K, n_ctx 131072 (wire-verified this session) + `ollama-7b` [unverified]. | Env |
| C8 | T2 free cloud only: NVIDIA NIM (~40 RPM shared [unverified]), OpenRouter `:free` (50 RPM / 50 RPD, no top-up), Nous Portal (50 RPM burst / 500K TPM, OAuth ~1h [unverified]). | User |
| C9 | Rate-limit-aware fan-out: batch independent work in ONE `delegate_task` call; serialize under load; no silent re-route on 429. | User |
| C10 | BOA + ITIL governance gate before any swarm dispatch; Top-Level Approver mandatory for 3+ workers. | User |
| C11 | Dashboard knobs $0-only; every knob its own config field with docstring, instant effect. | User |
| C12 | Unprobed claims marked `[unverified]`. | User |

Never route: `kimi-k2.6`, `nemotron-3-ultra-550b-a55b` on OpenRouter without `:free` (paid), SuperGrok/grok-2, "Ultra" models (AGENTS.md). T3 credentials (`GROK_API_KEY`) may exist in `~/.hermes/.env` but must never be consumed by the router.

---

## 1. Tier routing design ($0-only)

### 1.1 Tier backends

| Tier | Backend | URL / model | Status | Cost | Best for |
|---|---|---|---|---|---|
| T1 | Local llama-server (Vulkan/RX 480) | `http://192.168.1.10:8081`, `phi-4-mini-instruct` alias, Q4_K_M, 3.84B, **n_ctx 131072** (wire-verified), fallback `None` | enabled | $0 local, private, offline | Privacy/offline force-T1; simple transforms ≥80 conf |
| T1b | Local secondary (Lenovo CPU 7B) | dead — no LAN host serves `:8082` | **disabled** | $0 | Re-enable only after live `/v1/models` 200 [unverified] |
| T2 | Free cloud gateways | NVIDIA NIM `integrate.api.nvidia.com/v1`, OpenRouter `openrouter.ai/api/v1` (`:free` models only, 50 RPM / 50 RPD), Nous Portal `inference-api.nousresearch.com/v1` (OAuth ~1h) | enabled | $0 free tiers | Default cloud tier, 60–79 band |
| T3 | Paid (Grok/SuperGrok) | defined, `enabled: False`, **hard-locked** | disabled, locked | paid | Never. Change/security final judgment would go here in a paid setup — in zero-tier mode the gate ASKs + escalates instead. |

### 1.2 Confidence bands & ASK triggers ($0-only)

| Band | Confidence | Action |
|---|---|---|
| ≥ 80 | T1 eligible | Route to T1 local (router order T1-first). Privacy/offline keywords short-circuit here regardless of score. |
| 60–79 | T2 free cloud | Route to T2 — **OR ASK human** if `ask_human_band=True` (band wins over auto-route when both triggers active). |
| < 60 | ASK | T3 disabled → no $0 tier cleared → ASK with reason; security tasks here → escalate flag to James (C5). |

**ASK triggers:**
1. **3+ matched categories** (`ambiguous_task_asks_human=True`): no single tier is clearly right → ASK, rationale states why (e.g. "ambiguous: 3 categories matched").
2. **60–79% confidence band** (`ask_human_band`, `hybrid_band_enabled`): mid-confidence → ask rather than guess.
3. **Below T2 minimum (<60)** with T3 disabled → ASK: "below T2 minimum; T3 disabled (zero-tier) — no $0 tier cleared."
4. **Security cap 55%** (`security_confidence_cap=55`, `category_confidence_caps["security"]=55`): security matches max out at 55 → always <60 → ASK + escalate flag. Never silently route security to T2 or T3.

### 1.3 Scope-prefix handling

Inline hints parsed by `config.scope_prefix_pattern` (`\[(?:scope|size|scope_size)?[:\\s]*(\w+)\]`), mapped via `scope_prefix_values`:

- `[small]`/`[s]`/`[sm]` → small (scope modifier +5 on most categories)
- `[medium]`/`[m]`/`[med]` → medium (0 modifier)
- `[large]`/`[l]`/`[lg]` → large (−5 to −15 depending on category)

Fallback: `scope_word_thresholds = {small: 30, medium: 100}` words, or `estimated_lines` in context (<50 small, <200 medium, else large). Scope modifiers live per category in `CATEGORY_RULES[].scope_modifiers`.

Privacy/offline keywords (`privacy_offline_keywords`) + `privacy_force_t1=True` always short-circuit to T1/T1b regardless of band — data never leaves the machine. T1b is dead (no `:8082` host) → privacy + "larger model" keywords currently strand on T1; re-enable T1b only after a live probe.

### 1.4 `_select_tier` decision order (enforced in `router.py`)

1. **ITIL/BOA override:** ITIL `change` → ASK ("T3 disabled — change needs CHG + paid tier; zero-tier blocks"). `security` category match → ASK + `security_escalate: true` flag (escalate to James).
2. **Ambiguous:** ≥3 unique categories → ASK.
3. **Ask band:** 60–79% + `ask_human_band` → ASK.
4. **Privacy short-circuit:** `privacy_force_t1` + privacy/offline keyword → T1 (T1b if `t1b_keywords` match and T1b enabled — currently disabled).
5. **Architecture minimum:** architecture as top match → T2 minimum.
6. **Standard bands:** ≥80 → T1; 60–79 → T2; <60 → ASK ("below T2 minimum; T3 disabled — no $0 tier cleared").
7. `free_tier_priority` forced `False` in zero-tier mode — T1-first per router order, no T2-stealing of ≥80 tasks.

---

## 2. Swarm fan-out rules (zero-budget ceilings)

### 2.1 When to swarm

`parallelize_score` (0–1) = file-path hits ×0.5 + parallel-keyword hits ×0.35 + word-count ×0.15. `swarm_recommendation`:
- ≤ 8 → **solo**; 9–12 → **pair**; 13–18 → **swarm** (3–5 workers + reviewers); 19–25 → **mega** (5–10 + Top-Level Approver).
- Non-trivial (>8 score, ITIL ops, ambiguous ≥3 cats, confidence <60, medium/large scope, or auto-swarm triggers: refactor/integration/packaging/docs) → auto-swarm.
- Hard thresholds from `validate_swarm_plan`: >3 files, >2 modules, >5 sequential calls → swarm governed by BOA gate.
- Top-Level Approver mandatory when ≥3 workers.

### 2.2 Rate-limit ceilings ($0 T2 providers; all [unverified] until live-probed)

| Provider | RPM | Daily cap | Token limit | Cost basis | Role |
|---|---|---|---|---|---|
| NVIDIA NIM | ~40 (shared) | none (credit pool) | model-dependent | free credits [unverified] | Primary swarm engine; orchestrator + workers |
| OpenRouter `:free` | 50 | 50 RPD (no top-up) | none | $0 | Escalation/complex reasoning only — 50 RPD = ~2 minutes of full-speed swarming |
| Nous Portal | 50 (burst) | none | 500K TPM | $0 | Burst simple workers; OAuth ~1h expiry [unverified] |

**Pre-dispatch math (mandatory):** `total_requests = N workers × M calls each`. Compare to the selected provider's ceiling; `time_to_minutes = total_requests / RPM`. OpenRouter `:free`: a 5-worker swarm with 2 calls each = 10 requests = 20% of the entire day. If `total_requests > provider_rpm` → **serialize** (one subagent at a time), do not launch the burst.

### 2.3 Fan-out discipline (non-negotiable)

1. **Batch all independent sub-tasks into ONE `delegate_task(tasks=[...])` call** — never fan out sequential per-task calls that each burn RPM.
2. **Serialize under load:** once bursts are likely, run queued batches one subagent at a time; one completed serial round-trip beats several 429ed children.
3. **No silent re-route on 429:** a 429 says nothing about TOS tier health. Stop fan-out, report the failed batch, wait `retry-after`, slice blocked work sequentially, ask the user which reroute play (serialize / switch model-alias / TOS free tiers / local).
4. **Free tier + swarm_size > 2 → warn** (cost-aware sizing); downgrade to pair/solo when the free model can't absorb the burst.
5. Workers run on T2 free cloud unless privacy forces T1. T3 never (disabled). Record provider `retry-after`/`date` in the daily report; resume only after recovery.

---

## 3. Model assignment table (free models only)

| Role | Model | Tier → provider | Context | Cost basis | Assignment rule |
|---|---|---|---|---|---|
| Orchestrator (default) | `phi-4-mini-instruct` | T1 → llama-server `:8081` | 131072 [wire-verified] | $0 local | Privacy/offline force-T1 tasks; router order T1-first |
| Orchestrator (cloud default) | `nvidia/nemotron-3-super-120b-a12b` | T2 → NVIDIA NIM | 262K | NIM free credits [unverified] | Primary orchestrator; swarm score < 15 |
| Orchestrator (escalation) | `nvidia/nemotron-3-ultra-550b-a55b` | T2 → NVIDIA NIM | 1M | NIM free credits [unverified] | Swarm score ≥ 15; complex multi-phase, 10+ workers |
| | `nvidia/nemotron-3-ultra-550b-a55b:free` | T2 → OpenRouter `:free` | 1M | $0 | OR fallback for escalation; 50 RPD ceiling |
| High-frequency dispatch | `nvidia/nemotron-3.5-lightning-30b-a3b` | T2 → NVIDIA NIM | 1M | NIM credits [unverified] | Fast dispatch of many simple workers |
| Worker: code | `mistralai/codestral-22b-instruct-v0.1` | T2 → NVIDIA NIM | 128K | NIM credits [unverified] | Code generation |
| Worker: simple/reasoning | `nvidia/nemotron-nano-3-30b-a3b` | T2 → NVIDIA NIM | 128K | ~0.05 cred/req [unverified] | Text-only — **no tool calling** (verified 404 on `tool_calls`) |
| Worker: reasoning | `deepseek-ai/deepseek-v4-flash` | T2 → NVIDIA NIM | 128K | NIM credits [unverified] | Research, analysis |
| Worker: burst simple | `step-5-preview:free`, `ling-3.1-flash`, `stealth/missingno` | T2 → Nous Portal | 1M / 262K / 262K | $0 | Burst workers; OAuth ~1h [unverified]; 50 RPM / 500K TPM |
| Worker: simple local | `phi-4-mini-instruct` | T1 → `:8081` | 131072 | $0 | Force-T1 privacy tasks |

**Never assign:** `kimi-k2.6` (AGENTS.md), `nemotron-3-ultra-550b-a55b` on OpenRouter without `:free` (paid), SuperGrok/grok-2 (T3 disabled), Ultra models, any model without verified free status. Free model rosters change monthly — rescan `/v1/models` before hardcoding a model ID [unverified].

**Orchestrator vs worker split:** orchestrator = nemotron-3-super-120b (NIM) or phi-4-mini (T1); workers = nano/codestral/deepseek-v4-flash (NIM) or Nous free models for burst; escalation to ultra only when swarm score ≥ 15.

---

## 4. Governance gate checklist (BOA + ITIL) — before any swarm dispatch

Run in order; `decide_governance()` output (`tier`, `swarm_size`, `itil`, `rationale`, `seats_used`) is authoritative — adopt verbatim, never re-score on top.

- [ ] **ITIL classification first** (`classify_itil()`): incident / problem / change / request / event / unknown. `change` → CHG number required before proceeding; in zero-tier mode change → ASK (T3 blocked).
- [ ] **TOS routing:** `optimise()` tier + confidence + `parallelize` adopted as binding; `zero_tier_mode` enforced (T3 unreachable).
- [ ] **Governance-gate Approve:** BOA six seats answer in parallel — Architect, Engineer, Researcher, Reviewer, Budget (Token Optimiser), Executive (Chair) — then a governance statement (what was computed; never fabricated seat advice).
- [ ] **Independence:** workers write disjoint files/values; explicit do-not-touch lists naming sibling-owned paths; no shared-value collisions.
- [ ] **Reviewers:** every worker has a designated reviewer; reviewer inspects actual tool output/diff, not worker narrative (worker self-report is not evidence).
- [ ] **Top-Level Approver:** mandatory sign-off when ≥3 workers.
- [ ] **Security cap:** security tasks ≤55% confidence; if 55% can't be cleared → `security_escalate` flag, escalate to James — never silently downgrade to T2/T3.
- [ ] **Reentry guard:** `boa._BOA_REENTRY` prevents router↔boa infinite recursion (safe T2 lightweight fallback).
- [ ] **Logging:** decision + full session to `work/boa/governance/` (JSONL) and session log; never dispatch before the gate is logged.

Anti-patterns: swarming trivial work; overspawn; underspawn; splitting dependent tasks; skipping the reviewer; fixed swarm size; swarming free-tier models without rate-limit consideration; tight retry loops after 429; skipping the BOA gate; self-approving.

---

## 5. Calibration loop (learning log → per-category offsets)

1. **Record:** every `assess()` decision appended to `token_optimiser/learning_log.jsonl` with `task_id`, `tier`, `confidence`, `matched_categories`, `scope`, `context`, `timestamp`, `zero_tier_blocked`, `security_escalate`.
2. **Outcome feedback:** `record_outcome(task_id, {"outcome_type": worked\|partial\|failed\|needed_escalation, "tier_used", "token_used", "quality": good\|acceptable\|poor, "notes"})` appends the outcome to the entry by `task_id` (both `{"outcome": {...}}` and `{"outcome_type": ...}` shapes accepted).
3. **Calibrate:** `calibrate_confidence(category)` reads recent entries with outcomes: >5 entries, success rate < 0.5 → −10 confidence; > 0.8 → +5; clamped 0–99. Per-category offsets in `config.confidence_calibration`; applied via `update_calibration(category, delta)` (dashboard +/- buttons).
4. **Mode:** log-only first (dashboard displays outcomes, human adjusts manually). Auto-calibration only after ≥20 entries for a given category.
5. **Dashboard analytics:** routing distribution by tier (T1/T2/ASK; T3 must be zero), confidence histogram (watch the 60–80 ASK bucket), tier trend over time, category-tier matrix, effectiveness stats per tier. `config_diff` shows exactly what deviated from stock `$0` defaults.

---

## 6. Dashboard-as-cockpit knob list ($0-only; served on `:8765`, FastAPI `token_optimiser/dashboard/app.py`)

Every knob gets its own config field, docstring, instant effect (no restart — `set_enabled()` flips the singleton), and is exposed on the dashboard. **No hidden knobs. No T3 enable toggle — T3 is hard-locked; any attempt to enable is logged and refused.**

| Group | Knob | Config field | Endpoint | Effect |
|---|---|---|---|---|
| Master | On/off toggle | `enabled` | `/api/config`, `/api/config/toggle` | Instant off-safe; per-instance `enabled` resolution |
| Zero-tier lock | Zero-tier mode / T3 hard lock | `zero_tier_mode`, `t3_hard_disabled` | `/api/config` | Read-only in zero-tier; enabling T3 refused + logged |
| Thresholds | T1 min / T2 min | `threshold_t1_min` (80), `threshold_t2_min` (60) | `/api/config` | Band boundaries; 60–79 = ASK watch bucket |
| ASK | Hybrid band / human band / ambiguous | `ask_human_band`, `ambiguous_task_asks_human`, `hybrid_band_enabled` | `/api/config` | ASK trigger behavior |
| Caps | Security cap + per-category caps | `security_confidence_cap` (55), `category_confidence_caps` | `/api/config` | Per-category confidence ceilings |
| Privacy | Force-T1, keywords, T1b keywords | `privacy_force_t1`, `privacy_offline_keywords`, `t1b_keywords` | `/api/config` | Local short-circuit; data never leaves machine |
| Scope | Prefix regex, value map, word thresholds | `scope_prefix_pattern`, `scope_prefix_values`, `scope_word_thresholds` | `/api/config` | `[small]/[medium]/[large]` parsing |
| Rate ceilings | T2 provider RPM/RPD/TPM | `provider_rate_ceilings` | `/api/config/rate-ceilings` | Fan-out guard inputs (all [unverified]) |
| Calibration | Per-category offsets | `confidence_calibration` | `/api/config/calibration` | +/- offsets from learning-log outcomes |
| Tiers/backends | T1 URL/model/fallback(None); T2 gateways weight/enabled/api_key_env | `tier_backends` | `/api/config`, `/api/tiers/{toggle,health}` | Per-item enable/disable; T3 has no toggle |
| Models | Orchestrator default/escalation/high-frequency | `orchestrator_*_model`, `orchestrator_escalation_threshold` (15) | `/api/config` | Model assignment per task class (free-only roster) |
| Behavior | Parallelize threshold, review, governance mode | `parallelize_threshold` (0.7), `min_review_tier` (T2), `enforce_review`, `governance_mode` (auto) | `/api/config` | Swarm sizing, review, BOA engagement |
| Observability | Learning log viewer, stats, analytics, config diff | — | `/api/learning-log/*`, `/api/analytics/*`, `/api/config/diff` | Cockpit read surface |
| Test console | Ad-hoc assess | — | `/api/assess`, `/api/assess/batch` | Probe routing decisions |

---

## 7. Integration smoke-test structure ("pinky" wrapper)

Executable: `token_optimiser/integration/pinky_smoke_test.py` (stdlib-only — Arch has no system pip; run under a venv/uv). Seven layers, in order; each prints one clear PASS/FAIL line; exit non-zero on any failure; dashboard layer is **skipped, not failed**, if `:8765` isn't serving.

```
1. Dependencies   — import token_optimiser modules; python version; config importable
2. Config ($0)    — assert defaults: t1_min=80, t2_min=60, sec_cap=55, T3 hard-disabled,
                    zero_tier_mode=True, free_tier_priority=False,
                    T1 url=http://192.168.1.10:8081 model=phi-4-mini-instruct,
                    every T2 model entry free-only (:free suffix or NIM/Nous free)
3. Router ($0)    — assess probes:
                    simple → T1 (conf ≥ 80) or T2
                    security → conf ≤ 55, tier ASK, security_escalate flag set
                    3+ categories → ASK
                    [large] prefix → scope == "large"
                    60-79 band (+ask_human_band) → ASK
                    <60 (T3 disabled) → ASK, "no $0 tier cleared"
                    parallelize flag/score present
4. Learning log   — append by task_id; read-back; append_outcome by task_id; clear
5. Pinky wrapper  — optimise()/optimise_batch() dicts with tier/confidence/swarm;
                    disabled fallback → T2; record_outcome() bool
6. Mock backends  — T1/T2/T3 generate(); MockGateway.execute() routes; rate-limit guard:
                    NIM 40 RPM, OpenRouter :free 50 RPM / 50 RPD, Nous 500K TPM
                    (proceed vs serialize decision)
7. Dashboard API  — import app; route registry; optional live GET :8765/api/config (skip if down)
```

Each layer is `check_*()` returning bool; `main()` aggregates, prints summary, returns all-passed. Mock backends need no network — fully offline except optional dashboard GET.

### 7.1 Smoke-test results (this session)

Layers 1–6 pass against current repo code under Python 3.14.7 (prior run: `config t1_min: 80 t2_min: 60 sec_cap: 55`, `T3 enabled: False`, `GET :8765/api/config → 200 OK`). After the zero-tier patches below, re-run and confirm: `free_tier_priority: False`, `zero_tier_mode: True`, security probe → `tier: ASK` with escalation flag, `<60` probe → `tier: ASK`.

---

## 8. Unverified items [unverified]

- NVIDIA NIM ~40 RPM shared; credit pool size; per-model credit cost (~0.05 nano / ~0.2 super / ~0.5 ultra)
- OpenRouter `:free` 50 RPM / 50 RPD hard daily ceiling; whether `:free` roster still includes nemotron-3-ultra-550b:free (rosters change monthly — rescan `/v1/models`)
- Nous Portal OAuth token current validity in `~/.hermes/auth.json` (~1h expiry); refresh flow not probed
- `ollama-7b` availability on T1 (second local model in router order — not confirmed installed)
- NVIDIA NIM tool-calling fidelity per model (nemotron-nano-3-30b verified 404 on `tool_calls`; others unprobed)
- `:8765` on acer serves the neo-light TOS dashboard — port open and serves TOS dashboard HTML; `/api/config` returned 200 from localhost earlier this session (identity from acer not re-probed)
- Clarity dashboard `/api/tos/*` integration with TOS service `:8765`
- `pytest` not installed under `python3.14.7` (no system pip on Arch) → smoke script stdlib-only or `uv` venv
- T3 credentials (`GROK_API_KEY`) present in `~/.hermes/.env` but must never be consumed — enforcement not yet exercised end-to-end

---

## 9. Sources

- `token-budget-routing` skill — router patterns, ASK band (3+ cats / 60–79%), scope prefixes, dashboard-as-cockpit, learning log, pinky smoke test, pitfalls
- `free-tier-swarm-dispatch` skill — provider throughput table, model assignment by task class, `optimise()` first, credentials from `~/.hermes/.env` + `auth.json`
- `neo-light/AGENTS.md`, `ROUTING.md` — model order vulkan-3b → ollama-7b → minimax-m3 → openrouter-free; never SuperGrok/kimi-k2.6/Ultra in this TUI
- `neo-light/token_optimiser/{config,router,monica_integration,boa,credentials}.py`, `dashboard/app.py` — live repo code; wire-verified T1 values
- Live probes this session — TCP `192.168.1.10` `:8081` (phi-4-mini-instruct, 131072 ctx, OK), `:8765` (TOS dashboard HTML, OK); `router.assess()` / `optimise()` run under Python 3.14.7
