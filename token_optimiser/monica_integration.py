#!/usr/bin/env python3
"""
Token Optimiser — Monica Integration (Thin Wrapper)

UPDATED 2026-09-19:
- Free tier priority mode enabled by default
- T2 free cloud now stronger than T1 local for most tasks
- NVIDIA NIM, DeepSeek V4 Flash, Poolside Laguna integrated
"""

import sys
import os
from typing import Optional, Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from token_optimiser.router import LearningLog


def calibrate_confidence(category: str, base_confidence: int) -> int:
    """
    Adjust confidence based on learning log outcomes for the given category.

    Reads learning log entries for the category. If >5 entries with outcomes
    exist and success rate < 50%, reduce by 10. If >80%, increase by 5.
    Result is capped at 0-99.
    """
    if not category:
        return base_confidence
    log = LearningLog()
    entries = log.get_recent(1000)  # get all recent entries (up to 1000)
    category_entries = [
        e for e in entries
        if category in e.get("matched_categories", []) and "outcome" in e
    ]
    if len(category_entries) <= 5:
        return base_confidence
    # The writer (plugin.token_optimiser_feedback) stores
    #   {"outcome": {"outcome": "worked", "quality": ..., "delta": 0}}
    # NOT an "outcome_type" key. The old lookup here always missed, so
    # success_rate was 0.0 for every category and the <0.5 branch fired a
    # permanent -10 penalty despite a ~93% real success rate.
    # Accept both shapes so old and new log rows are honoured.
    def _worked(entry: dict) -> bool:
        outcome = entry.get("outcome") or {}
        if not isinstance(outcome, dict):
            return str(outcome).strip().lower() in ("worked", "success", "ok", "true")
        marker = outcome.get("outcome_type", outcome.get("outcome"))
        return str(marker).strip().lower() in ("worked", "success", "ok", "true")

    successes = sum(1 for e in category_entries if _worked(e))
    success_rate = successes / len(category_entries)
    if success_rate < 0.5:
        base_confidence -= 10
    elif success_rate > 0.8:
        base_confidence += 5
    return max(0, min(99, base_confidence))


def optimise(task: str, context: Optional[dict] = None) -> Dict[str, Any]:
    """
    Assess a task and return a routing decision with parallelization info.
    """
    from token_optimiser.router import TokenRouter
    router = TokenRouter()
    decision = router.assess(task, context or {})
    result = decision.to_dict()
    result["parallelize"] = decision.parallelize
    result["parallelize_score"] = decision.parallelize_score

    # Calibrate confidence based on learning log outcomes
    category = result.get("matched_categories", [None])[0] if result.get("matched_categories") else None
    if category:
        calibrated = calibrate_confidence(category, result["confidence"])
        result["confidence"] = calibrated
        result["calibrated"] = calibrated != decision.confidence
        if result["calibrated"]:
            result["rationale"] += f" | Calibrated: {decision.confidence} → {calibrated} (category: {category})"

    # BOA/ITIL governance enrichment (new)
    result["itil_classification"] = getattr(decision, "itil_classification", None) or result.get("itil_classification")
    result["swarm_recommendation"] = getattr(decision, "swarm_recommendation", None) or result.get("swarm_recommendation")
    result["governance_applied"] = bool(result.get("itil_classification") or result.get("swarm_recommendation"))
    result["governance_mode"] = "auto"

    return result


def optimise_batch(tasks: List[str], context: Optional[dict] = None) -> List[Dict[str, Any]]:
    from token_optimiser.router import TokenRouter
    router = TokenRouter()
    results = []
    for task in tasks:
        decision = router.assess(task, context or {})
        result = decision.to_dict()
        result["parallelize"] = decision.parallelize
        result["parallelize_score"] = decision.parallelize_score

        # Calibrate confidence based on learning log outcomes
        category = result.get("matched_categories", [None])[0] if result.get("matched_categories") else None
        if category:
            calibrated = calibrate_confidence(category, result["confidence"])
            result["confidence"] = calibrated
            result["calibrated"] = calibrated != decision.confidence
            if result["calibrated"]:
                result["rationale"] += f" | Calibrated: {decision.confidence} → {calibrated} (category: {category})"

        results.append(result)
    return results


def optimiser_enabled() -> bool:
    from token_optimiser.config import config
    return bool(config.enabled)


def record_outcome(task_id: str, outcome: dict) -> bool:
    from token_optimiser.router import LearningLog
    log = LearningLog()
    return log.append_outcome(task_id, outcome)


def get_learning_log(limit: int = 50) -> List[dict]:
    from token_optimiser.router import LearningLog
    log = LearningLog()
    return log.get_recent(limit)


def get_orchestrator_routing(task_type: str, confidence: int) -> Dict[str, Any]:
    """
    Return an orchestrator-aware RoutingDecision for the given task_type.

    Always uses route_orchestrator_task under the hood, guaranteeing that
    reviews and orchestrator tasks land on a capable tier.  Same task_type +
    same confidence + same config ⇒ same decision (deterministic).
    """
    from token_optimiser.router import route_orchestrator_task
    decision = route_orchestrator_task(task_type, confidence)
    return decision.to_dict()


