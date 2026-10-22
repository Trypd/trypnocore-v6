"""Drop the mind's own speech before it can become heard:."""
from __future__ import annotations

import hashlib


class SelfVoiceBuffer:
    def __init__(self) -> None:
        self.utterance: str | None = None
        self.fingerprint: str | None = None

    def arm(self, utterance: str, waveform: bytes) -> None:
        self.utterance = utterance
        self.fingerprint = hashlib.sha256(waveform).hexdigest()

    def is_self(self, waveform: bytes | None, transcript: str | None) -> bool:
        if waveform is not None and self.fingerprint is not None:
            if hashlib.sha256(waveform).hexdigest() == self.fingerprint:
                return True
        if transcript is not None and self.utterance is not None:
            if transcript.strip() == self.utterance.strip():
                return True
        return False
