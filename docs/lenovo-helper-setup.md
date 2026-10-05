# Lenovo M710Q Helper Setup

**Date:** 2026-09-26  
**Status:** ✅ Active and verified  
**BoA Sign-off:** Pending

## Overview

The Lenovo M710Q (192.168.1.8, SSH alias `anvil`) has been configured as a dual-purpose helper machine for the Acer workstation (192.168.1.10):

1. **T1b — Local CPU Inference**: llama.cpp serving Qwen2.5-7B on CPU, accessible at `http://192.168.1.8:8082`
2. **Build Slave**: Docker buildx + gcc compilation offloading from the Acer

## Hardware Specifications

| Component | Lenovo M710Q | Acer (Server) |
|-----------|-------------|---------------|
| CPU | i5-7500T (4C/4T, 3.1GHz) | Ryzen 5 1400 (4C/8T) |
| GPU | Intel HD 630 (iGPU only) | RX 480 (8GB VRAM) |
| RAM | 15GB | 15GB |
| OS | Omarchy (Arch-based) | Arch Linux |
| Network | 1 GbE (enp0s31f6) | 1 GbE (wlp3s0f0u4, 2.4GHz WiFi) |

## AI Inference (T1b Tier)

### Components

- **llama.cpp**: Built from source (`ggml-org/llama.cpp`) with `-DGGML_RPC=ON`
- **Model**: Qwen2.5-7B-Instruct-1M-Q4_K_M (4.4GB GGUF)
- **llama-server**: Running on port 8082 directly (no RPC server — simplified)

### How It Works

The llama-server on the Lenovo uses the RPC protocol to offload GPU layers to the Lenovo's CPU. When the Acer's llama.cpp needs to run a model too large for the RX 480's 4GB VRAM, it can chain to the Lenovo's RPC worker to distribute layers across machines.

### Token-Optimiser Integration

The T1b tier is registered in the token-optimiser config and router:

```python
# config.py tier_backends
"T1b": {
    "url": "http://192.168.1.8:8082",
    "model": "qwen2.5-7b-instruct-1m",
    "quality_rating": 0.72,
    "context_tokens": 32768,
    "vram_usage_gb": 0,  # CPU-only
}
```

**Routing logic**: T1b is selected when:
- Task contains privacy/offline keywords (forces local) AND
- Task contains T1b keywords: `deep analysis`, `7b`, `larger model`, `more knowledge`, `longer context`, `complex analysis`, `deep reasoning`, `detailed output`

This means T1b is only used when the user explicitly needs a larger model for a privacy-sensitive task — the default routing still prefers T1 (Acer GPU, ~87 tok/s) for fast local tasks and T2 (free cloud) for everything else.

### API Usage

```bash
# Chat completions (from Acer or any LAN machine)
curl http://192.168.1.8:8082/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b-instruct-1m","messages":[{"role":"user","content":"Hello"}],"max_tokens":16}'

# Health check
curl http://192.168.1.8:8082/health

# OpenAI SDK (from Acer)
python -c "
from openai import OpenAI
client = OpenAI(base_url='http://192.168.1.8:8082/v1', api_key='EMPTY')
print(client.chat.completions.create(
    model='qwen2.5-7b-instruct-1m',
    messages=[{'role': 'user', 'content': 'Hello!'}]
).choices[0].message.content)
"
```

### Systemd Services

The `llama-server-lenovo.service` is managed by systemd on the Lenovo for persistence across reboots. The `llama-rpc-server.service` has been removed (see "Architecture Note" below).

```bash
# llama-server (serves Qwen2.5-7B on :8082)
sudo systemctl status llama-server-lenovo.service
```

Service file: `/etc/systemd/system/llama-server-lenovo.service`

### Architecture Note

The initial setup included a `ggml-rpc-server` on port 50052 with `--rpc` layer offloading.
This was simplified because both the RPC server and llama-server were on the same machine —
offloading CPU layers to another CPU process on the same box provides no benefit. The RPC
approach is designed for GPU→CPU cross-machine offloading (e.g., Acer's Vulkan → Lenovo CPU),
but the Acer runs its own llama-server independently. If cross-machine GPU→CPU offloading is
needed in the future, the RPC server can be re-added with `--rpc 192.168.1.8:50052` on the
Acer side and `--rpc 127.0.0.1:50052` on the Lenovo side, with proper GPU layer detection.

## Build Slave

### Docker Context

A Docker context named `lenovo` is configured on the Acer:

```bash
# List contexts
docker context ls

# Build on Lenovo from Acer
docker --context=lenovo build -t my-app:latest .

# Run on Lenovo from Acer
docker --context=lenovo run --rm my-app:latest
```

### SSH Access

Passwordless SSH from Acer to Lenovo:
```bash
ssh anvil  # Connects to 192.168.1.8
```

### Compilation Offload

Direct gcc/cmake compilation over SSH:
```bash
# Compile on Lenovo from Acer
ssh anvil "gcc -o app app.c"
ssh anvil "cd ~/project && cmake -B build && cmake --build build"
```

### Available Build Tools on Lenovo

- GCC 16.2.1
- CMake 4.4.3
- Git 2.55.0
- Docker 29.7.2 + Buildx 0.36.1

## Performance Notes

| Metric | T1 (Acer GPU) | T1b (Lenovo CPU) |
|--------|----------------|------------------|
| Model | Phi-3.5-mini 3B | Qwen2.5-7B 7B |
| Speed | ~25-35 tok/s | ~5-10 tok/s |
| VRAM | 3.0GB | 0 (system RAM) |
| Context | 4K tokens | 32K tokens |
| Use case | Fast local tasks | Large model, privacy-sensitive |

## Future Improvements

- [ ] Sync model library between Acer and Lenovo (NFS or periodic sync)
- [ ] Set up llama.cpp RPC on the Acer side to offload layers TO the Lenovo when running larger models (re-add RPC server if needed)
- [ ] Add the Lenovo to the token-optimiser dashboard as a visible tier
- [ ] Consider moving the T1 model cache to the Lenovo for shared access
- [ ] Set up firewall rules to restrict port 8082 to LAN subnet only (security)
