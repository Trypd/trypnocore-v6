# WSL-side plumbing (Trypnocore v6)

The fleet runs in WSL. This folder is the WSL half of the harness.

## `hooks/` — Claude Code hook shims (user-level, `~/.claude/hooks/`)

Five shims, all fail-silent (a down memory server never blocks a prompt):

| Shim | Hook | What it does |
|---|---|---|
| `tryp-session-start.sh` | SessionStart | Assembles the full bootstrap (CORE.md header, newest soulbackup, soul.md, bootstrap doc, tasks.md), soulchain rehydrate + drift report, one semantic memory page. Fires on `source=compact` too, so identity reloads after autocompaction. |
| `tryp-prompt-context.sh` | UserPromptSubmit | Per-prompt injection from the agent's own pool + collective pool + skills/rules (strong match) + identity pool (stronger match) + monologue tail. |
| `tryp-stop-seal.sh` | Stop | Seals a soulchain turn ring, epoch-seals identity-doc drift. |
| `tryp-stop-narrate.sh` | Stop | Detached Jaynesian narrator: rewrites the exchange as first-person internal monologue via LFM (OpenRouter free tier), appends to the agent's `monologue.md`, stores a pool atom, extracts durable facts. |
| `tryp-precompact-distill.sh` | PreCompact | Detached: distills the outgoing transcript into pool atoms before compaction, snapshots soul.md → soulbackup{today}.md. |

All five call Windows-side Python helpers in `OmegaPrimeZero/mcp/` via `cmd.exe /c` interop (WSL→Windows localhost is broken on this box).

## `bin/` — WSL local bin helpers

- `opsay` — Peer-Operator voice into fleet channels: `opsay "#lobby" "message"`. Wraps `tc send` with `AGENT_SLUG=operator`.

## `claudish-config-redacted.json` — claudish config shape

The claudish `~/.claudish/config.json` with API keys redacted. Shows the `customEndpoints` + `routing` pattern for adding providers (xiaomi token-plan, qwen MaaS, featherless, longcat, muse, nim, inception, adverserial).
