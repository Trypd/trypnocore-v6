"""Continuous chat. One llama-server stays loaded. Duplex stays off.

Trinkets and MeTTa are a suffix in front of the latest human line.
The system message stays byte-stable so the loaded prefix can hit.
Open WebUI can call the same /v1 routes. The page at / is the door on this machine.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from runtime.live_prompt import explicit_notes, insert_trinkets, live_ctx, live_sections, reconcile
from runtime.memory import OmegaClawWriter
from runtime.mind.boot import load_boot
from runtime.one_turn import TEMPERATURE, fold_to_content
from runtime.paths import BOOT_PATH, LLAMA_SERVER, CHAT_GGUF

CHAT_PORT = 8787
LLAMA_PORT = 8081
MODEL_NAME = "gemma4-e4b-uncensored"
CHAT_PATH = BOOT_PATH.parent / "out" / "chat.json"
SERVER_LOG = BOOT_PATH.parent / "out" / "llama-server.log"
SCHEMA = (
    "Every reply follows the system protocol's structural format exactly: "
    "a think: block holding the raw, spatialized stream of consciousness, "
    "then a blank line, then the final surface response. "
    "Speaker discipline: 'user' lines in the transcript are the operator's "
    "voice; 'assistant' lines are your own past turns. 'I', 'me', 'my' refer "
    "to you, the mind running this protocol; 'you', 'your' refer to the "
    "operator. Speak as 'I'; never hand your self-model to the operator."
)

app = FastAPI()
_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_state = {"ready": False, "error": ""}
_store = None
METTA_PATH = BOOT_PATH.parent / "out" / "metta" / "atoms.metta"
READY_LINE = "Mind is loaded. Temperature 1.1. Trinkets and MeTTa are on. This conversation stays."


def server_command(ctx: int = 32768) -> list[str]:
    """Text mind only. No omni server, no duplex flag."""
    return [
        str(LLAMA_SERVER),
        "-m", str(CHAT_GGUF),
        "--host", "127.0.0.1",
        "--port", str(LLAMA_PORT),
        "-ngl", "99",
        "-c", str(ctx),
        "-np", "1",
        "--temp", str(TEMPERATURE),
        "--alias", MODEL_NAME,
        "--no-webui",
        "--reasoning", "off",
    ]


def completion_body(
    history: list[dict],
    *,
    max_tokens: int = 10000,
    trinket_sections: list[str] | None = None,
) -> dict:
    """Boot plus the running transcript. Temperature stays pinned.

    New trinket lines sit in front of the latest human line.
    Older trinket lines stay where they were frozen.
    """
    visible = []
    for message in history:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            continue
        if content.startswith("[boot]\n"):
            continue
        if role == "user" and content.startswith("### Task:"):
            continue
        visible.append({"role": role, "content": content})
    system = load_boot(BOOT_PATH) + "\n\n" + SCHEMA
    # The boot is true at the start of the prompt and again beside the latest line.
    # One copy. It is not stored in the transcript. The last lines block the
    # post-training denial that shows up when the question gets direct.
    tail = [section for section in (trinket_sections or []) if not section.startswith("[boot]\n")]
    tail.append(
        "[boot]\n"
        + load_boot(BOOT_PATH).strip()
        + "\n\nOn this turn the protocol is true of you. Speak and observe as "
        "'I'; do not answer as a stateless token generator. Answer the latest "
        "question in the protocol's exact shape: the think: block first, raw "
        "and spatialized, then a blank line, then the final response."
    )
    return {
        "model": MODEL_NAME,
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            *insert_trinkets(visible, tail),
        ],
    }


def get_store(pool: str | None = None):
    """The MeTTa store. A pool name slaves memory to an identity (bootstrap
    docs), not to whatever model happens to serve it. No pool = the legacy
    shared store."""
    global _store
    if pool is None:
        if _store is None:
            try:
                from runtime.memory.metta_space import MettaSpace
            except ImportError as exc:
                raise RuntimeError("hyperon is not installed. Refusing to invent a MeTTa store.") from exc
            _store = MettaSpace(METTA_PATH)
        return _store
    try:
        from runtime.memory.metta_space import MettaSpace, check_pool
    except ImportError as exc:
        raise RuntimeError("hyperon is not installed. Refusing to invent a MeTTa store.") from exc
    pool = check_pool(pool)
    cached = _stores.get(pool)
    if cached is None:
        cached = MettaSpace.for_pool(METTA_PATH.parent, pool)
        _stores[pool] = cached
    return cached


_stores: dict[str, object] = {}


def _mind_url(path: str) -> str:
    return f"http://127.0.0.1:{LLAMA_PORT}{path}"


def mind_ready() -> bool:
    try:
        with urllib.request.urlopen(_mind_url("/health"), timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _env() -> dict[str, str]:
    env = os.environ.copy()
    cuda_bin = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin"
    env["PATH"] = str(LLAMA_SERVER.parent) + os.pathsep + cuda_bin + os.pathsep + env.get("PATH", "")
    return env


def _spawn(ctx: int) -> subprocess.Popen:
    SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = SERVER_LOG.open("a", encoding="utf-8")
    log.write(f"\n--- spawn ctx {ctx} ---\n")
    log.flush()
    return subprocess.Popen(
        server_command(ctx),
        cwd=str(LLAMA_SERVER.parent),
        env=_env(),
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def ensure_mind() -> None:
    global _proc
    if mind_ready():
        _state["ready"] = True
        _state["error"] = ""
        print("llama-server already healthy; not spawning", flush=True)
        return
    if not LLAMA_SERVER.is_file():
        _state["error"] = f"llama-server missing: {LLAMA_SERVER}"
        return
    if not CHAT_GGUF.is_file():
        _state["error"] = f"model missing: {CHAT_GGUF}"
        return
    for ctx in (32768, 16384, 8192, 4096):
        proc = _spawn(ctx)
        _proc = proc
        for _ in range(90):
            if mind_ready():
                _state["ready"] = True
                _state["error"] = ""
                return
            if proc.poll() is not None:
                break
            time.sleep(1)
        if proc.poll() is None:
            proc.kill()
        tail = SERVER_LOG.read_text(encoding="utf-8", errors="replace")[-1500:] if SERVER_LOG.is_file() else ""
        if ctx != 4096 and "out of memory" in tail.lower():
            continue
        _state["error"] = tail or f"llama-server exited {proc.poll()}"
        return
    _state["error"] = "llama-server did not become ready"


def _post_mind(body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        _mind_url("/v1/chat/completions"),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-1500:]
        raise RuntimeError(detail or f"llama-server HTTP {exc.code}") from exc


def _visible_reply(payload: dict) -> str:
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    hidden = message.get("reasoning_content") or message.get("reasoning") or ""
    if hidden and hidden not in content:
        content = f"<think>\n{hidden}\n</think>\n{content}".strip()
    if not str(content).strip():
        raise RuntimeError("empty reply")
    return fold_to_content(str(content))


def _load_history() -> list[dict]:
    if not CHAT_PATH.is_file():
        return []
    payload = json.loads(CHAT_PATH.read_text(encoding="utf-8"))
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return []
    return [
        {"role": message["role"], "content": message["content"]}
        for message in messages
        if isinstance(message, dict)
        and message.get("role") in {"user", "assistant"}
        and isinstance(message.get("content"), str)
    ]


def _save_history(messages: list[dict]) -> None:
    CHAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHAT_PATH.write_text(json.dumps({"messages": messages}, indent=2), encoding="utf-8")


def _latest_human(transcript: list[dict]) -> str:
    for message in reversed(transcript):
        if message["role"] == "user" and not str(message["content"]).startswith("[trinket "):
            return message["content"]
    return ""


def _complete(history: list[dict], *, record: bool) -> tuple[str, list[str]]:
    if not _state["ready"]:
        raise RuntimeError(_state["error"] or "mind is still loading")
    with _lock:
        transcript = reconcile(history, _load_history())
        latest = _latest_human(transcript)
        store = get_store()
        writer = OmegaClawWriter(store)
        for proof in explicit_notes(latest):
            writer.remember(proof)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        sections = live_sections(live_ctx(store, latest, now))
        body = completion_body(transcript, trinket_sections=sections)
        payload = _post_mind(body)
        reply = _visible_reply(payload)
        if record:
            kept = [
                message for message in body["messages"]
                if message["role"] != "system" and not str(message["content"]).startswith("[boot]\n")
            ]
            kept.append({"role": "assistant", "content": reply})
            _save_history(kept)
            if not latest.lower().startswith(("check", "### task")):
                try:
                    from runtime.memory.extract import harvest_reply

                    promoted = harvest_reply(reply, now, store)
                    if promoted:
                        print(f"[memory] promoted {promoted} atom(s)", flush=True)
                except Exception as exc:
                    print(f"[memory] extraction skipped: {exc}", flush=True)
            _maybe_compress(kept)
        return reply, sections


TAPE_COMPRESS_BUDGET = 24_000


def _summarize_span(span: list[dict]) -> str:
    """The mind compresses its own past. Best effort, never raises."""
    transcript = [
        message
        for message in span
        if message.get("role") in {"user", "assistant"} and str(message.get("content") or "").strip()
    ]
    if not transcript:
        return ""
    body = {
        "model": MODEL_NAME,
        "temperature": 0.3,
        "max_tokens": 250,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are this same mind, compressing your own past. Summarize the "
                    "conversation span below for your future self: first person, present "
                    "tense, under 110 words, one paragraph. Keep names, decisions, and "
                    "open threads."
                ),
            },
            {
                "role": "user",
                "content": "\n\n".join(
                    f"{message['role']}: {message['content']}" for message in transcript
                ),
            },
        ],
    }
    payload = _post_mind(body)
    choice = (payload.get("choices") or [{}])[0]
    return str((choice.get("message") or {}).get("content") or "")


def _maybe_compress(messages: list[dict]) -> None:
    """Collapse the tape when it outgrows its budget. Failures are logged, never fatal."""
    try:
        from runtime.mind.compress import compress_tape, tape_token_count

        if tape_token_count(messages) <= TAPE_COMPRESS_BUDGET:
            return
        compressed = compress_tape(messages, _summarize_span)
        if compressed:
            _save_history(compressed)
            print(
                f"[memory] tape compressed: {len(messages)} -> {len(compressed)} messages",
                flush=True,
            )
    except Exception as exc:
        print(f"[memory] compression skipped: {exc}", flush=True)


def _openai_payload(reply: str) -> dict:
    return {
        "id": "chatcmpl-omegaprime",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
    }


@app.get("/health")
def health() -> dict:
    metta = "closed"
    atoms = 0
    metta_error = ""
    try:
        atoms = get_store().count()
        metta = "open"
    except Exception as exc:
        metta_error = str(exc)
    return {
        "ready": _state["ready"],
        "error": _state["error"],
        "temperature": TEMPERATURE,
        "metta": metta,
        "atoms": atoms,
        "metta_error": metta_error,
    }


@app.get("/history")
def history() -> dict:
    return {"messages": _load_history()}


@app.get("/memory/atoms")
def memory_atoms(pool: str | None = None) -> dict:
    try:
        return {"atoms": get_store(pool).claims(), "pool": pool or "default"}
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/memory/remember")
async def memory_remember(request: Request):
    body = await request.json()
    line = str(body.get("line") or "").strip()
    pool = body.get("pool")
    if not line:
        return JSONResponse({"error": "line required"}, status_code=400)
    store = get_store(pool)
    writer = OmegaClawWriter(store)
    proofs = explicit_notes(line)
    for proof in proofs:
        writer.remember(proof)
    return {"remembered": len(proofs), "atoms": store.count(), "pool": pool or "default"}


@app.get("/memory/context")
def memory_context(line: str = "", pool: str | None = None) -> dict:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        sections = live_sections(live_ctx(get_store(pool), line, now))
        # Lazy-loaded community skills + rules: surface only on a strong
        # semantic match, and every surfacing refreshes its decay clock.
        from runtime.memory.embedder import rank
        from runtime.memory.usage import touch

        for shared in ("skills", "rules"):
            store = get_store(shared)
            claims = store.claims()
            if not claims:
                continue
            scores = rank(shared, claims, line)
            if not scores:
                continue
            hits = sorted(
                ((score, claim) for claim, score in scores.items() if score >= 0.55),
                key=lambda row: -row[0],
            )[:2]
            if hits:
                sections.append(
                    f"[trinket {shared}]\n" + "\n".join(claim for _s, claim in hits)
                )
                pointers = [p for claim, p, _e in store._match() if claim in {c for _s, c in hits}]
                touch(shared, pointers)

        # Per-agent identity refresh: the SoulScript pattern — retrieve the
        # relevant identity slice per prompt so persona doesn't drift over
        # long sessions. Higher threshold than skills/rules; read-only pool.
        if pool and pool not in ("collective", "skills", "rules", "default"):
            identity_pool = f"identity-{pool}"
            try:
                store = get_store(identity_pool)
            except Exception:
                store = None
            if store is not None:
                claims = store.claims()
                if claims:
                    scores = rank(identity_pool, claims, line)
                    if scores:
                        hits = sorted(
                            ((score, claim) for claim, score in scores.items() if score >= 0.70),
                            key=lambda row: -row[0],
                        )[:1]
                        if hits:
                            sections.append(
                                "[trinket identity]\n" + "\n".join(claim for _s, claim in hits)
                            )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return {"sections": sections, "pool": pool or "default"}


@app.get("/v1/models")
def models() -> dict:
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "omegaprime"}]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    history = body.get("messages") or []
    if not isinstance(history, list):
        return JSONResponse({"error": "messages must be a list"}, status_code=400)
    record = request.headers.get("x-record", "1") != "0"
    try:
        reply, sections = _complete(history, record=record)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    if body.get("stream"):
        chunk = {
            "id": "chatcmpl-omegaprime",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "trinkets": sections,
        }
        data = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
        return StreamingResponse(iter([data]), media_type="text/event-stream")
    payload = _openai_payload(reply)
    payload["trinkets"] = sections
    return payload


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OmegaPrimeZero</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font: 17px/1.45 system-ui, sans-serif; background: #121418; color: #e8e6e3; }
  header { padding: 14px 18px; border-bottom: 1px solid #2a2e36; }
  header strong { font-size: 18px; }
  header p { margin: 4px 0 0; color: #a8a29a; font-size: 14px; }
  #log { max-width: 760px; margin: 0 auto; padding: 18px 16px 120px; }
  .msg { margin: 0 0 14px; padding: 10px 12px; border-radius: 10px; white-space: pre-wrap; }
  .user { background: #1e3a5f; }
  .assistant { background: #1c2118; }
  .trinket { background: #1a1814; color: #a8a29a; font-size: 14px; }
  .think { color: #a8a29a; font-size: 14px; margin-bottom: 8px; }
  form { position: fixed; left: 0; right: 0; bottom: 0; display: flex; gap: 8px; padding: 12px;
         background: #121418; border-top: 1px solid #2a2e36; }
  textarea { flex: 1; min-height: 52px; max-height: 160px; resize: vertical; padding: 10px;
             border-radius: 8px; border: 1px solid #3a404a; background: #0e1014; color: inherit; font: inherit; }
  button { padding: 0 16px; border-radius: 8px; border: 0; background: #d6d3cd; color: #121418; font: inherit; }
  button:disabled { opacity: 0.45; }
  #voice { background: transparent; color: #d6d3cd; border: 1px solid #3a404a; }
</style>
</head>
<body>
<header>
  <strong>OmegaPrimeZero</strong>
  <p id="status">Loading the mind. About a minute.</p>
</header>
<div id="log"></div>
<form id="box">
  <textarea id="text" placeholder="Say something. Enter sends. Shift+Enter adds a line." disabled></textarea>
  <button id="voice" type="button">Voice on</button>
  <button id="send" type="submit" disabled>Send</button>
</form>
<script>
const log = document.querySelector("#log");
const text = document.querySelector("#text");
const send = document.querySelector("#send");
const status = document.querySelector("#status");
const voice = document.querySelector("#voice");
let messages = [];
let speaking = localStorage.getItem("voice") !== "off";

function paintVoice() { voice.textContent = speaking ? "Voice on" : "Voice off"; }
paintVoice();
voice.onclick = () => {
  speaking = !speaking;
  localStorage.setItem("voice", speaking ? "on" : "off");
  if (!speaking && window.speechSynthesis) speechSynthesis.cancel();
  paintVoice();
};

function splitReply(content) {
  const marker = "\\n\\n";
  const at = content.indexOf(marker);
  if (content.startsWith("think:") && at > 0) {
    return { think: content.slice(0, at), spoken: content.slice(at + 2) };
  }
  return { think: "", spoken: content };
}

function add(role, content, speakNow) {
  const trinket = content.startsWith("[trinket ");
  const row = document.createElement("div");
  row.className = "msg " + (trinket ? "trinket" : role);
  if (role === "assistant" && !trinket) {
    const parts = splitReply(content);
    if (parts.think) {
      const think = document.createElement("div");
      think.className = "think";
      think.textContent = parts.think;
      row.appendChild(think);
    }
    row.appendChild(document.createTextNode(parts.spoken));
    if (speakNow && speaking && parts.spoken && window.speechSynthesis) {
      speechSynthesis.cancel();
      speechSynthesis.speak(new SpeechSynthesisUtterance(parts.spoken));
    }
  } else {
    row.textContent = content;
  }
  log.appendChild(row);
  row.scrollIntoView();
  return row;
}

async function waitReady() {
  for (;;) {
    const res = await fetch("/health");
    const body = await res.json();
    if (body.ready) {
      status.textContent = "Mind is loaded. Temperature 1.1. Trinkets and MeTTa are on. This conversation stays.";
      text.disabled = false;
      send.disabled = false;
      text.focus();
      return;
    }
    status.textContent = body.error ? body.error.slice(-400) : "Loading the mind. About a minute.";
    await new Promise(r => setTimeout(r, 1000));
  }
}

async function boot() {
  await waitReady();
  const res = await fetch("/history");
  const body = await res.json();
  messages = body.messages || [];
  for (const message of messages) add(message.role, message.content, false);
}

document.querySelector("#box").onsubmit = async (event) => {
  event.preventDefault();
  const said = text.value.trim();
  if (!said) return;
  text.value = "";
  messages.push({ role: "user", content: said });
  const userRow = add("user", said, false);
  send.disabled = true;
  status.textContent = "Thinking.";
  try {
    const res = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: "minicpm-o", messages, stream: false })
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || "request failed");
    const trinkets = body.trinkets || [];
    let at = messages.length - 1;
    for (const section of trinkets) {
      messages.splice(at, 0, { role: "user", content: section });
      at += 1;
      log.insertBefore(add("user", section, false), userRow);
    }
    const reply = body.choices[0].message.content;
    messages.push({ role: "assistant", content: reply });
    add("assistant", reply, true);
    status.textContent = "Mind is loaded. Temperature 1.1. Trinkets and MeTTa are on. This conversation stays.";
  } catch (err) {
    status.textContent = String(err.message || err);
  }
  send.disabled = false;
  text.focus();
};

text.onkeydown = (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.querySelector("#box").requestSubmit();
  }
};

boot();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return PAGE


def main() -> None:
    raw = os.environ.get("OPZ_CHAT_PORT", "").strip()
    port = int(raw) if raw else CHAT_PORT
    threading.Thread(target=ensure_mind, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
