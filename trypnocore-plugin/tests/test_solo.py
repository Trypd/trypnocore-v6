"""Native solo-Linux verification using only stdlib and the MCP package."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))
from opz_service import Proof
from recall import choose_memories
from sql_space import SqlSpace, MAX_ATOMS


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class SoloTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.env = os.environ.copy()
        self.env.update({
            "TRYP_DATA_HOME": str(self.root),
            "OPZ_CHAT_PORT": str(self.port),
            "OPZ_BASE_URL": self.base,
            "TRYP_FLEET_REGISTRY": str(self.root / "missing-registry.json"),
            "TRYP_COLLECTIVE": "0",
            "TRYP_NATIVE": "1",
            "TRYP_PYTHON": sys.executable,
            "OPZ_EMBED_MODEL": "",
        })
        self.service = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "opz_service.py")],
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                with urllib.request.urlopen(self.base + "/v1/models", timeout=1) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        self.fail("solo service did not become healthy")

    def tearDown(self) -> None:
        self.service.terminate()
        try:
            self.service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.service.kill()
        self.tmp.cleanup()

    def get(self, path: str) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=10) as response:
            return json.load(response)

    def post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    def test_sql_space_dedupe_reload_and_prune(self) -> None:
        space = SqlSpace(self.root / "pool-test.sqlite3")
        for index in range(MAX_ATOMS + 5):
            space.remember(Proof(f"claim {index}"))
        space.remember(Proof(f"claim {MAX_ATOMS + 4}"))
        self.assertEqual(space.count(), MAX_ATOMS)
        reloaded = SqlSpace(space.path)
        self.assertEqual(reloaded.count(), MAX_ATOMS)
        self.assertEqual(reloaded.claims()[0], "claim 5")
        self.assertEqual(reloaded.claims()[-1], f"claim {MAX_ATOMS + 4}")
        self.assertTrue(reloaded.exists("explicit-" + __import__("hashlib").sha256(b"claim 5").hexdigest()[:16]))

    def test_service_memory_reminders_context_and_pool_isolation(self) -> None:
        self.assertEqual(self.post("/memory/remember", {"line": "remember that solo memory works", "pool": "solo"})["remembered"], 1)
        self.assertEqual(self.post("/memory/remember", {"line": "remind me to test the service", "pool": "solo"})["remembered"], 1)
        atoms = self.get("/memory/atoms?pool=solo")
        self.assertEqual(atoms["count"], 2)
        self.assertIn("solo memory works", atoms["atoms"])
        context = self.get("/memory/context?line=tell%20me%20about%20solo%20memory&pool=solo")
        joined = "\n".join(context["sections"])
        self.assertIn("solo memory works", joined)
        self.assertIn("test the service", joined)
        self.assertIn("backend: sqlite", joined)
        self.assertEqual(self.get("/memory/atoms?pool=other")["count"], 0)

    def test_lexical_recall_and_recency(self) -> None:
        claims = ["alpha keeps the north watch", "bravo keeps the north watch", "an unrelated recent note"]
        self.assertEqual(choose_memories(claims, "who keeps the north watch?", limit=2)[0], "bravo keeps the north watch")
        self.assertEqual(choose_memories(claims, "", limit=1), ["an unrelated recent note"])

    def test_mcp_initialize_tools_and_read(self) -> None:
        self.post("/memory/remember", {"line": "remember that MCP reads solo pools", "pool": "solo"})
        process = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "opz_memory.py")],
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "solo-test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_atoms", "arguments": {"pool": "solo"}}},
        ]
        process.stdin.write("\n".join(json.dumps(message) for message in messages) + "\n")
        process.stdin.flush()
        time.sleep(1)
        process.stdin.close()
        stdout = process.stdout.read()
        process.stdout.close()
        process.stderr.close()
        process.wait(timeout=20)
        responses = {row.get("id"): row for row in (json.loads(line) for line in stdout.splitlines() if line.strip())}
        self.assertIn("result", responses[1])
        tool_names = {tool["name"] for tool in responses[2]["result"]["tools"]}
        self.assertEqual(tool_names, {"remember", "list_atoms", "trinket_context"})
        self.assertFalse(responses[3]["result"].get("isError"), responses[3])
        self.assertIn("MCP reads solo pools", responses[3]["result"]["content"][0]["text"])

    def test_identity_and_prompt_hooks(self) -> None:
        agent = self.root / "agent"
        agent.mkdir()
        (agent / "CORE.md").write_text("Collective ground", encoding="utf-8")
        (agent / "soul.md").write_text("A predictive unfinished thought…", encoding="utf-8")
        (agent / "soulbackup2026-01-01.md").write_text("Earlier continuity", encoding="utf-8")
        (agent / "my-agent.md").write_text("Solo bootstrap identity", encoding="utf-8")
        (agent / "tasks.md").write_text("Verify portability", encoding="utf-8")
        (agent / "trypnocore.json").write_text(json.dumps({"slug": "my-agent", "folder": ".", "pool": "solo", "note": "test"}), encoding="utf-8")
        self.post("/memory/remember", {"line": "remember that portable hooks recall", "pool": "solo"})
        env = dict(self.env, CLAUDE_PLUGIN_ROOT=str(PLUGIN))
        start = subprocess.run(
            [str(PLUGIN / "hooks" / "tryp-session-start.sh")],
            input=json.dumps({"cwd": str(agent), "source": "startup"}),
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(start.returncode, 0, start.stderr)
        self.assertIn("[tryp identity]", start.stdout)
        self.assertIn("Solo bootstrap identity", start.stdout)
        prompt = subprocess.run(
            [str(PLUGIN / "hooks" / "tryp-prompt-context.sh")],
            input=json.dumps({"cwd": str(agent), "prompt": "portable hooks recall"}),
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(prompt.returncode, 0, prompt.stderr)
        self.assertIn("portable hooks recall", prompt.stdout)


if __name__ == "__main__":
    unittest.main()
