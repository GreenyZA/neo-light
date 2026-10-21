"""
Token Optimiser — Configuration

UPDATED 2026-10-05 — swarm routing strategy based on live throughput analysis:
- NVIDIA NIM is now PRIMARY (weight 2.0): 40 RPM, no daily reset, credit-based.
  Only provider that sustains full-speed swarming for 2+ hours without hitting
  a wall. 80 models, small models cost ~0.05 credits/req.
- OpenRouter is SECONDARY (weight 1.5): 20 RPM, 1,000 RPD with $10 lifetime
  top-up. Best model quality (Nemotron 3 Ultra 550B at 1M context) but half
  the RPM of NVIDIA.
- Nous Portal is FALLBACK (weight 0.5): 50 RPM burst, 500K TPM, but only 8
  free models and OAuth expires hourly. Good for simple/fast workers.
- Combined: ~110 RPM, ~1,050+ RPD — enough for serious swarming.
- Free model lists expanded from live scan (16 OR + 80 NV + 8 Nous free models).
- Category preferences updated: NVIDIA NIM models as primary per category.

UPDATED 2026-10-04 (CHG-2026-030) — corrected against the wire, not from memory:
- T1 endpoint: 192.168.1.10:8081 (llama-server, Vulkan, RX 480)
- T1 model: phi-4-mini-instruct Q4_K_M, 3.84B, n_ctx 131072 (WAS: Phi-3.5-mini
  Q5_K_M / 4096 ctx / 3.0GB — a model that is not loaded. The server accepts any
  model name and silently substitutes, so the wrong name never errored.)
- T1 fallback: NONE. qwen2.5-coder-3b-instruct is not on this box.
- T1b: DISABLED. Both 192.168.1.8:8082 and 192.168.1.102:8082 return HTTP 000;
  nothing on the LAN serves 8082. The privacy short-circuit sends its
  strictest tasks here, so a dead T1b silently strands them.
- Credentials: token_optimiser never loaded ~/.hermes/.env, so from inside this
  process every free tier looked unavailable and decisions escalated to T3.
  Fixed in credentials.py (auto-loads on import; env always wins).
- Calibration: the writer stores outcome={"outcome": "worked"}; the reader
  looked for "outcome_type". Every category took a permanent -10 penalty.
  Fixed in monica_integration.py.
- T3 remains opt-in (enabled: False) per Johann's standing "No SuperGrok".

UPDATED 2026-09-19:
|- T2 expanded: 40+ free models (NVIDIA Nemotron, DeepSeek V4 Flash, Poolside, etc.)
|- New: Free tier priority mode — T2 free cloud before T1 when quality is better
|- New: NVIDIA NIM integration (integrate.api.nvidia.com/v1)
|- New: DeepSeek V4 Flash free via OpenRouter AND NVIDIA NIM
|- T1b was: secondary local tier on Lenovo M710Q for larger CPU models when
  privacy requires local + more knowledge than T1's 3B.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenOptimiserConfig:
    enabled: bool = True
    learning_log_path: str = "token_optimiser/learning_log.jsonl"
    confidence_calibration: dict = field(default_factory=dict)
    priority_budget: int = 1000
    max_t1_daily_savings: int = 5000
    recent_decisions: list = field(default_factory=list)
    learning_log: list = field(default_factory=list)

    # Free tier priority: T2 free cloud tried BEFORE T1 local.
    # ZERO-TIER MODE ($0 only): router order is T1 local -> T2 free cloud.
    # Forced False so high-confidence (>=80) work stays on T1 local per router order.
    free_tier_priority: bool = False

    # Category → preferred free model mapping ($0 only).
    # Every entry must be free: NVIDIA NIM free-credit models, OpenRouter `:free`
    # models only (never bare paid IDs), Nous Portal free models, or local-only.
    # NVIDIA NIM credit costs are [unverified]; match model to task class to conserve.
    category_free_model_preference: dict = field(default_factory=lambda: {
        "code_gen_small": "nvidia/nemotron-3-super-120b-a12b",
        "code_gen_medium": "nvidia/nemotron-3-super-120b-a12b",
        "code_gen_large": "nvidia/nemotron-3-ultra-550b-a55b",
        "documentation": "nvidia/nemotron-3-super-120b-a12b",
        "research": "deepseek-ai/deepseek-v4-flash",
        "testing": "nvidia/nemotron-3-super-120b-a12b",
        "infrastructure": "nvidia/nemotron-3-super-120b-a12b",
        "simple_transform": "phi-4-mini-instruct",
        "architecture": "nvidia/nemotron-3-super-120b-a12b",
        "privacy": "local-only",
    })

    # Orchestrator model configuration
    # Default: nemotron-3-super-120b-a12b — best daily driver (40 RPM, 262K ctx, ~0.2 credits/req)
    # Escalation: nemotron-3-ultra-550b-a55b — complex multi-phase tasks (1M ctx, ~0.5 credits/req)
    # High-frequency: nemotron-3.5-lightning-30b-a3b — fast dispatch, 1M ctx, cheap credits
    # stealth/missingno removed: not in Nous Portal live /v1/models catalog (0 stealth models, verified this session)
    orchestrator_default_model: str = "nvidia/nemotron-3-super-120b-a12b"
    orchestrator_escalation_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    orchestrator_high_frequency_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    orchestrator_escalation_threshold: int = 15  # swarm score >= 15 → escalate to Ultra

    tier_backends: dict = field(default_factory=lambda: {
        "T1": {
            # VERIFIED against the wire 2026-10-04. This box IS 192.168.1.10;
            # the running server's own cmdline is:
            #   llama-server -m .../Phi-4-mini-instruct-Q4_K_M.gguf -dev Vulkan0
            #     -ngl 99 -c 131072 -ctk q4_0 --port 8081 --alias phi-4-mini-instruct
            # /v1/models reports id=phi-4-mini-instruct, n_ctx=131072,
            # n_params=3.84B. The old values (Phi-3.5-mini-Q5_K_M, 4096 ctx,
            # 3.0GB) described a model that is not loaded. CRITICAL: this server
            # accepts ANY model name and silently substitutes what it has, so a
            # wrong name here never errors — it just misreports what it serves.
            "url": "http://192.168.1.10:8081",
            "model": "phi-4-mini-instruct",
            # No local fallback exists: qwen2.5-coder-3b-instruct is not on this
            # box. Falling back to it can only produce a false claim. Escalate
            # to T2 free instead, which is a real, working tier.
            "fallback_model": None,
            "max_prompt_tokens": 32768,
            "enabled": True,
            "tweak_notes": "Local llama-server on RX 480 (Vulkan). Phi-4-mini-instruct Q4_K_M, 3.84B, n_ctx 131072, q4_0 KV. ~40-90 tok/s measured. NOTE: 3B-class -- route substantive work to T2 free.",
            "quality_rating": 0.70,
            "vram_usage_gb": 2.48,
            "context_tokens": 131072,
            "alternative_models": {
                "code": "Qwen2.5-Coder-7B-Instruct-IQ3_S (3.0GB, best code)",
                "reasoning": "phi-4-mini-instruct Q4_K_M (2.5GB, best local reasoning)",
                "agentic": "Qwen3.5-4B-Q4_K_M (2.4GB, tool calling)",
                "fast": "Llama-3.2-3B-Instruct-Q4_K_M (2.0GB, fastest)",
            },
        },
        "T1b": {
            # DISABLED 2026-10-04. Both candidate hosts are dead:
            #   192.168.1.8:8082   -> HTTP 000 (connection refused)
            #   192.168.1.102:8082 -> HTTP 000 (connection refused)
            # Nothing on this LAN serves 8082 at all. An uncommitted edit had
            # moved this from .102 to .8, which made it unreachable rather than
            # fixing it. The privacy short-circuit routes its STRICTEST tasks
            # here, so a dead T1b means "must stay local, offline, air-gapped"
            # work has nowhere to go. Left enabled, it advertised a capability
            # that does not exist. Disabled until a host actually runs it.
            "url": None,
            "model": "qwen2.5-7b-instruct-1m",
            "fallback_model": None,
            "max_prompt_tokens": 32768,
            "enabled": False,
            "tweak_notes": "DISABLED: no host on the LAN serves :8082. Was Lenovo M710Q CPU llama-server. Re-enable only after a live /v1/models probe returns 200.",
            "quality_rating": 0.0,
            "vram_usage_gb": 0,
            "context_tokens": 0,
            "alternative_models": {
                "code": "qwen2.5-7b-instruct-1m (CPU, 7B, larger context)",
                "chat": "qwen2.5-7b-instruct-1m (CPU, more knowledge than T1 3B)",
                "reasoning": "qwen2.5-7b-instruct-1m (CPU, 7B for complex analysis)",
            },
        },
        "T2": {
            "gateways": [
                {
                    "name": "NVIDIA_NIM",
                    "url": "https://integrate.api.nvidia.com/v1",
                    "type": "nvidia_nim",
                    "api_key_env": "NVIDIA_API_KEY",
                    "weight": 2.0,
                    "enabled": True,
                },
                {
                    "name": "OpenRouter",
                    "url": "https://openrouter.ai/api/v1",
                    "type": "openrouter",
                    "api_key_env": "OPENROUTER_API_KEY",
                    "weight": 1.5,
                    "enabled": True,
                },
                {
                    "name": "OmniRoute",
                    "url": "http://127.0.0.1:20128/v1",
                    "type": "omniroute",
                    "weight": 1.0,
                    "enabled": True,
                },
                {
                    "name": "NOUS",
                    "url": "https://inference-api.nousresearch.com/v1",
                    "type": "nous",
                    "api_key_env": "NOUS_API_KEY",
                    "weight": 0.5,
                    "enabled": True,
                },
            ],
            "free_models": [
                # OpenRouter :free models (16)
                "nvidia/nemotron-3-ultra-550b-a55b:free",
                "nvidia/nemotron-3.5-lightning:free",
                "nvidia/nemotron-3-super-120b-a12b:free",
                "google/gemma-4-31b-it:free",
                "google/gemma-4-26b-a4b-it:free",
                "cohere/north-mini-code:free",
                "thinkingmachines/inkling:free",
                "thinkingmachines/inkling-small:free",
                "dots-studio/dots-3-note-preview:free",
                "poolside/laguna-s-2.1:free",
                "poolside/laguna-xs-2.1:free",
                "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                "apodex/apodex-1.1-mini:free",
                "liquid/lfm-2.5-2.6b:free",
                "inclusionai/ling-3.0-flash-sante:free",
                "openrouter/free",
            ],
            "nvidia_free_models": [
                # NVIDIA NIM free models (80, credit-based)
                "nvidia/nemotron-4-340b-instruct",
                "nvidia/nemotron-3-ultra-550b-a55b",
                "nvidia/nemotron-3-super-120b-a12b",
                "nvidia/nemotron-3.5-lightning-30b-a3b",
                "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                "nvidia/nemotron-nano-3-30b-a3b",
                "nvidia/llama-3.1-nemotron-ultra-253b-v1",
                "nvidia/llama-3.1-nemotron-70b-instruct",
                "nvidia/llama-3.1-nemotron-51b-instruct",
                "nvidia/nemotron-3.5-content-safety",
                "nvidia/nemotron-3-embed-1b",
                "nvidia/embed-qa-4",
                "nvidia/nv-embedqa-mistral-7b-v2",
                "nvidia/llama-nemotron-embed-vl-1b-v2",
                "nvidia/llama-3.2-nv-embedqa-1b-v1",
                "nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1",
                "nvidia/cosmos-reason2-8b",
                "nvidia/llama-3.1-nemoguard-8b-content-safety",
                "nvidia/llama-3.1-nemoguard-8b-topic-control",
                "nvidia/llama-3.1-nemotron-safety-guard-8b-v3",
                "nvidia/mistral-nemo-minitron-8b-8k-instruct",
                "nvidia/ai-synthetic-video-detector",
                "nvidia/ising-calibration-1.5-31b",
                "nvidia/neva-22b",
                "nvidia/nvclip",
                "nvidia/vila",
                "nvidia/riva-translate-4b-instruct",
                "nvidia/riva-translate-4b-instruct-v2",
                "meta/llama-3.3-70b-instruct",
                "meta/llama-3.2-90b-vision-instruct",
                "meta/llama-3.2-11b-vision-instruct",
                "meta/llama-guard-4-12b",
                "meta/codellama-70b",
                "meta/llama2-70b",
                "meta/muse-glimmer-30b",
                "meta/muse-spark-1.3",
                "meta/muse-spark-1.2",
                "meta/muse-spark-1.1",
                "deepseek-ai/deepseek-v4.1-flash",
                "deepseek-ai/deepseek-v4-flash",
                "deepseek-ai/deepseek-coder-6.7b-instruct",
                "mistralai/mistral-large",
                "mistralai/mistral-large-2-instruct",
                "mistralai/mistral-7b-instruct-v0.3",
                "mistralai/codestral-22b-instruct-v0.1",
                "mistralai/mixtral-8x22b-v0.1",
                "mistralai/mistral-nemo",
                "mistralai/mistral-saba",
                "mistralai/ministral-14b-2512",
                "mistralai/ministral-8b-2512",
                "mistralai/ministral-3b-2512",
                "mistralai/mistral-large-2512",
                "mistralai/mistral-small-3.2-24b-instruct",
                "mistralai/mistral-small-3.1-24b-instruct",
                "mistralai/mistral-medium-3.5",
                "mistralai/mistral-medium-3.1",
                "mistralai/mistral-medium-3",
                "mistralai/devstral-2512",
                "mistralai/mistral-embed-2312",
                "mistralai/codestral-embed-2505",
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "openai/gpt-oss-safeguard-20b",
                "google/gemma-4-31b-it",
                "google/gemma-3-12b-it",
                "google/gemma-3-4b-it",
                "google/gemma-2b",
                "google/codegemma-1.1-7b",
                "google/codegemma-7b",
                "google/recurrentgemma-2b",
                "google/deplot",
                "google/diffusiongemma-26b-a4b-it",
                "moonshotai/kimi-k2.6",
                "moonshotai/kimi-k3",
                "moonshotai/kimi-k2.5",
                "moonshotai/kimi-k2",
                "moonshotai/kimi-k2-thinking",
                "moonshotai/kimi-k2-0905",
                "moonshotai/kimi-k2.7-code",
                "z-ai/glm-5.3",
                "z-ai/glm-5.3-flash",
                "z-ai/glm-5.2",
                "z-ai/glm-5.1",
                "z-ai/glm-5",
                "z-ai/glm-4.7",
                "z-ai/glm-4.7-flash",
                "z-ai/glm-4.6",
                "z-ai/glm-4.6v",
                "z-ai/glm-4.5",
                "z-ai/glm-4.5v",
                "z-ai/glm-5-turbo",
                "z-ai/glm-5v-turbo",
                "ibm/granite-3.0-3b-a800m-instruct",
                "ibm/granite-3.0-8b-instruct",
                "ibm/granite-34b-code-instruct",
                "ibm/granite-8b-code-instruct",
                "microsoft/phi-3-vision-128k-instruct",
                "microsoft/phi-3.5-moe-instruct",
                "microsoft/kosmos-2",
                "qwen/qwen3-coder",
                "qwen/qwen3-coder-next",
                "qwen/qwen3-coder-flash",
                "qwen/qwen3-coder-plus",
                "qwen/qwen3-coder-30b-a3b-instruct",
                "qwen/qwen3-30b-a3b",
                "qwen/qwen3-30b-a3b-thinking-2507",
                "qwen/qwen3-14b",
                "qwen/qwen3-8b",
                "qwen/qwen3-32b",
                "qwen/qwen3-235b-a22b",
                "qwen/qwen3-235b-a22b-thinking-2507",
                "qwen/qwen3-max",
                "qwen/qwen3-max-thinking",
                "qwen/qwen3.5-35b-a3b",
                "qwen/qwen3.5-27b",
                "qwen/qwen3.5-122b-a10b",
                "qwen/qwen3.5-9b",
                "qwen/qwen3.5-flash-02-23",
                "qwen/qwen3.5-plus-20260420",
                "qwen/qwen3.5-plus-02-15",
                "qwen/qwen3.5-397b-a17b",
                "qwen/qwen3.6-flash",
                "qwen/qwen3.6-35b-a3b",
                "qwen/qwen3.6-max-preview",
                "qwen/qwen3.6-27b",
                "qwen/qwen3.6-plus",
                "qwen/qwen3.7-flash",
                "qwen/qwen3.7-plus",
                "qwen/qwen3.7-max",
                "qwen/qwen3.8-27b",
                "qwen/qwen3.8-flash",
                "qwen/qwen3.8-2.4t-a95b",
                "qwen/qwen3.8-max-0902",
                "qwen/qwen3.8-omni-flash",
                "qwen/qwen3-vl-32b-instruct",
                "qwen/qwen3-vl-8b-thinking",
                "qwen/qwen3-vl-8b-instruct",
                "qwen/qwen3-vl-30b-a3b-thinking",
                "qwen/qwen3-vl-30b-a3b-instruct",
                "qwen/qwen3-vl-235b-a22b-thinking",
                "qwen/qwen3-vl-235b-a22b-instruct",
                "qwen/qwen3-embedding-8b",
                "qwen/qwen3-embedding-4b",
                "qwen/qwen-2.5-7b-instruct",
                "qwen/qwen-2.5-72b-instruct",
                "qwen/qwen-plus",
                "qwen/qwen-plus-2025-07-28",
                "poolside/laguna-xs-2.1",
                "writer/palmyra-creative-122b",
                "writer/palmyra-fin-70b-32k",
                "writer/palmyra-med-70b",
                "writer/palmyra-med-70b-32k",
                "snowflake/arctic-embed-l",
                "adept/fuyu-8b",
                "ai21labs/jamba-1.5-large-instruct",
                "aisingapore/sea-lion-7b-instruct",
                "bigcode/starcoder2-15b",
                "databricks/dbrx-instruct",
                "01-ai/yi-large",
                "nv-mistralai/mistral-nemo-12b-instruct",
                "zyphra/zamba2-7b-instruct",
                "minimaxai/minimax-m3",
                "minimaxai/minimax-m3.1-flash",
                "upstage/solar-mini4",
                "upstage/solar-pro4",
                "upstage/solar-pro3",
                "kwaipilot/kat-coder-pro-v2.5",
                "arcee-ai/trinity-large-thinking",
                "rekaai/reka-edge",
                "sakana/fugu-ultra",
                "sakana/fugu-ultra-v2",
                "sakana/fugu-max",
                "perplexity/pplx-embed-v1-4b",
                "perplexity/pplx-embed-v1-0.6b",
                "amazon/nova-2-lite-v1",
                "amazon/nova-lite-v1",
                "amazon/nova-micro-v1",
                "amazon/nova-pro-v1",
                "amazon/nova-premier-v1",
                "thenlper/gte-base",
                "thenlper/gte-large",
                "intfloat/e5-large-v2",
                "intfloat/e5-base-v2",
                "intfloat/multilingual-e5-large",
                "sentence-transformers/paraphrase-minilm-l6-v2",
                "sentence-transformers/all-minilm-l12-v2",
                "baai/bge-base-en-v1.5",
                "sentence-transformers/multi-qa-mpnet-base-dot-v1",
                "baai/bge-large-en-v1.5",
                "baai/bge-m3",
                "sentence-transformers/all-mpnet-base-v2",
                "sentence-transformers/all-minilm-l6-v2",
                "openai/text-embedding-ada-002",
                "openai/text-embedding-3-large",
                "openai/text-embedding-3-small",
                "mistralai/voxtral-small-24b-2507",
                "google/gemini-embedding-2",
                "google/gemini-embedding-001",
                "google/gemini-embedding-2-preview",
            ],
            "nous_free_models": [
                "meituan/longcat-2.5-preview:free",
                "meituan/longcat-2.0:free",
                "inclusionai/ling-3.0-flash-fin:free",
                "inclusionai/ling-3.0-flash-sante:free",
                "stepfun/step-3.7-flash:free",
                "upstage/solar-mini4:free",
                "poolside/laguna-s-2.1:free",
                "poolside/laguna-xs-2.1:free",
                # Live Nous free tier additions (scan 2026-10-11; OK to route here):
                "stepfun/step-5-preview:free",     # 27B/600B MoE, 1M ctx, multimodal, mandatory reasoning, tools
                "inclusionai/ling-3.1-flash",      # text, 262K ctx, tools, zero-cost (no :free suffix on Nous)
                "stealth/missingno",               # Nous default free stealth model, 262K ctx, tools
            ],
            "max_prompt_tokens": 32000,
            "quality_rating": 0.9,
        },
        "T3": {
            "providers": [
                {
                    "name": "Grok (SuperGrok)",
                    "url": "https://grok.api.x.ai/v1",
                    "type": "grok",
                    "api_key_env": "GROK_API_KEY",
                    "model": "grok-2-1212",
                    "max_prompt_tokens": 32000,
                    "enabled": False,
                    "tweak_notes": "T3 HARD-LOCKED ($0 zero-tier mode): no paid tiers, no top-ups, ever. "
                                   "Dashboard has no T3 enable toggle; enabling is logged and refused.",
                },
            ],
            "default_provider": "Grok (SuperGrok)",
            "t3_locked": True,
        },
    })

    security_confidence_cap: int = 55
    category_confidence_caps: dict = field(default_factory=lambda: {
        "security": 55,
        "architecture": 65,
        "privacy": 55,
        "monica_mail_triage_private": 60,
        "monica_customer_records_local": 55,
        "monica_local_redaction": 60,
        "monica_sb_preprocess": 65,
        "monica_audio_transcript_redaction": 60,
        "monica_attachment_sanitization": 60,
        "monica_log_scrub": 60,
        "monica_contact_calendar_redaction": 55,
        "monica_export_anonymization": 60,
        "monica_reidentification_guard": 55,
        "monica_local_indexing": 65,
        "monica_health_status": 85,
        "monica_portal_summary": 80,
        "monica_ops_log_prep": 80,
        "monica_time_prep": 75,
        "monica_followup_list": 80,
    })

    # Privacy/offline keywords that ALWAYS force T1 routing regardless of free_tier_priority.
    # When privacy_force_t1 is True and any of these keywords appear in the task,
    # the router short-circuits to T1 (local, air-gapped, never leaves the machine).
    privacy_offline_keywords: list = field(default_factory=lambda: [
        "offline", "airgap", "air-gapped", "air gapped", "no internet",
        "local only", "on-premise", "on premise", "must stay local",
        "data residency", "sovereign", "leave this machine", "never leave",
        "stay on device", "no cloud", "without internet",
    ])

    privacy_force_t1: bool = True

    # Keywords that indicate the user needs a larger model than T1's 3B.
    # When combined with privacy/offline keywords (force T1), routes to T1b (Lenovo 7B CPU) instead.
    t1b_keywords: list = field(default_factory=lambda: [
        "deep analysis", "7b", "larger model", "more knowledge",
        "longer context", "complex analysis", "deep reasoning", "detailed output",
    ])
    threshold_t1_min: int = 80
    threshold_t2_min: int = 60
    threshold_t3_always_below: int = 60
    hybrid_band_enabled: bool = True
    ask_human_band: bool = False
    ambiguous_task_asks_human: bool = True
    scope_word_thresholds: dict = field(default_factory=lambda: {"small": 30, "medium": 100})
    scope_prefix_pattern: str = r"\[(?:scope|size|scope_size)?[:\s]*(\w+)\]"
    scope_prefix_values: dict = field(default_factory=lambda: {
        "small": "small", "s": "small", "sm": "small",
        "medium": "medium", "m": "medium", "med": "medium",
        "large": "large", "l": "large", "lg": "large",
    })

    # Learning log calibration
    calibration_enabled: bool = True
    calibration_min_samples: int = 5

    # Parallelization scoring
    parallelize_threshold: float = 0.7

    # ── Zero-tier mode ($0 only) ──────────────────────────────────────────
    # T3 is hard-disabled: no paid tiers, no top-ups, ever. The dashboard has
    # no T3 enable toggle; any attempt to enable T3 is logged and refused.
    zero_tier_mode: bool = True
    t3_hard_disabled: bool = True

    # Rate-limit ceilings for $0 T2 providers (all [unverified] until live-probed).
    # Used by the fan-out guard: N workers x M calls must fit inside RPM before
    # dispatch; OpenRouter :free RPD is a hard daily ceiling.
    provider_rate_ceilings: dict = field(default_factory=lambda: {
        "NVIDIA_NIM": {"rpm": 40, "rpd": None,
                       "notes": "shared credit pool [unverified]; ~0.05–0.5 cred/req by model [unverified]"},
        "OpenRouter": {"rpm": 50, "rpd": 50,
                       "notes": ":free, no top-up — hard daily ceiling [unverified]"},
        "Nous Portal": {"rpm": 50, "tpm": 500000,
                        "notes": "OAuth expires ~hourly; refresh required [unverified]"},
    })

    # Orchestrator-aware routing
    orchestrator_routing: bool = True
    min_review_tier: str = "T2"
    min_orchestrator_tier: str = "T2"
    enforce_review: bool = True

    # BOA/ITIL governance mode for monica_integration.optimise
    # "off": never use BOA, pure router (backward compat, no overhead)
    # "auto": use lightweight BOA (classify_itil + validate_swarm_plan) for non-trivial/ops tasks
    # "force_boa": always attempt lightweight BOA governance for binding tier + swarm
    governance_mode: str = "auto"

    def _ts(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "threshold_t1_min": self.threshold_t1_min,
            "threshold_t2_min": self.threshold_t2_min,
            "threshold_t3_always_below": self.threshold_t3_always_below,
            "hybrid_band_enabled": self.hybrid_band_enabled,
            "ask_human_band": self.ask_human_band,
            "ambiguous_task_asks_human": self.ambiguous_task_asks_human,
            "security_confidence_cap": self.security_confidence_cap,
            "category_confidence_caps": self.category_confidence_caps or {},
            "privacy_offline_keywords": self.privacy_offline_keywords,
            "privacy_force_t1": self.privacy_force_t1,
            "scope_word_thresholds": self.scope_word_thresholds,
            "scope_prefix_pattern": self.scope_prefix_pattern,
            "scope_prefix_values": self.scope_prefix_values,
            "confidence_calibration": self.confidence_calibration,
            "tier_backends": self.tier_backends,
            "priority_budget": self.priority_budget,
            "max_t1_daily_savings": self.max_t1_daily_savings,
            "recent_decisions": self.recent_decisions,
            "learning_log": self.learning_log,
            "free_tier_priority": self.free_tier_priority,
            "category_free_model_preference": self.category_free_model_preference,
            "parallelize_threshold": self.parallelize_threshold,
            "orchestrator_routing": self.orchestrator_routing,
            "min_review_tier": self.min_review_tier,
            "min_orchestrator_tier": self.min_orchestrator_tier,
            "enforce_review": self.enforce_review,
            "governance_mode": self.governance_mode,
            "t1b_keywords": self.t1b_keywords,
            "orchestrator_default_model": self.orchestrator_default_model,
            "orchestrator_escalation_model": self.orchestrator_escalation_model,
            "orchestrator_high_frequency_model": self.orchestrator_high_frequency_model,
            "orchestrator_escalation_threshold": self.orchestrator_escalation_threshold,
            "zero_tier_mode": self.zero_tier_mode,
            "t3_hard_disabled": self.t3_hard_disabled,
            "provider_rate_ceilings": self.provider_rate_ceilings,
        }


config = TokenOptimiserConfig()


def _ts() -> str:
    return config._ts()


def to_dict() -> dict:
    return config.to_dict()


def set_enabled(enabled: bool):
    config.enabled = enabled


def is_enabled() -> bool:
    return config.enabled


def update_calibration(category: str, delta: int):
    if category not in config.confidence_calibration:
        config.confidence_calibration[category] = 0
    config.confidence_calibration[category] += delta


def reset_calibration():
    config.confidence_calibration.clear()
