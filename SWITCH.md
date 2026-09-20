# Switch

**Default is James.** Light Engine is opt-in when you want a cheap TUI to save SuperGrok. Closing Light Engine returns the bar to James. Login resets leftover Local mode. It does not open a TUI.

| Environment | How | Pays |
|-------------|-----|------|
| **James** (default) | `james` or `grok` with `~/.grok`. Omarchy agent key. Bar **Grok**. | SuperGrok |
| **Light Engine** (on demand) | `light-engine`, bar **Local**, `clarity-engine local` | Grok TUI on Vulkan 3B |
| **Neo** | `neo` | Hermes, Matrix skin, MiniMax free. Cwd `work/` |
| **Multi-Agent** | `multi-agent` | Swarm. Architect approves. Same Matrix skin. |

`light-engine` sets `GROK_HOME` to this repo’s `.grok-home` and starts in this directory. James’s skills and SuperGrok default stay untouched.

Inside Light Engine:

```
/model vulkan-3b
/model ollama-7b
/model minimax-m3
/model openrouter-free
```

Default is `vulkan-3b`. If the 3B chokes on tools, `/model minimax-m3` (still free). Do not `/model` a Grok id.

Bar: **Grok / Local** is the engine switch, not only a view.

| Chip | Opens | Pays |
|------|-------|------|
| **Grok** | James TUI (`james`) | SuperGrok |
| **Local** | Light Engine TUI (`light-engine`) | Vulkan 3B, then free |

Same commands: `clarity-engine grok` · `clarity-engine local`. This SuperGrok session cannot become Vulkan. Close it or leave it; Local opens the other TUI.

**Meter dead, stuck in Light Engine:** say **I want james back**, or `/james`, or any terminal `back-to-james`.

The Local panel also shows live Vulkan + machine specs.
