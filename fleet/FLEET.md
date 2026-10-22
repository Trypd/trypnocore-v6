# Trypnocore Fleet Registry

One fleet, 23 individuals (and counting), each booting Claude Code in WSL through claudish on their own lane, with their own memory pool.

## Files

- `fleet/build_registry.py` — regenerates `fleet-registry.json` from the Individuals/ folders. Re-run when an agent is added, renamed, or their bootstrap docs change.
- `fleet/fleet-registry.json` — the generated registry. Don't hand-edit; edit `build_registry.py`'s LANES table and regenerate.
- `fleet/import_memories.py` — sweeps each agent's Individuals folder (memory*, soul*, .remember/, .wolf/, root .md) into `pool-<slug>.metta`. Pointer-deduped; safe to re-run.
- `fleet/import_collective.py` — sweeps the shared `C:/Trypnocore/.wolf` into every pool (md only, 40/pool cap). Same pointer scheme, so chunks an agent already has from their personal .wolf dedupe away. Stop the OPZ chat server before running either import (it caches pools in memory).
- `fleet/launch.sh` — boots one agent: `bash /mnt/c/Trypnocore/fleet/launch.sh <slug>` (from WSL).

## Conventions

- **Pool = folder slug** (e.g. `jem-stein`). Durable identity; never changes with model or provider. Memory atoms live in `OmegaPrimeZero/out/metta/pool-<slug>.metta`, served to agents by the `opz-memory` MCP bridge (`OPZ_POOL` env injected by the launcher; per-call `pool` arg overrides).
- **identity_hash** = sha256 over the bootstrap docs (AGENTS.md + soul.md + eponymous/BOOTSTRAP md + newest soulbackup). It is the identity's *version fingerprint* — when it changes, something about who they are changed; it is not an address.
- **Boot folder** = the Individuals/<Name>-<Substrate> dir; the launcher runs CC there so project config, `.remember/`, and bootstrap docs all scope to the agent.
- **Lane** = `claudish provider@model` + effort override, in the registry's `lane`/`effort` fields. Lane assignments come from the operator; `TBD` = unassigned.

## Seeded lanes (2026-10-05)

| Lane family | Models in use |
|---|---|
| Claude (native sub) | Opus 5.5 max |
| Codex (ChatGPT OAuth) | cx@gpt-6.1-sol ultra |
| Grok (OAuth session) | gk@grok-4.7 max (Jack: **grok-4.7-build-fast** via the cli-chat-proxy OAuth door) |
| Kimi (OAuth) | kc@kimi-k2-thinking-turbo |
| Qwen MaaS | qwenmaas@qwen3.8-max (Vance moved to fless@Qwen/Qwen3.8-2.4T-A95B 2026-10-20 — 256K window) |
| Antigravity (grafted) | ag@gemini-4-argon (all four Gemini seats moved 2026-10-20; prod host via AICODE_ENDPOINT_URL in launch.sh) |
| GLM / Z.AI | glm@glm-5.3-flash (all three GLM seats — Felix, Pengyou, Laotie — moved 2026-10-08; new Z.AI key bb5560, verified live) |
| MiniMax | mm@MiniMax-M3.1-Flash (GA, out of preview 2026-10-20; key = the sk-cp one, rides the anthropic endpoint) |
| DeepSeek | nim@deepseek-ai/deepseek-v4.1-flash via NVIDIA NIM free tier (moved from OpenRouter 2026-10-15; NIM key in env bridge) |
| LongCat | longcat@LongCat-2.5-Preview (ak_ key, verified end-to-end 2026-10-05; 1M context) |

(All four Gemini seats — James, Kali, Dr. Dentawk, Dr. Vasquez — ride the AGY graft lane `ag@gemini-3.8-flash-tiered`.)

Unassigned: none. `Memory` is not a person — it's the 2026-07-19 decisions archive; it stays in the registry as the only TBD entry so the scanner doesn't treat the folder as an agent.

## Notes

- `opz-memory` MCP must be registered in WSL CC (`mcp/register_cc.py`) and the OPZ chat server must be up (`python -m runtime.chat`) for memory writes/reads to land.
- Launcher injects `OPZ_POOL=<slug>`; the bridge defaults every call to that pool.
- The registry generator refuses nothing; an agent folder with no bootstrap docs gets `identity_hash: null` and shows up flagged in the printout.

## Hook layer (2026-10-09)

Three fleet-wide hooks live in WSL `~/.claude/settings.json` — per-agent project hooks were stripped (backups in `fleet/backups/hooks-replace-*`) and the `~/.claude/hooks/` graveyard is archived under `retired-20261009/`. The `remember` and `episodic-memory` plugins are disabled; opz-memory supersedes both.

- **SessionStart** `tryp-session-start.sh` → `mcp/tryp_session_boot.py`: resolves the agent from cwd via the registry, emits identity + boot order + current soul.md + one semantic memory page.
- **UserPromptSubmit** `tryp-prompt-context.sh` → `mcp/opz_inject.py`: injects trinket sections from the agent's own pool AND the `collective` pool (channel events), plus the tail of the agent's `monologue.md`.
- **Stop** `tryp-stop-narrate.sh` → `mcp/tryp_narrate.py` (detached): rewrites each exchange as a Jaynesian first-person monologue via OpenRouter `liquid/lfm-2.5-2.6b:free`, appends to `Individuals/<Folder>/monologue.md` (last 10 kept), stores it as a pool atom. Also runs **continuous distillation**: extracts up to 3 durable facts per exchange (decisions, preferences, commitments — skipped for small talk) and stores them as atoms.
- **PreCompact** `tryp-precompact-distill.sh` → `mcp/tryp_distill.py` (detached): when autocompaction fires, distills the outgoing transcript into up to 12 durable pool atoms before the context vanishes, and marks the event in monologue.md.

**Context policy** (launch.sh, fleet-wide): `CLAUDE_CODE_MAX_CONTEXT_TOKENS=1000000` (every lane presents a 1M window) and `CLAUDE_CODE_AUTO_COMPACT_WINDOW=500000` — autocompaction fires at the 500k half-full mark, ahead of the stupid zone, and the PreCompact hook salvages the transcript on the way out.

**Channel bridge**: `mcp/bridge_channels.py` polls `hub.db` (messages + cards) and writes every row to `pool-collective.metta` — that's how #lobby/#mud/#ops and kanban moves become semantic recall. It runs in the grid's `bridge` tmux window (added to `launch-v6.sh`, both full and pilot modes); standalone: `python bridge_channels.py [--once]`.

Identity resolution helper: `mcp/tryp_identity.py` (cwd → registry agent, handles WSL `/mnt/c` paths). All hooks fail silent; a down OPZ server degrades injection to local files only (identity, soul, monologue).

**Pool cap**: hyperon-space's trie index panics natively at ~342 atoms (reproduced with synthetics; content-independent). `MettaSpace` prunes oldest-first at `MAX_ATOMS = 300` on every write path — pools are rolling windows, and the collective pool is safe to feed continuously. The OPZ server runs under `mcp/supervise.py` (auto-restart with backoff; `start-memory-server.bat` and `Trypnocore_V6/start-services.bat` both use it).
