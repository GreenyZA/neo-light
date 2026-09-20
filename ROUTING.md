# Routing (Light Engine)

James TOS is the shop-floor router. Do not fork it here.

Hermes **64k floor is 16384** in this install (`agent/model_metadata.py`). This box cannot host 64k KV. Brain: `llama3.1-16k`. GPU 3B fallback. A Hermes upgrade resets the floor.

Launch is still `neo`. Close the old TUI first.

Vulkan 3B train ctx: 32768. Hermes usable local: 16k 8B. Do not load llama3.1-64k.

Callers (optional, from a shell, not SuperGrok):

```
bash ~/.grok/skills/token-optimiser/callers/llamacpp-curl.sh "qwen2.5-coder-3b-instruct" "PROMPT" 256
```
