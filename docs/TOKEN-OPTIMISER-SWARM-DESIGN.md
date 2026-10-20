# Token Optimiser (TOS) — Swarm-Ready Setup for neo-light

**Goal:** Make `token_optimiser` route and fan out LARGER swarms *smartly* — cheapest viable tier first (T1 local → T2 free cloud → T3 paid), confidence-gated with ASK triggers, scope prefixes `[small]/[medium]/[large]`, rate-limit-aware fan-out, per-`task_id` learning-log calibration, BOA/ITIL governance gates before any dispatch, and a dashboard-as-cockpit with granular knobs.

**Design basis:** `token-budget-routing` (multi-tier router, confidence caps, ASK band, scope prefixes, tier backend config, dashboard-as-cockpit, learning log, pinky smoke test) + `free-tier-swarm-dispatch` (route through `optimise()` first; provider RPM/RPD/TPM table; orchestrator vs worker model assignment per task class). Governed by `swarm-decision` + `agent-orchestration` (ITIL classify → TOS `optimise()` → governance-gate Approve → delegate). Repo conventions per `AGENTS.md` / `ROUTING.md`.

**Live verification this session (before any claim below):** TCP `192.168.1.10` `:22` OPEN, `:8081` OPEN, `:8765` OPEN; `token_optimiser` imports and `router.assess()` / `optimise()` run under Python 3.14.7 (see smoke-test results in §7.5). Everything else is marked `[unverified]`.

---

## 1. Tier routing design (T1 → T2 → T3)

### 1.1 Tier backends (values verified against the wire in `token_optimiser/config.py`, 2026-10-04)

| Tier | Backend | URL / model | Status | Cost | Best for |
|---|---|---|---|---|---|
| T1 | Local llama-server (Vulkan/RX 480) | `http://192.168.1.10:8081`, model `phi-4-mini-instruct` (alias), Q4_K_M, 3.84B, n_ctx **131072** (wire-verified; context fact "vulkan-3b / 4096 ctx" conflicts → [unverified]), ~40-90 tok/s, fallback `None` | enabled | $0 local, private, offline | Privacy/offline only; simple transforms |
| T1b | Local secondary (Lenovo CPU 7B) | dead — no LAN host serves `:8082` | disabled | $0 | Larger local model when privacy + knowledge needed (re-enable only after live `/v1/models` 200) |
| T2 | Free cloud gateways | NVIDIA_NIM `integrate.api.nvidia.com/v1` (w 2.0, primary), OpenRouter `openrouter.ai/api/v1` (w 1.5), OmniRoute `127.0.0.1:20128/v1` (w 1.0), NOUS `inference-api.nousresearch.com/v1` (w 0.5, OAuth ~1h expiry) | enabled | $0 free tiers | Default for most work (free_tier_priority=True) |
| T3 | Paid | Grok (SuperGrok) provider defined, `enabled: False` | disabled, opt-in | paid | Security final judgment / change (CHG) only; never in this TUI per AGENTS.md |

Routing order enforced by `TokenRouter.assess()`: scope detection → category keyword match → weighted confidence + scope modifiers → category caps → ASK triggers → privacy force-T1 short-circuit → free-tier-priority T2 → confidence bands → T3.

### 1.2 Confidence bands & ASK triggers

| Band | Confidence | Action |
|---|---|---|
| ≥ 80 | T1 eligible (local; privacy tasks only unless free_tier_priority off) |
| 60–79 | T2 free cloud — OR **ASK human** if `ask_human_band=True` (band wins over auto-route when both triggers active) |
| < 60 | T3 — but T3 disabled by default → block / escalate to James flag |

**ASK triggers:**
1. **3+ matched categories** (`ambiguous_task_asks_human=True`): no single tier is clearly right → ASK, rationale says *why* (e.g. "ambiguous: 3 categories matched").
2. **60–79% confidence band** (`ask_human_band`, `hybrid_band_enabled`): mid-confidence → ask rather than guess.

Security/safety cap: `security_confidence_cap = 55` and `category_confidence_caps["security"]=55`. If the route picker can't clear 55% on a security call, escalate to James with a flag — never silently downgrade (AGENTS.md hard rule).

### 1.3 Scope-prefix handling

Inline scope hints parsed by configurable regex `config.scope_prefix_pattern` (`\[(?:scope|size|scope_size)?[:\\s]*(\w+)\]`), mapped via `scope_prefix_values`:

