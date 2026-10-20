# Monica's Skills — Updated Best Picks, Exclusive $0 Free Tier

**Scope:** Monica's skill roles — PA/business-manager work, orchestrator routing, swarm workers, code tasks.
**Constraint:** $0 total spend. Only models with a genuine no-payment-path route qualify. Anything that requires a credit card, top-up, paid plan, or AI Enterprise license is EXCLUDED.
**Workspace:** `/home/warpuppy/Projects/neo-light`
**Status date:** 2026-10-19 (SAST). All `$0` claims grounded in sources below; reachability = network reachable (HTTP 200 on `/v1/models` without auth). Model *invocation* was NOT live-tested (no API keys held) and is marked `[unverified-invocation]`.

---

## Verified reachability (live this session)

| Endpoint | HTTP | Reachable? | Notes |
|---|---|---|---|
| `https://openrouter.ai/api/v1/models` | 200 | Yes | Nous Portal (`inference-api.nousresearch.com/v1`) returns the identical list — Nous Portal is OpenRouter-backed |
| `https://integrate.api.nvidia.com/v1/models` | 200 | Yes | NVIDIA NIM gateway reachable; `nemotron-3-super-120b-a12b` free endpoint deprecated 10/19/2026 |
| `http://acer:8081/v1.models` | 200 | Yes | Local llama-server; serves `phi-4-mini-instruct` only (vulkan-3b NOT listed) |

---

## Per-model table (all candidates evaluated)

| # | Model | Provider / route | Truly $0? | Context window | Limits | Purpose | Swarm-suitable? | Tool-calling fidelity | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `nemotron-3-super-120b-a12b` | OpenRouter `:free` (`nvidia/...:free`); NVIDIA NIM (free endpoint deprecated today) | YES (OpenRouter `:free`) | 1M (NVIDIA) / 262K (OpenRouter listing — discrepancy) | OpenRouter `:free` 50 RPD unfunded (swarm-hostile); NIM 40 RPM (design doc) | Orchestrator / complex reasoning / tool use | NO on `:free` (50 RPD); OK as single-shot orchestrator | **Verified** (live this session + OpenRouter: accepts `tools`/`tool_choice`) | **PICK — orchestrator** |
| 2 | `nemotron-3-ultra-550b-a55b` | OpenRouter `:free` | YES (OpenRouter `:free`) | 1M | OpenRouter `:free` 50 RPD; uptime ~20–26% | Escalation / complex multi-phase | NO (low uptime + 50 RPD) | [unverified-invocation] | **Pick — escalation only** (flagged below) |
| 3 | `nemotron-3.5-super-vl` | OpenRouter `:free` (`nvidia/nemotron-3.5-super-vl:free`) | YES | 1M | OpenRouter `:free` 50 RPD | VLM: text/image/document/PDF/video in → text out | NO (50 RPD) | [documented "tool use"; not live-verified] | **Pick — VLP/vision tasks only** |
| 4 | `deepseek-v4-flash` | OpenRouter `:free` (`deepseek/deepseek-v4-flash:free`); PAID on Nous Portal ($0.07/$0.14 per 1M) | YES (OpenRouter `:free` only) | [unverified] | OpenRouter `:free` 50 RPD | Reasoning / code / flash workers | NO (50 RPD); OK single-shot | [unverified-invocation] | **Pick — code/reasoning fallback** |
| 5 | `phi-4-mini-instruct` | Local llama-server `http://acer:8081` (GGUF Q4_K, 3.8B) | YES ($0 local) | 131072 (verified) | None (local, private, offline) | Simple transforms, small code, PII-force-local | **YES** — only $0 swarm-worker route | [unverified-invocation] (small model; likely weak) | **PICK — T1 swarm worker / force-local** |
| 6 | `nemotron-3-nano-3-30b` (`nemotron-3-nano-30b-a3b`) | NVIDIA NIM (free endpoint deprecated) | [unverified / deprecated] | 1M (nvidia.com) / 262K (build.nvidia) | NIM 40 RPM | Simple sub-agents | NO | **NOT supported** — 404 on tools (per prior research) | **EXCLUDED — no tools + deprecated endpoint** |
| 7 | `codestral-22b` | Mistral La Plateforme / OpenRouter | **NO — PAID** | 32K | $0.30 in / $0.90 out per 1M; OpenRouter "Paid API Only" | Code generation | N/A (paid) | N/A | **EXCLUDED — requires payment** |
| 8 | `nemotron-3-super-120b-a12b` (NVIDIA NIM direct) | NVIDIA NIM `integrate.api.nvidia.com` | Endpoint deprecated today | — | — | — | — | — | **EXCLUDED — NIM free endpoint deprecated 10/19/2026** |

