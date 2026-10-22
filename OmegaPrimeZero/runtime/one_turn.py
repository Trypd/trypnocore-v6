"""One text turn. Official llama.cpp, language GGUF, marked boot.

No second mind. No training. No duplex. Thoughts stay in content.
`--continue` appends one more reply onto the stored tape.
llama-cli single-turn takes one user prompt, so earlier messages are quoted inside it.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from runtime.mind.boot import load_boot
from runtime.mind.schema import SchemaError, assert_content_only, parse_assistant_content
from runtime.mind.turn import Tape, build_frame, reject_side_field, run_turn
from runtime.paths import BOOT_PATH, LLAMA_CLI, MINICPM_GGUF

SCHEMA_ASK = (
    "Reply in this exact shape and nothing else.\n"
    "think: one short line about what you are doing\n"
    "\n"
    "Then one spoken sentence."
)

DEFAULT_NEXT = "Repeat the exact think line from your last reply, as one spoken sentence."
TEMPERATURE = 1.1


class TurnError(RuntimeError):
    pass


def _reply_only(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    text = re.sub(r"\[ Prompt:.*?\]", "", text)
    text = text.replace("Exiting...", "")
    if "> " in text:
        text = text.split("> ")[-1]
    lines = []
    for line in text.splitlines():
        if line.startswith(("build :", "model :", "Loading model", "available commands", "modalities :")):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def fold_to_content(raw: str) -> str:
    """Put any think-tag into content. Never a side field."""
    text = _reply_only(raw)
    match = re.search(r"<think>\s*(.*?)\s*</think>\s*(.*)\Z", text, flags=re.DOTALL)
    if match:
        thoughts = [line.strip() for line in match.group(1).splitlines() if line.strip()]
        utterance = match.group(2).strip()
        head = "\n".join(f"think: {line}" if not line.startswith("think:") else line for line in thoughts)
        if not head:
            head = "think: empty"
        return f"{head}\n\n{utterance or '...'}"
    start = text.rfind("think:")
    if start >= 0:
        text = text[start:]
    if text.startswith("think:") and "\n\n" not in text:
        body = text[len("think:"):].strip()
        parts = re.split(r"(?<=[.!?])\s+", body, maxsplit=1)
        if len(parts) == 2:
            return f"think: {parts[0]}\n\n{parts[1]}"
        return f"think: {body}\n\n{body}"
    if text.startswith("think:"):
        return text
    sentence = " ".join(text.split())
    return f"think: reply\n\n{sentence}"


def _user_line(said: str) -> str:
    return f"{said.rstrip()}\n\n{SCHEMA_ASK}"


def prompt_for(said: str, history: list[dict] | None = None) -> str:
    """One user prompt. With history, earlier role/content pairs are quoted above the new request."""
    line = _user_line(said)
    if not history:
        return line
    blocks = ["Conversation so far. Answer only the new request. The spoken sentence is the part after the blank line."]
    for message in history:
        assert_content_only(message)
        blocks.append(f"{message['role']}:\n{message['content']}")
    blocks.append(f"user:\n{line}")
    return "\n\n".join(blocks)


def generate(
    said: str,
    *,
    history: list[dict] | None = None,
    temperature: float = TEMPERATURE,
    boot: Path = BOOT_PATH,
    model: Path = MINICPM_GGUF,
    cli: Path = LLAMA_CLI,
) -> str:
    if not cli.is_file():
        raise TurnError(f"llama-cli missing: {cli}")
    if not model.is_file():
        raise TurnError(f"model missing: {model}")
    load_boot(boot)
    prompt = prompt_for(said, history)
    command = [
        str(cli),
        "-m", str(model),
        "-sysf", str(boot),
        "-p", prompt,
        "-n", "180",
        "-c", "4096",
        "-ngl", "99",
        "--temp", str(temperature),
        "--single-turn",
        "--simple-io",
        "--log-disable",
        "--no-show-timings",
        "--no-display-prompt",
        "--chat-template-kwargs", '{"enable_thinking":false}',
    ]
    completed = subprocess.run(
        command,
        cwd=str(cli.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or "")[-2000:]
        raise TurnError(f"llama-cli exit {completed.returncode}\n{tail}")
    raw = completed.stdout.replace("\r\n", "\n").replace("\r", "\n")
    capture = BOOT_PATH.parent / "out" / "last-stdout.txt"
    capture.parent.mkdir(parents=True, exist_ok=True)
    capture.write_text(raw, encoding="utf-8")
    if prompt in raw:
        raw = raw.split(prompt)[-1]
    return fold_to_content(raw)


def _write_tape(tape: Tape, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"messages": tape.request()}, indent=2), encoding="utf-8")


def one_turn(said: str, *, out_path: Path | None = None) -> str:
    """Run one reply and store it as content on a fresh tape."""
    boot = load_boot(BOOT_PATH)
    content = generate(said)

    def mind(_frame: list[dict]) -> str:
        return content

    tape = Tape()
    tape.append("user", _user_line(said))
    frame = build_frame(boot=boot, supplemental="", tape=tape, trinket_sections=[], sensory=[])
    stored = run_turn(tape, mind, frame)
    parse_assistant_content(stored)
    if out_path is not None:
        _write_tape(tape, out_path)
    return stored


def load_tape(path: Path) -> Tape:
    if not path.is_file():
        raise TurnError(f"tape missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TurnError("tape must be an object")
    reject_side_field(payload)
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise TurnError("tape has no messages")
    tape = Tape()
    for message in messages:
        if not isinstance(message, dict):
            raise TurnError("tape message must be an object")
        tape.append(message["role"], message["content"])
    if tape.messages[-1]["role"] != "assistant":
        raise TurnError("tape must end on an assistant reply")
    return tape


def continue_turn(
    said: str,
    *,
    tape_path: Path,
    generate_fn=generate,
    temperature: float = TEMPERATURE,
) -> str:
    """Append one user line and one assistant reply. Leave the earlier messages in place."""
    tape = load_tape(tape_path)
    history = tape.request()
    boot = load_boot(BOOT_PATH)
    content = generate_fn(said, history=history, temperature=temperature)

    def mind(_frame: list[dict]) -> str:
        return content

    tape.append("user", _user_line(said))
    frame = build_frame(boot=boot, supplemental="", tape=tape, trinket_sections=[], sensory=[])
    try:
        stored = run_turn(tape, mind, frame)
    except SchemaError:
        tape_path.with_name("second-turn-folded.txt").write_text(content, encoding="utf-8")
        raise
    parse_assistant_content(stored)
    _write_tape(tape, tape_path)
    return stored


def main() -> None:
    import sys

    args = sys.argv[1:]
    out = Path(__file__).resolve().parents[1] / "out" / "one-turn.json"
    if args and args[0] == "--senses":
        from runtime.senses import sense_turn

        stored = sense_turn(out)
    elif args and args[0] == "--continue":
        said = " ".join(args[1:]).strip() or DEFAULT_NEXT
        stored = continue_turn(said, tape_path=out)
    else:
        said = " ".join(args).strip() or "Say who you are in one sentence."
        stored = one_turn(said, out_path=out)
    parsed = parse_assistant_content(stored)
    print(parsed.utterance)
    print(f"\n[tape] {out}")


if __name__ == "__main__":
    main()