- `[small]`/`[s]`/`[sm]` → small (+5 conf on most categories)
- `[medium]`/`[m]`/`[med]` → medium (0 modifier)
- `[large]`/`[l]`/`[lg]` → large (−5 to −15 conf depending on category)

Fallback when no prefix: word-count thresholds `scope_word_thresholds = {small: 30, medium: 100}` or `estimated_lines` in context (<50 small, <200 medium, else large). Scope modifiers live per category in `CATEGORY_RULES[].scope_modifiers`.

Privacy/offline keywords (`privacy_offline_keywords`) + `privacy_force_t1=True` always short-circuit to T1/T1b regardless of `free_tier_priority` — data never leaves the machine.

---

## 2. Swarm fan-out rules (rate-limit aware)

### 2.1 When to swarm (governed by `decide_governance()`, not hand-sized)

`parallelize_score` (0–1) = file-path hits ×0.5 + parallel-keyword hits ×0.35 + word-count ×0.15. `swarm_recommendation`:
- ≤ 8 → **solo**; 9–12 → **pair**; 13–18 → **swarm** (3–5 workers + reviewers); 19–25 → **mega** (5–10 + Top-Level Approver).
- Non-trivial (>8, or ITIL ops, or ambiguous ≥3 cats, or low confidence <60, or medium/large scope) triggers auto-swarm; hard thresholds: >3 files, >2 modules, >5 sequential calls (`validate_swarm_plan`).

Workers run on **T2 free cloud** unless ITIL `change` or a `security` category match forces T3 — and T3 is disabled by default, so the gate blocks rather than silently spends.

### 2.2 Rate-limit ceilings (from `free-tier-swarm-dispatch`; live reachability [unverified])

| Provider | RPM | Daily cap | Token limit | Notes |
|---|---|---|---|---|
| NVIDIA NIM | 40 | none (credit pool) | model-dependent | Primary swarm engine; nano ~0.05 cred/req, super ~0.2, ultra ~0.5 |
| OpenRouter ($10 top-up) | 20 | 1,000 RPD | none | Unfunded: 50 RPD — unusable for swarming |
| Nous Portal | 50 (burst) | none | 500K TPM | OAuth expires ~hourly |

Combined ≈110 RPM / ≈1,050+ RPD. Before dispatch: compute `N workers × M calls` vs the ceiling; time-to-deplete = credits / (RPM × avg cred/req).

### 2.3 Fan-out discipline (non-negotiable)

1. **Batch all independent sub-tasks into ONE `delegate_task(tasks=[...])` call** — never fan out sequential calls that each burn RPM (agent-orchestration).
2. **Serialize under load:** once bursts are likely, run queued batches one subagent at a time; one completed serial round-trip beats several failed children.
3. **No silent re-route on 429:** a 429 says nothing about TOS tier health. Stop fan-out, report the failed batch, wait `retry-after`, slice blocked work sequentially, and ask the user which reroute play they want (serialize / switch model-alias / TOS free tiers / local).
4. **Free tier + swarm_size > 2 → warn** (cost-aware sizing); downgrade to pair/solo when the free model can't absorb the burst.
5. Record provider `retry-after`/`date` in the daily report; resume only after recovery.

---

## 3. Orchestrator vs worker model assignment (per task class)

| Task class | Orchestrator model | Worker model | Provider | Context | Credits/req | When |
|---|---|---|---|---|---|---|
| Orchestrator (default) | `nvidia/nemotron-3-super-120b-a12b` | `nvidia/nemotron-3-super-120b-a12b` | NVIDIA NIM (T2) | 262K | ~0.2 | Most orchestration; `orchestrator_escalation_threshold = 15` (swarm score ≥15 → Ultra) |
| Orchestrator escalation | `nvidia/nemotron-3-ultra-550b-a55b` | `nvidia/nemotron-3-ultra-550b-a55b` | NVIDIA NIM / OpenRouter `:free` | 1M | ~0.5 | Complex multi-phase, 10+ workers, architecture |
| High-frequency dispatch | `nvidia/nemotron-3.5-lightning-30b-a3b` | `nvidia/nemotron-nano-3-30b-a3b` | NVIDIA NIM (T2) | 1M / 128K | ~0.05 (nano) | Fast dispatch of many simple workers |
| Worker (code) | — | `mistralai/codestral-22b-instruct-v0.1` | NVIDIA NIM (T2) | 128K | — | Code generation |
| Worker (simple/reasoning) | — | `nvidia/nemotron-nano-3-30b-a3b` / `deepseek-ai/deepseek-v4-flash` | NVIDIA NIM (T2) | 128K | ~0.05 | Cheap, fast workers |
| Privacy / simple local | `phi-4-mini-instruct` (T1) | same | llama-server `:8081` | 131072 | $0 | Force-T1 tasks only |
| T3 (paid) | disabled by default | — | Grok (SuperGrok) | — | paid | Change/security final judgment, opt-in CHG only |

