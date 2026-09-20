# neo-light

**A lightweight agent environment with token-optimiser routing and swarm-first multi-agent capabilities.**

neo-light runs agent workloads across a 3-tier model hierarchy — local GPU, free cloud, then paid — so you can keep your heavy models for the hard jobs and burn tokens cheaply on everything else.

## Features

- **3-tier budget routing** — T1 local (llama.cpp on your own GPU), T2 free cloud (40+ free models via OpenRouter and NVIDIA NIM), T3 paid (escalation only).
- **Swarm-first delegation** — any non-trivial task (3+ files, 2+ modules, 5+ tool calls) is automatically decomposed into parallel worker agents with paired reviewers.
- **Local + free priority** — T1 Vulkan 3B and T2 free cloud are tried *before* paid APIs. SuperGrok and other premium models are reserved for the heavyweight agent (James).
- **Token Optimiser (TOS)** — every call is scored for cheapest viable route, with per-category confidence caps (e.g. security tasks capped at 55%, escalating to human review).
- **Hermes TUI** — launches as a Matrix-themed terminal UI with isolated `HERMES_HOME`.
- **Learning log** — routing decisions are logged to `token_optimiser/learning_log.jsonl` for calibration over time.

## Quick Start

```bash
# Clone
git clone https://github.com/WarPuppy/neo-light.git
cd neo-light

# Install dependencies (Python 3.10+)
pip install pyyaml

# Launch
./bin/neo
```

The `neo` script:

1. Sets up an isolated `.hermes-home` inside the repo.
2. Loads API keys for OpenRouter and NVIDIA NIM from `~/.config/openrouter/api_key` and `~/Work/Projects/nvapi.key`.
3. Pins local llama-server at `http://192.168.1.10:8081` (T1) as primary.
4. Starts Hermes in TUI mode inside `work/`.

## Configuration

### Routing tiers

| Tier | Provider | Models | Use case |
|------|----------|--------|----------|
| **T1** | Local llama-server (`:8081`) | Phi-3.5-mini, Qwen2.5-Coder-3B | Code, reasoning, tool calling on your own GPU |
| **T2** | OpenRouter, NVIDIA NIM | DeepSeek V4 Flash, Nemotron, Poolside, 40+ free models | General tasks, research, documentation |
| **T3** | SuperGrok | grok-2-1212 | Escalation only (disabled by default) |

Edit `token_optimiser/config.py` to adjust:

- `tier_backends` — change T1 URL/model, add/remove T2 gateways.
- `free_tier_priority` — when `true`, T2 free models are tried *before* T1 local if quality estimates are higher.
- `security_confidence_cap` — default 55. Security tasks below this threshold escalate to human review.
- `category_free_model_preference` — per-category free model selection (code_gen, research, testing, etc.).

### Switching models at runtime

From inside the Hermes TUI:

```
/model vulkan-3b
/model ollama-7b
/model minimax-m3
/model openrouter-free
```

### Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | T2 OpenRouter access |
| `NVIDIA_API_KEY` / `NVAPI_KEY` | T2 NVIDIA NIM access |
| `LM_BASE_URL` | Override T1 endpoint (default `http://192.168.1.10:8081/v1`) |
| `LM_API_KEY` | T1 API key (default `lm-studio`) |

Keys are auto-loaded by `bin/neo` from `~/.config/openrouter/api_key` and `~/Work/Projects/nvapi.key` if present.

## Swarm delegation

neo-light uses a **swarm-first** pattern for multi-file, multi-module work:

1. **Orchestrator** decomposes the task into independent sub-tasks.
2. **Workers** execute in parallel (one per sub-task).
3. **Reviewers** validate each worker's output independently.
4. Work is only marked done when all reviewers issue a clean pass (zero Critical/High findings).

This is enforced for any task touching more than 3 files, more than 2 modules, or requiring more than 5 sequential tool calls.

## Project structure

```
neo-light/
├── bin/
│   └── neo              # Launch script (sets HERMES_HOME, pins T1, starts TUI)
├── token_optimiser/
│   ├── config.py        # Tier backends, model lists, confidence caps
│   ├── router.py        # Routing logic
│   ├── SKILL.md         # Token Optimiser skill definition
│   └── learning_log.jsonl
├── work/                # Default working directory for the TUI
└── README.md
```

## License

MIT License. See [LICENSE](LICENSE) for details.