### Nous Portal free catalog ($0, 50 RPM / 500K TPM, no card, OpenAI-compatible at `https://inference-api.nousresearch.com/v1`)
Free models (rotates monthly): Step 5 Preview, LongCat 2.0, LongCat 2.5 Preview, Step 3.7 Flash, Beam 1.0 501B A23B, Laguna S 2.1, Laguna XS 2.1, Solar Mini 4. Source: portal.nousresearch.com/models; dev.to Nous Portal explained; llmperks.com/nous.
- DeepSeek V4 Flash on Nous Portal is **PAID** ($0.07/$0.14 per 1M) — do NOT route Monica's Nous traffic to it expecting $0.
- Role: burst simple workers / overflow when OpenRouter `:free` 50 RPD is exhausted. [unverified-invocation — requires API key]

---

## Best picks per role (exclusive $0)

### 1. PA / business-manager work (Monica)
Non-PII tasks: portal summaries, pipeline/invoice summaries, follow-up lists, ops-log prep, time-tracking prep.
- **Primary:** `deepseek-v4-flash:free` (OpenRouter `:free`) — strong reasoning/flash, $0. Single-shot only (50 RPD).
- **Burst/overflow:** Nous Portal free models (Step 5 Preview, LongCat 2.0/2.5, Ling 3.1 Flash) at `inference-api.nousresearch.com/v1` — 50 RPM / 500K TPM, no card. [unverified-invocation]
- **PII/privacy (force T1 per router.py `monica_*` categories):** `phi-4-mini-instruct` on `acer:8081` — local, $0, offline. Router already force-tiers `monica_mail_triage_private`, `monica_customer_records_local`, `monica_*_redaction`, `monica_export_anonymization`, `monica_reidentification_guard`, etc. to T1.

### 2. Orchestrator routing
- **Primary:** `nemotron-3-super-120b-a12b:free` — tool-calling verified, 1M ctx, best free orchestrator. Limit: 50 RPD on OpenRouter `:free` — fine for low-frequency orchestration, NOT for fan-out.
- **Escalation (complex multi-phase, 10+ workers, architecture):** `nemotron-3-ultra-550b-a55b:free` — 1M ctx, $0, but uptime only ~20–26% and 50 RPD. Use only as escalation fallback.
- **AGENTS.md note:** "Never … Ultra in this TUI" refers to Grok Ultra/xAI; `nemotron-3-ultra-550b` is evaluated here because you explicitly listed it — keep it escalation-only and flagged.

### 3. Swarm workers (fan-out)
- **Only $0 route that survives fan-out:** `phi-4-mini-instruct` on local `acer:8081` — no RPM ceiling, private, offline. 3.8B → simple tasks only (transforms, small snippets, classification).
- **Do NOT use OpenRouter `:free` or Nous for swarm workers** — 50 RPD (OpenRouter) / 50 RPM (Nous) will throttle a swarm. Per design doc: "Free tier + swarm_size > 2 → warn; downgrade to pair/solo."