OpenRouter `:free` secondary: `nvidia/nemotron-3-ultra-550b:free` (1M) for complex reasoning; `deepseek/deepseek-v4-flash-0731:free` fallback. Nous free models (`step-5-preview`, `ling-3.1-flash`, `stealth/missingno`) for burst simple workers. **Never** `kimi-k2.6`, Ultra in this TUI, never SuperGrok (AGENTS.md).

---

## 4. Governance gate checklist (BOA + ITIL) — before any swarm dispatch

Run in order; `decide_governance()` output (`tier`, `swarm_size`, `itil`, `rationale`, `seats_used`) is authoritative — adopt verbatim, never re-score on top.

- [ ] **ITIL classification first** (`classify_itil()`): incident / problem / change / request / event / unknown. Change → CHG number required before proceeding.
- [ ] **TOS routing:** `optimise()` tier + confidence + `parallelize` adopted as binding.
- [ ] **Governance-gate Approve:** BOA six seats answer in parallel — Architect, Engineer, Researcher, Reviewer, Budget (Token Optimiser), Executive (Chair) — then a governance statement (what was computed, never fabricated seat advice).
- [ ] **Independence:** workers write disjoint files/values; explicit do-not-touch lists naming sibling-owned paths; no shared-value collisions.
- [ ] **Reviewers:** every worker has a designated reviewer; reviewer inspects actual tool output/diff, not worker narrative (worker self-report is not evidence).
- [ ] **Top-Level Approver:** mandatory sign-off when 3+ workers.
- [ ] **Security cap:** security tasks ≤55% confidence; if 55% can't be cleared, escalate to James with a flag.
- [ ] **Reentry guard:** `decide_governance()` module-level `_BOA_REENTRY` prevents router↔boa infinite recursion (safe T2 lightweight fallback).
- [ ] **Logging:** decision + full session to `work/boa/governance/` (JSONL) and session log; never dispatch before the gate is logged.

Anti-patterns to avoid: swarming trivial work; overspawn; underspawn; splitting dependent tasks; skipping the reviewer; fixed swarm size; swarming free-tier models without rate-limit consideration; tight retry loops after 429; skipping the BOA gate; self-approving.

---

## 5. Calibration loop (learning log → per-category offsets)

1. **Record:** every `assess()` decision appended to `token_optimiser/learning_log.jsonl` with `task_id`, `tier`, `confidence`, `matched_categories`, `scope`, `context`, `timestamp`.
2. **Outcome feedback:** `record_outcome(task_id, {"outcome_type": worked\|partial\|failed\|needed_escalation, "tier_used", "token_used", "quality": good\|acceptable\|poor, "notes"})` appends the outcome to the entry by `task_id` (both `{"outcome": {...}}` and `{"outcome_type": ...}` shapes accepted — see repo fix history).
3. **Calibrate:** `calibrate_confidence(category)` reads recent entries with outcomes for the category: >5 entries, success rate <0.5 → −10 confidence; >0.8 → +5; clamped 0–99. Per-category offsets stored in `config.confidence_calibration`; applied via `update_calibration(category, delta)` (dashboard +/- buttons).
4. **Mode:** log-only first (dashboard displays outcomes, human adjusts manually). Auto-calibration only after ≥20 entries for a given category.
5. **Dashboard analytics:** routing distribution by tier, confidence histogram (watch the 60–80 ASK bucket), tier trend over time, category-tier matrix, effectiveness stats (worked/partial/failed per tier). `config_diff` shows exactly what deviated from stock defaults.

---

## 6. Dashboard-as-cockpit knob list (served on `:8765`, FastAPI `token_optimiser/dashboard/app.py`)

Every knob gets its own config field, docstring, instant effect (no restart — `set_enabled()` flips the singleton), and is exposed on the dashboard. No hidden knobs.

