# neo-light Status Report

**Last updated:** 2026-10-05 18:15 SAST
**Fixed by:** Monica (on behalf of space-bunny-alpha's interrupted session)

---

## What Was Fixed

### Dashboard Unit (token-optimiser-dashboard.service)
- **Problem:** WorkingDirectory pointed at `/home/warpuppy/Projects/neo-light-warpuppy` but ExecStart used `/home/warpuppy/Projects/pinky-optimiser/.venv/bin/python` — dashboard was running from the wrong project.
- **Fix:** Updated `WorkingDirectory=/home/warpuppy/Projects/neo-light` so the dashboard runs from the correct repo.
- **Python:** Still uses `pinky-optimiser/.venv/bin/python` (neo-light has no .venv of its own).
- **Status:** Active (running), port 8765, HTTP 200.

---

## Current State

### Running Services

| Service | Status | Details |
|---------|--------|---------|
| `token-optimiser-dashboard.service` | Active (running) | Port 8765, HTTP 200, "Token Optimiser Dashboard" |
| `llama-vulkan.service` | Active (running) | Port 8081, serving `phi-4-mini-instruct` (Phi-4-mini Q4_K_M, 128K ctx, Vulkan on RX 480) |

### NOT Running

- **neo-light TUI** — it's a CLI launcher (`bin/neo`), not a daemon. No process expected unless the TUI is open.
- **Learning log stale** — `token_optimiser/learning_log.jsonl` last written Sep 20. 124 entries total (T1:10, T2:69, T3:45). No routing decisions logged in 15 days.

### Dashboard API (verified working)

- `GET /` → 200, "Token Optimiser Dashboard"
- `GET /api/learning-log/stats` → `{"total_entries":124,"by_tier":{"T2":69,"T1":10,"T3":45}}`
- `GET /api/analytics/overview` → `{"total_assessments":124,"avg_confidence":76.2,"tier_distribution":{"T2":55.6,"T1":8.1,"T3":36.3}}`

---

## Uncommitted Changes (16 files, +575 / -97)

```
docs/lenovo-helper-setup.md                        |  16 +-
token_optimiser/__init__.py                        |  10 +-
token_optimiser/__pycache__/...                    |  Bin (multiple)
token_optimiser/boa.py                             | 380 ++++++++++++++++++---
token_optimiser/config.py                          |  72 +++-
token_optimiser/dashboard/ollama_control.py        |  21 +-
token_optimiser/monica_integration.py              |  18 +-
token_optimiser/router.py                          |  87 ++++-
token_optimiser/tests/test_integration.py          |  48 ++-
work/stout-hermes-task.md                          |  12 +-
work/stout-paste-to-stepfun.md                     |   8 +-
```

**Key changes:** BOA+ITIL governance, T1b tier (Lenovo M710Q Qwen2.5-7B CPU inference), router/config enhancements.

**Last commit:** `2e66f76 Add T1b tier: Lenovo M710Q Qwen2.5-7B CPU inference`
**Branch:** main, 1 commit ahead of origin/main

---

## Known Issues

### 1. helper-mirror.service (FAILING)
- **Error:** rsync code 23, permission denied on `/home/warpuppy/Projects/stout/work/x86_64/airootfs/var/lib/rpcbind`, `var/log/audit`, `var/log/private`, `var/named`, `var/log/btmp`
- **Cause:** `stout/work/x86_64/airootfs/` contains root-owned files that the user rsync can't read.
- **Fix needed:** Either `sudo chown` those directories, or add `--exclude` for `stout/work/x86_64/airootfs/` in the rsync command.
- **Impact:** Twinforge mirror to Lenovo is not working. Unrelated to neo-light.

### 2. neo-light has no .venv
- The dashboard uses `pinky-optimiser/.venv/bin/python` because neo-light doesn't have its own virtual environment.
- All deps (fastapi, uvicorn, pydantic, httpx) are installed in pinky-optimiser's venv.

---

## How to Run neo-light

```bash
# Start the TUI
~/Projects/neo-light/bin/neo

# Dashboard is already running on :8765
# Open http://192.168.1.10:8765 in a browser
```

---

## neo-light-core Library

**Repo:** `/home/warpuppy/Projects/neo-light-core/`
**Tags:** v1.0.0, v2.0.0, v2.1.0 (working tree is ahead of v2.1.0)
**Commits:** 3 (latest: `c2f48b3 Add token_optimiser module with T1b Lenovo tier`)

### Dual Layout
- **Root files** (boa.py, config.py, router.py, etc.) — STALE, from older flatten-refactor
- **token_optimiser/ package** — THE ACTUAL CODE, updated with all fixes

### Key Fixes in token_optimiser/ (vs root)
| File | Fix |
|------|-----|
| `boa.py` | +1473 lines, anti-hijack `_ask_prompt()`, 6-seat board, ITIL classify, governance logging |
| `config.py` | phi-4-mini Q4_K_M 128K ctx (was Phi-3.5-mini Q5_K_M), T1b disabled, credentials auto-load |
| `router.py` | `backend="llama_server"` (was "ollama"), T1b tier, category heuristics, parallelization |
| `credentials.py` | NEW — auto-loads `~/.hermes/.env` so free tiers don't look unavailable |

### Critical Bugs Fixed
1. **Credentials** — token_optimiser never loaded `~/.hermes/.env`, so free tiers looked unavailable → escalated to T3
2. **Calibration** — writer stored `outcome={"outcome": "worked"}`, reader looked for `"outcome_type"` → permanent -10 penalty per category
3. **T1 backend** — declared `"ollama"` but URL is llama-server → code matching on backend=="ollama" never reached T1
4. **T1b dead** — both 192.168.1.8:8082 and 192.168.1.102:8082 return HTTP 000, disabled in config

### Uncommitted Changes (7 modified + 1 new)
```
 M token_optimiser/__init__.py
 M token_optimiser/boa.py
 M token_optimiser/config.py
 M token_optimiser/dashboard/ollama_control.py
 M token_optimiser/monica_integration.py
 M token_optimiser/router.py
 M token_optimiser/tests/test_integration.py
?? token_optimiser/credentials.py
```

---

## File Locations

| What | Path |
|------|------|
| Repo | `/home/warpuppy/Projects/neo-light/` |
| Dashboard unit | `~/.config/systemd/user/token-optimiser-dashboard.service` |
| T1 model | `/home/warpuppy/model/models/Phi-4-mini-instruct-Q4_K_M.gguf` |
| Learning log | `/home/warpuppy/Projects/neo-light/token_optimiser/learning_log.jsonl` |
| Fork (warpuppy) | `/home/warpuppy/Projects/neo-light-warpuppy/` |
| Fork (phantom) | `/home/warpuppy/Projects/neo-light-phantom/` |
| Core library | `/home/warpuppy/Projects/neo-light-core/` |
| pinky-optimiser (dashboard venv) | `/home/warpuppy/Projects/pinky-optimiser/` |
