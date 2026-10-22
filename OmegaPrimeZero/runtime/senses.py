"""Eyes, ears, and voice for one turn.

llama-omni-cli loads the MiniCPM-o towers and runs one prefill plus one decode.
Duplex streaming stays off. The text runner keeps temperature 1.1.
"""
from __future__ import annotations

import io
import math
import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from runtime.mind.schema import parse_assistant_content
from runtime.mind.turn import Tape, run_turn
from runtime.one_turn import TEMPERATURE, TurnError, _write_tape, fold_to_content, load_tape
from runtime.paths import (
    BOOT_PATH,
    LLAMA_OMNI,
    MINICPM_AUDIO_GGUF,
    MINICPM_GGUF,
    MINICPM_PROJECTOR_GGUF,
    MINICPM_TOWERS,
    MINICPM_TTS_GGUF,
    MINICPM_VISION_GGUF,
)
from runtime.slaves.audio import heard_line
from runtime.slaves.self_voice import SelfVoiceBuffer
from runtime.slaves.vl import saw_line

REF_AUDIO = Path(r"D:\llama.cpp-omni\tools\omni\assets\default_ref_audio\default_ref_audio.wav")
OMNI_CANDIDATES = (
    Path(r"D:\llama.cpp-omni-ninja\bin\llama-omni-cli.exe"),
    LLAMA_OMNI,
    Path(r"D:\llama.cpp-omni-build\bin\llama-omni-cli.exe"),
    Path(r"D:\llama.cpp-omni-build\Release\llama-omni-cli.exe"),
)


def missing_towers() -> list[Path]:
    return [path for path in MINICPM_TOWERS if not path.is_file()]


def find_omni() -> Path:
    for path in OMNI_CANDIDATES:
        if path.is_file():
            return path
    raise TurnError(f"llama-omni-cli missing: {LLAMA_OMNI}")


def sense_command(
    *,
    cli: Path,
    prefix: str,
    ref_audio: Path,
    temperature: float = TEMPERATURE,
    ngl: str = "99",
) -> list[str]:
    """One turn-based omni call. No server, no duplex flag."""
    return [
        str(cli),
        "-m", str(MINICPM_GGUF),
        "--vision", str(MINICPM_VISION_GGUF),
        "--audio", str(MINICPM_AUDIO_GGUF),
        "--tts", str(MINICPM_TTS_GGUF),
        "--projector", str(MINICPM_PROJECTOR_GGUF),
        "--omni",
        "--test", prefix, "1",
        "--temp", f"{temperature}",
        "--ref-audio", str(ref_audio),
        "-ngl", ngl,
        "-c", "4096",
    ]