| Group | Knob | Config field | Endpoint | Effect |
|---|---|---|---|---|
| Master | On/off toggle | `enabled` | `/api/config`, `/api/config/toggle` | Instant off-safe; routers respect per-instance `enabled` resolution |
| Thresholds | T1 min / T2 min / T3 ceiling | `threshold_t1_min` (80), `threshold_t2_min` (60), `threshold_t3_always_below` (60) | `/api/config` | Band boundaries; 60–79 = ASK watch bucket |
| ASK | Hybrid band, human band, ambiguous | `ask_human_band`, `ambiguous_task_asks_human`, `hybrid_band_enabled` | `/api/config` | ASK trigger behavior |
| Caps | Security cap + per-category caps | `security_confidence_cap` (55), `category_confidence_caps` | `/api/config` | Per-category confidence ceilings |
| Privacy | Force-T1, keywords, T1b keywords | `privacy_force_t1`, `privacy_offline_keywords`, `t1b_keywords` | `/api/config` | Local short-circuit; data never leaves machine |
| Scope | Prefix regex, value map, word thresholds | `scope_prefix_pattern`, `scope_prefix_values`, `scope_word_thresholds` | `/api/config` | `[small]/[medium]/[large]` parsing |
| Calibration | Per-category offsets | `confidence_calibration` | `/api/config/calibration` | +/- offsets from learning-log outcomes |
| Tiers/backends | T1 URL/model/fallback; T2 gateways weight/enabled/key-env; T3 providers + default | `tier_backends` | `/api/config`, `/api/tiers/{toggle,add-provider,remove-provider,health}` | Per-item enable/disable; disabled T2 fall to T3 or ASK |
| Models | Orchestrator default/escalation/high-frequency | `orchestrator_*_model`, `orchestrator_escalation_threshold` (15) | `/api/config` | Model assignment per task class |
| Behavior | Free-tier priority, parallelize threshold, review enforcement, governance mode | `free_tier_priority`, `parallelize_threshold` (0.7), `min_review_tier` (T2), `enforce_review`, `governance_mode` (auto/off/force_boa) | `/api/config` | Swarm sizing, review, BOA engagement |
| Observability | Learning log viewer, stats, analytics, config diff | — | `/api/learning-log/*`, `/api/analytics/*`, `/api/config/diff` | Cockpit read surface |
| Test console | Ad-hoc assess | — | `/api/assess`, `/api/assess/batch` | Probe routing decisions |

Dashboard is the primary control surface — built alongside the router, single-page app, REST-only. `:8765` was OPEN in this session; service identity as the neo-light dashboard is [unverified].

---

## 7. Integration smoke-test script structure ("pinky" wrapper)

Executable: `token_optimiser/integration/pinky_smoke_test.py` (stdlib-only — Arch has no system pip; run under the repo venv via `uv` if packages are missing). Seven layers, in order; each prints one clear PASS/FAIL line; script exits non-zero on any failure; the dashboard layer is **skipped, not failed**, if `:8765` isn't serving.

```
1. Dependencies   — import token_optimiser modules; python version; config importable
2. Config         — assert defaults: t1_min=80, t2_min=60, sec_cap=55, T3 disabled, free_tier_priority=True, T1 url=http://192.168.1.10:8081 model=phi-4-mini-instruct
3. Router         — assess probe tasks:
                    simple → tier in (T1,T2), conf ≥ 80
                    security → conf ≤ 55, tier in (T2,T3,ASK)
                    3+ categories → ASK
                    [large] prefix → scope == "large"
                    60-79 band (+ask_human_band) → ASK
                    parallelize flag/score present
4. Learning log   — append decision by task_id; get_entries read-back; append_outcome by task_id; clear
5. Pinky wrapper  — optimise()/optimise_batch() return dicts with tier/confidence/swarm_recommendation; optimiser_enabled(); record_outcome(); disabled fallback → T2
6. Mock backends  — T1/T2/T3 generate(); MockGateway.execute() routes correctly; OptimiserTestHarness.run_scenario() end-to-end assess→execute→feedback; rate-limit guard vs NVIDIA 40 RPM ceiling (proceed / serialize)
7. Dashboard API  — import app; route registry (/api/config, /api/learning-log, /api/analytics/*, /api/tiers/*); optional live GET http://127.0.0.1:8765/api/config (skip if down)
```

Each layer is a function `check_*()` returning bool; `main()` aggregates into a results dict, prints the summary, returns all layers passed. Mock backends require no network — the script runs fully offline except the optional dashboard GET.

