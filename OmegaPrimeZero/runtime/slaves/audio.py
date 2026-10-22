"""Waveform to heard:. Utterance to speech. Self-voice never becomes input."""
from __future__ import annotations

from runtime.paths import AUDIO_STACK
from runtime.slaves.self_voice import SelfVoiceBuffer


def heard_line(
    waveform: bytes | None,
    transcript: str | None,
    buffer: SelfVoiceBuffer,
) -> str | None:
    if waveform is None and not transcript:
        return None
    if buffer.is_self(waveform, transcript):
        return None
    if waveform is None:
        return None
    text = (transcript or "external speech").strip()
    if text.startswith("think:") or text.startswith("heard:"):
        raise RuntimeError("audio must not paraphrase or emit think:")
    return f"heard: {text}"


def speak(utterance: str, buffer: SelfVoiceBuffer) -> dict:
    """Synthesis body is exactly the utterance. Then the filter arms."""
    waveform = utterance.encode("utf-8")
    buffer.arm(utterance, waveform)
    return {"text": utterance, "waveform": waveform}


def checkpoint() -> list[str]:
    """Model, mmproj, tokenizer, vocoder+tokenizer, vocoder. Paths only."""
    return [str(path) for path in AUDIO_STACK]
