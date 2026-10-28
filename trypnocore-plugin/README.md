# Trypnocore memory and identity plugin

Trypnocore provides associative memory, identity loading, soulcycle snapshots, optional soulchain sealing and Jaynesian narration, plus the Your Turn, Planning With Files, and Metacognition skills. The same memory service works with Claude Code and with harnesses that speak MCP or plain HTTP.

Two installation profiles are supported:

- **Solo Linux/WSL:** native Python, SQLite pools, no GPU or OPZ installation required.
- **Collective CC-WSL:** the existing Windows + WSL + OmegaPrimeZero fleet setup.

## Solo Linux/WSL quickstart

Requirements: `python3` with `venv`, `pip`, and network access for the small `mcp` package. There is no torch, transformers, Hyperon, FastAPI, or GPU dependency.

From a checkout of this plugin:

```bash
bash install-solo.sh
```

The installer creates an isolated environment at `~/.local/share/trypnocore/venv`, installs only `mcp>=1.26,<2` (the current stdio API), registers the plugin as `trypnocore@local`, and starts the memory service on `127.0.0.1:8787`. It writes machine-local configuration to `~/.claude/plugins/trypnocore/config.env`; that file is not portable and is never committed.

Restart Claude Code or run `/reload-plugins`.

### Solo identity

Copy `trypnocore.example.json` to `trypnocore.json` in the agent's project folder and edit it:

```json
{
  "slug": "my-agent",
  "folder": ".",
  "pool": "my-agent",
  "lane": "",
  "note": "Solo agent"
}
```

The folder is relative to the JSON file. Alternatively, set `TRYP_AGENT_SLUG`, `TRYP_BOOT_FOLDER`, and `OPZ_POOL` in the environment. Without identity configuration, memory still works using a pool derived from the current directory name; soulchain-specific output is skipped.

### Service controls

```bash
~/.claude/plugins/trypnocore/scripts/opz-service.sh status
~/.claude/plugins/trypnocore/scripts/opz-service.sh restart
~/.claude/plugins/trypnocore/scripts/opz-service.sh stop
~/.claude/plugins/trypnocore/scripts/opz-service.sh start
```

Useful environment overrides before installation or service start:

- `TRYP_DATA_HOME`: virtualenv, pools, logs, and PID file location.
- `OPZ_CHAT_PORT`: memory service port, default `8787`.
- `OPZ_BASE_URL`: URL used by hooks and MCP, default `http://127.0.0.1:8787`.

## Use from other assistants

### Claude Code and Claude Duet

The installer registers `plugin:trypnocore:opz-memory` with tools `remember`, `list_atoms`, and `trinket_context`. The plugin also supplies SessionStart, UserPromptSubmit, Stop, and PreCompact hooks.

### Wajo/Fo, Grok Bot, GPT Dot, and other MCP clients

Use this stdio MCP command, substituting your plugin path:

```bash
~/.claude/plugins/trypnocore/scripts/opz-memory-mcp.sh
```

If your harness needs an explicit environment, set `OPZ_POOL` and `OPZ_BASE_URL`. The exact JSON location for these fields is harness-specific; use the harness's MCP configuration UI or documentation.

### Assistants without MCP support

The local HTTP API is model-agnostic:

```bash
# Store a memory
curl -X POST http://127.0.0.1:8787/memory/remember \
  -H 'Content-Type: application/json' \
  -d '{"line":"remember that portable memory works","pool":"solo"}'

# Recall it
curl 'http://127.0.0.1:8787/memory/atoms?pool=solo'

# Get associative context for a prompt
curl --get 'http://127.0.0.1:8787/memory/context' \
  --data-urlencode 'line=tell me about portable memory' \
  --data-urlencode 'pool=solo'
```

A reminder uses `remind me to ...` in the `line` field. Pool names are lowercase letters, digits, underscores, and hyphens.

## Optional semantic embeddings

Solo installs default to lexical recall and **zero GPU use**. Semantic embeddings are opt-in:

```bash
export OPZ_EMBED_MODEL=google/embeddinggemma-2
export OPZ_EMBED_DEVICE=cpu   # use cuda only when you have enough VRAM
~/.claude/plugins/trypnocore/scripts/opz-service.sh restart
```

The environment must also have `sentence-transformers` and its dependencies installed in the solo virtualenv. If the model cannot load, recall falls back to lexical matching.

## LoRA and custom narrator endpoints

Memory and identity are independent of the model. To use an OpenAI-compatible local or hosted model for narration/distillation, set:

```bash
export TRYP_NARRATOR_BASE_URL=http://127.0.0.1:8081/v1/chat/completions
export TRYP_NARRATOR_MODEL=your-lora-model
```

An API key is optional for custom endpoints. The default remains OpenRouter, where a key is required. The future LFM2.5 3B VL Heretic LoRA server can therefore supply narration while the same SQLite memory and identity hooks remain unchanged.

## Collective CC-WSL installation

From WSL:

```bash
bash /mnt/c/Trypnocore/Trypnocore_V6/trypnocore-plugin/install.sh
```

The collective profile expects OmegaPrimeZero at `C:\Trypnocore\OmegaPrimeZero`, its Windows Python virtualenv, the fleet registry at `C:\Trypnocore\fleet\fleet-registry.json`, and `Individuals/` boot folders. OPZ must be running on `127.0.0.1:8787`.

After verifying the plugin, retire old loose hooks and the duplicate global MCP registration:

```bash
bash /mnt/c/Trypnocore/Trypnocore_V6/trypnocore-plugin/install.sh --retire-shims
```

Both installers back up `~/.claude/settings.json` and `~/.claude.json` before changing them and are safe to re-run.