def should_review(task_type: str) -> bool:
    """
    Return True if the given task_type requires a review pass.

    Deterministic: depends only on the task_type and config.enforce_review.
    """
    from token_optimiser.config import config
    if not config.enforce_review:
        return False
    task_lower = task_type.lower()
    review_patterns = ("review", "complex_worker", "multi_worker", "orchestrate")
    return any(p in task_lower for p in review_patterns)


# ── System Prompt Text ──────────────────────────────────────────────────────────

SYSTEM_PROMPT_INSTRUCTIONS = """
## Token Optimiser (Always-On Pre-Dispatch Filter)

Before dispatching ANY worker, you must route the task through the token
optimiser. This is mandatory — every agent call passes through it.

### How to call it

    from token_optimiser.monica_integration import optimise, optimiser_enabled
    decision = optimise(task_description, {"estimated_lines": 50})

### Tier meanings ($0 zero-tier mode; router order T1 local -> T2 free cloud)

- T1: Local llama-server (phi-4-mini-instruct Q4_K_M on RX 480, `http://192.168.1.10:8081`,
  n_ctx 131072 wire-verified). Fast, free, private, offline.
  Used for: privacy-sensitive tasks (force-T1), offline mode, and all confidence
  >= 80 work (router order is T1-first). Quality: 0.70/1.0 — fine for simple
  transforms, weak on complex reasoning.
- T2: FREE CLOUD — the default cloud tier for confidence 60–79 (and non-trivial
  swarm work). Zero budget: NVIDIA NIM (~40 RPM shared [unverified], free-credit
  models), OpenRouter `:free` only (50 RPM / 50 RPD, no top-up — hard daily
  ceiling), Nous Portal (50 RPM burst / 500K TPM, OAuth ~1h [unverified]).
  Default orchestrator: `nvidia/nemotron-3-super-120b-a12b` (NVIDIA NIM).
- T3: DISABLED. No paid tiers, no top-ups, ever (SuperGrok/Grok hard-locked).
  Security/change tasks that would have gone T3 now ASK + escalate flag.
- ASK: Ambiguous tasks (3+ categories) or 60–79% band when `ask_human_band=True`,
  or below 60% with T3 disabled ("no $0 tier cleared"). Pause and ask user.

### Orchestrator model selection (free models only)

- DEFAULT: `nvidia/nemotron-3-super-120b-a12b` — NVIDIA NIM, 262K context,
  ~0.2 credits/req [unverified]. Most orchestration.
- ESCALATION: `nvidia/nemotron-3-ultra-550b-a55b` — NVIDIA NIM, 1M context,
  ~0.5 credits/req [unverified]; OpenRouter fallback must be the `:free` variant.
  Triggered when swarm score >= 15 (`orchestrator_escalation_threshold`).
- HIGH-FREQUENCY: `nvidia/nemotron-3.5-lightning-30b-a3b` — NVIDIA NIM, 1M
  context, cheap credits. Fast dispatch of many simple workers.
- Workers: `nvidia/nemotron-nano-3-30b-a3b` (text-only — NO tool calling,
  verified 404 on tool_calls), `mistralai/codestral-22b-instruct-v0.1` (code),
  `deepseek-ai/deepseek-v4-flash` (reasoning) — all NVIDIA NIM; Nous free models
  (`step-5-preview:free`, `ling-3.1-flash`, `stealth/missingno`) for burst.
- Local: `phi-4-mini-instruct` (T1, `:8081`) for force-T1 privacy tasks.

Never: `kimi-k2.6`, Ultra models, `nemotron-3-ultra-550b-a55b` on OpenRouter
without `:free` (paid), SuperGrok/grok-2 (AGENTS.md).

### Zero-tier mode (ENABLED, locked)

`zero_tier_mode=True`, `t3_hard_disabled=True`, `free_tier_priority=False`.
T1-first per router order: confidence >= 80 stays on T1 local. T2 free cloud
covers 60–79 (ASK if `ask_human_band`). Below 60 → ASK (T3 disabled — no
$0 tier cleared). Privacy/offline keywords always short-circuit to T1.

### Recording outcomes

After the worker completes:

    from token_optimiser.monica_integration import record_outcome
    record_outcome(decision["task_id"], {
        "outcome_type": "worked",
        "details": "Worker completed successfully"
    })

### Rules

1. ALWAYS call optimise() before dispatching any worker — no exceptions.
2. If tier is "ASK", do NOT dispatch. Ask the user first.
3. If the optimiser is disabled, route to T2 and note it.
4. Record outcomes after every dispatched task.
5. The routing decision is visible to the worker — share it so the worker can adjust
   (T1: be concise. T2: use full context, the model is smart. T3: thorough, critical).
"""