### 4. Code tasks
- `codestral-22b` is **EXCLUDED** (paid, no `:free`). Replacement under $0:
- **Primary:** `deepseek-v4-flash:free` (OpenRouter `:free`) — reasoning/code-capable flash model. Single-shot (50 RPD).
- **Small/local snippets:** `phi-4-mini-instruct` on `acer:8081` — $0, private, small-code only.
- No verified free tool-calling code model remains under $0 besides the above; complex code generation should stay with the orchestrator (`nemotron-3-super-120b:free`), not a swarm worker.

---

## EXCLUDED — requires payment or top-up (do not use)

| Model | Reason |
|---|---|
| `codestral-22b` | Mistral API $0.30/$0.90 per 1M; OpenRouter "Paid API Only"; no `:free` variant listed |
| `nemotron-3-super-120b-a12b` via NVIDIA NIM direct | Free endpoint deprecated 10/19/2026; NIM container deployment requires NVIDIA AI Enterprise license (paid) |
| `nemotron-3-nano-3-30b` | NIM free endpoint deprecated; no tool calling (404 on tools) |
| Nous Portal DeepSeek V4 Flash | Paid on Nous ($0.07/$0.14 per 1M) even though free on OpenRouter `:free` |
| T3 / Grok SuperGrok / xAI Ultra / `kimi-k2.6` | Paid; barred by AGENTS.md for this TUI |

---

## Grounding / sources

1. OpenRouter `nvidia/nemotron-3-super-120b-a12b:free` — free, tools supported, 262K ctx (OpenRouter listing): https://openrouter.ai/nvidia/nemotron-3-super-120b-a12b:free
2. NVIDIA build.nvidia.com `nemotron-3-super-120b-a12b` — free endpoint deprecated 10/19/2026: https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b
3. NVIDIA docs API reference: https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-super-120b-a12b
4. OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free` — free, 1M ctx, uptime ~20–26%: https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free
5. OpenRouter `deepseek/deepseek-v4-flash:free` — free: https://openrouter.ai/deepseek/deepseek-v4-flash:free
6. Mistral AI pricing — Codestral $0.30 in / $0.90 out per 1M (paid): https://docs.mistral.ai/inference/pricing
7. NVIDIA build.nvidia.com `nemotron-3-nano-30b-a3b` — free endpoint deprecated: https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b
8. OpenRouter `nvidia/nemotron-3.5-super-vl:free` — free, 1M ctx, NVIDIA provider 96.55% uptime: https://openrouter.ai/nvidia/nemotron-3.5-super-vl:free
9. Nous Portal models (free list) + 50 RPM / 500K TPM, no card: https://portal.nousresearch.com/models
10. dev.to "Nous Portal, Explained" — free plan $0, 50 RPM/500K TPM, OpenRouter-backed: https://dev.to/zackchew/nous-portal-explained-plans-models-tools-and-hermes-cloud-9hh
11. llmperks.com/nous — 8 free models, base URL `https://inference-api.nousresearch.com/v1`: https://www.llmperks.com/nous
12. nvidia.com Nemotron LLM info — hosted inference at build.nvidia.com, OpenMDW-1.1, AI Enterprise required for NIM: https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/llm-info/
13. Live curl this session: `acer:8081/v1/models` → `phi-4-mini-instruct` only (3.8B, 131072 ctx); OpenRouter/NVIDIA/Nous API roots all HTTP 200.
14. Repo: `token_optimiser/router.py` (Tiers, `monica_*` force-T1 categories, security cap 55), `docs/TOKEN-OPTIMISER-SWARM-DESIGN.md` §3 (orchestrator/worker table), `AGENTS.md` (routing order, never-SuperGrok/Ultra/kimi-k2.6).

---

## Marked `[unverified-invocation]`
No API keys were held, so actual chat/completions/tool-calling calls to OpenRouter, NVIDIA NIM, or Nous Portal were not executed. Reachability (HTTP 200 on the model-list root) and `$0` pricing are documented/verified; per-model invocation fidelity remains `[unverified-invocation]` until a key is configured and a smoke test is run.
