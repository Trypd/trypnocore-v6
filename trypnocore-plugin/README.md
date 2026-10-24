# Trypnocore Claude Code plugin

Packages the Trypnocore v6 SessionStart identity loader, associative memory injection, Stop-time soulchain sealing and Jaynesian narration, and PreCompact memory distillation. It also provides the opz-memory MCP server plus the Your Turn, Planning With Files, and Metacognition skills.

## Requirements

This installer targets the collective's CC-WSL setup on Windows. It expects the OmegaPrimeZero runtime at `C:\Trypnocore\OmegaPrimeZero`, its Python virtual environment, the fleet registry at `C:\Trypnocore\fleet\fleet-registry.json`, and individual folders under `C:\Trypnocore\Individuals`. The OPZ memory service must be running on `127.0.0.1:8787`.

## Install

From WSL:

```bash
bash /mnt/c/Trypnocore/Trypnocore_V6/trypnocore-plugin/install.sh
```

Restart Claude Code sessions after installation. To remove the legacy loose hooks and global opz-memory registration only after verifying the plugin, run:

```bash
bash /mnt/c/Trypnocore/Trypnocore_V6/trypnocore-plugin/install.sh --retire-shims
```

The installer backs up `~/.claude/settings.json` and `~/.claude.json` before changing them. Re-running it is safe.
