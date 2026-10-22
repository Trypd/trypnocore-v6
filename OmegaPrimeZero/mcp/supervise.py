"""Supervised runner for the OPZ chat server.

The bare `python -m runtime.chat` process dies silently (OOM, CUDA faults,
session kills) and everything downstream — hooks, bridge, MCP — goes dark
with it. This wrapper restarts it with backoff and appends to
out/supervisor.log. Stop with Ctrl+C; it stops the child too.

Run: python mcp/supervise.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "out" / "supervisor.log"
MIN_UPTIME_S = 30      # faster crashes than this count as flapping
MAX_BACKOFF_S = 300


def log(line: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{stamp}] {line}"
    print(text, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except Exception:
        pass


def main() -> None:
    backoff = 5
    while True:
        started = time.time()
        log("starting python -m runtime.chat")
        proc = subprocess.Popen(
            [sys.executable, "-m", "runtime.chat"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            log("supervisor stopped by operator")
            return
        uptime = time.time() - started
        log(f"runtime.chat exited code={code} after {uptime:.0f}s")
        backoff = 5 if uptime >= MIN_UPTIME_S else min(backoff * 2, MAX_BACKOFF_S)
        log(f"restarting in {backoff}s")
        time.sleep(backoff)


if __name__ == "__main__":
    main()