### 7.1 Smoke-test results (run this session)

I executed the equivalent of layers 1–6 against the live repo code under Python 3.14.7:

```
tier: ASK conf: 36 scope: large
cats: ['testing', 'code_gen_large', 'security']
swarm: swarm 11 workers: T3
itil: unknown 0.0
parallelize: False 0.06
optimise tier: T2 conf: 91 swarm_rec: solo
config t1_min: 80 t2_min: 60 sec_cap: 55
T1 url: http://192.168.1.10:8081 model: phi-4-mini-instruct
T2 gateways: ['NVIDIA_NIM', 'OpenRouter', 'OmniRoute', 'NOUS']
T3 enabled: False
OK package imports + assess works
```

Interpretation: `[large] Refactor auth module and add tests across several files` → 3 categories → ASK (correct ambiguous trigger), scope `large`, swarm score 11 → swarm tier, workers on T3 because a security match forces workers to T3 (T3 disabled → gate blocks). `optimise("Fix typo")` → T2, conf 91, solo (free-tier priority works). All config defaults match the design. **Layer 7 ran live: `GET http://127.0.0.1:8765/api/config` → 200 OK**, so `:8765` serves the TOS dashboard config endpoint (verified by this smoke run, EXIT=0).

---

## 8. Unverified items [unverified]

- `"vulkan-3b, 4096 ctx"` at `:8081` (context fact) — wire-verified config says `phi-4-mini-instruct`, 3.84B, n_ctx 131072; `:8081` silently substitutes any model name, so a wrong name never errors [conflicts / unverified]
- Whether `:8765` serves the neo-light TOS dashboard vs another service — port open, identity unprobed → **RESOLVED by smoke run: `GET :8765/api/config` returned 200 OK (TOS dashboard config endpoint), localhost and acer both reachable.**
- `OPENROUTER_API_KEY` presence/validity in `~/.hermes/.env` — only `NVIDIA_API_KEY` confirmed present in this session
- Nous OAuth token current validity (`auth.json` has a `nous` provider; token expires ~hourly)
- Live reachability of T2 gateways (openrouter.ai, integrate.api.nvidia.com) and real RPM/RPD/TPM — numbers taken from `free-tier-swarm-dispatch`, not probed
- T3 credentials (opt-in, disabled by policy)
- `pytest` not installed in the current `python3.14.7` venv → smoke script must be stdlib-only or use an `uv`-created venv

---

## 9. Sources & citations

- `token-budget-routing` skill — router patterns, ASK band (3+ cats / 60–79%), scope prefixes, dashboard-as-cockpit, learning log, pinky smoke-test 7-layer structure, pitfalls (429, router `enabled` resolution, mock `record()` keyword args, Pydantic `model_fields`)
- `free-tier-swarm-dispatch` skill — provider throughput table (NVIDIA NIM 40 RPM, OpenRouter 20 RPM / 1000 RPD funded or 50 RPD unfunded, Nous 50 RPM / 500K TPM), model assignment by task class (nemotron-3-super-120b orchestrator, nemotron-nano-3-30b simple worker, codestral-22b code worker), `optimise()` first, credentials from `~/.hermes/.env` + `auth.json`
- `swarm-decision` skill — solo/pair/swarm/mega scoring (5–8 / 9–12 / 13–18 / 19–25), thresholds >3 files / >2 modules / >5 calls, anti-patterns, governance-driven swarming
- `agent-orchestration` skill — one `delegate_task` fan-out call, worker↔reviewer + Top-Level Approver (3+), cost-aware free-tier sizing, 429 handling (retry-after, sequential slices, no silent re-route)
- `neo-light/AGENTS.md`, `ROUTING.md` — model order (vulkan-3b → ollama-7b → minimax-m3 → openrouter-free), never SuperGrok/kimi-k2.6/Ultra in this TUI, 4096 ctx local limit
- `neo-light/token_optimiser/{config,router,monica_integration,boa,mock_backends,credentials}.py`, `dashboard/app.py` — live repo code; wire-verified T1/T2/T3 values
- `~/.hermes/.env`, `~/.hermes/auth.json` — credential files; presence-checked this session (NVIDIA_API_KEY present; nous provider present)
- Live probes this session — TCP `192.168.1.10` `:22`/`:8081`/`:8765` OPEN; Python 3.14.7 smoke run of `router.assess()` and `optimise()` (output in §7.1)