def write_tone(path: Path, seconds: float = 1.0, rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for index in range(count):
            sample = int(8000 * math.sin(2 * math.pi * 220 * index / rate))
            frames += struct.pack("<h", sample)
        handle.writeframes(frames)


def write_frame(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        Image.new("RGB", (64, 64), (24, 140, 48)).save(path, "JPEG")
        return
    except Exception:
        path.write_bytes(
            bytes.fromhex(
                "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc40014000100000000000000000000000000000009ffc40014100100000000000000000000000000000000ffda0008010100003f007fffd9"
            )
        )


def stage_case(image: Path, audio: Path, work: Path) -> str:
    case = work / "case"
    case.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image, case / "in_0000.jpg")
    shutil.copyfile(audio, case / "in_0000.wav")
    return str(case / "in_")


def output_root(work: Path) -> Path:
    return work / "tools" / "omni" / "output"


def collect_text(root: Path) -> str:
    if not root.is_dir():
        return ""
    parts = []
    for file in sorted(root.rglob("llm_text.txt")):
        text = file.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _concat_wavs(paths: list[Path]) -> bytes:
    frames: list[bytes] = []
    params: tuple[int, int, int] | None = None
    for path in paths:
        with wave.open(str(path), "rb") as handle:
            current = (handle.getnchannels(), handle.getsampwidth(), handle.getframerate())
            if params is None:
                params = current
            elif current != params:
                raise TurnError(f"voice chunks differ in format: {path}")
            frames.append(handle.readframes(handle.getnframes()))
    if params is None:
        raise TurnError("voice chunks missing")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(params[0])
        handle.setsampwidth(params[1])
        handle.setframerate(params[2])
        handle.writeframes(b"".join(frames))
    return buffer.getvalue()


def collect_voice(root: Path) -> bytes | None:
    """Full spoken wav. Chunk names are wav_0 … wav_24, so numeric order matters."""
    if not root.is_dir():
        return None
    merged = [path for path in root.rglob("tts_output_merged.wav") if path.stat().st_size > 44]
    if merged:
        return merged[-1].read_bytes()
    chunks: list[tuple[int, Path]] = []
    for path in root.rglob("wav_*.wav"):
        suffix = path.stem.removeprefix("wav_")
        if suffix.isdigit() and path.stat().st_size > 44:
            chunks.append((int(suffix), path))
    if not chunks:
        wavs = [path for path in sorted(root.rglob("*.wav")) if path.stat().st_size > 44]
        return wavs[-1].read_bytes() if wavs else None
    chunks.sort()
    return _concat_wavs([path for _index, path in chunks])


def sense_messages(raw_text: str, input_wav: bytes, voice_wav: bytes | None) -> tuple[str, str, str, SelfVoiceBuffer]:
    """saw: and heard: stay on the user side. The spoken wav arms the self-voice filter."""
    buffer = SelfVoiceBuffer()
    saw = saw_line("one green frame")
    if saw is None or BOOT_PATH.name in saw:
        raise TurnError("eyes produced no saw line")
    heard = heard_line(input_wav, "a short tone", buffer)
    if heard is None:
        raise TurnError("ears dropped the input tone")
    content = fold_to_content(raw_text)
    utterance = parse_assistant_content(content).utterance
    waveform = voice_wav if voice_wav else utterance.encode("utf-8")
    buffer.arm(utterance, waveform)
    if heard_line(waveform, utterance, buffer) is not None:
        raise TurnError("voice leaked back into heard:")
    return saw, heard, content, buffer


def sense_turn(tape_path: Path, *, temperature: float = TEMPERATURE, ngl: str = "99") -> str:
    missing = missing_towers()
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise TurnError(f"tower missing: {names}")
    cli = find_omni()
    work = tape_path.parent / "omni-run"
    if work.exists():
        shutil.rmtree(work)
    media = work / "media"
    media.mkdir(parents=True)
    image = media / "frame.jpg"
    audio = media / "tone.wav"
    write_frame(image)
    write_tone(audio)
    ref = REF_AUDIO if REF_AUDIO.is_file() and REF_AUDIO.stat().st_size > 1000 else audio
    prefix = stage_case(image, audio, work)
    command = sense_command(cli=cli, prefix=prefix, ref_audio=ref, temperature=temperature, ngl=ngl)
    if "llama-omni-server" in command or "--duplex" in command:
        raise TurnError("duplex is off")
    env = os.environ.copy()
    cuda_bin = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1\bin"
    env["PATH"] = str(cli.parent) + os.pathsep + cuda_bin + os.pathsep + env.get("PATH", "")
    completed = subprocess.run(
        command,
        cwd=str(work),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
        env=env,
    )
    log = work / "omni-log.txt"
    log.write_text((completed.stdout or "") + "\n" + (completed.stderr or ""), encoding="utf-8")
    if completed.returncode != 0 and ngl == "99":
        tail = (completed.stderr or "") + (completed.stdout or "")
        if "out of memory" in tail.lower():
            return sense_turn(tape_path, temperature=temperature, ngl="20")
    if completed.returncode != 0:
        raise TurnError(f"llama-omni-cli exit {completed.returncode}\n{(completed.stderr or '')[-2000:]}")
    root = output_root(work)
    raw = collect_text(root)
    if not raw:
        raw = completed.stdout or ""
    voice = collect_voice(root)
    if voice:
        (tape_path.parent / "voice.wav").write_bytes(voice)
    saw, heard, content, _buffer = sense_messages(raw, audio.read_bytes(), voice)
    try:
        tape = load_tape(tape_path)
    except TurnError:
        tape = Tape()

    def mind(_frame: list[dict]) -> str:
        return content

    tape.append("user", f"{saw}\n{heard}")
    stored = run_turn(tape, mind, [])
    _write_tape(tape, tape_path)
    return stored
