"""Operator checkpoints. Recorded, frozen, not opened by unit tests."""
from __future__ import annotations

from pathlib import Path

MIND_GGUF = Path(r"C:\Users\Trypd\Downloads\LFM2.5-8B-A1B-heretic.i1-Q5_K_S.gguf")
VL_GGUF = Path(r"D:\LM Studio\models\LFM2.5-VL-3B-heretic-Q4_K_M.gguf")
AUDIO_GGUF = Path(r"D:\LM Studio\models\LFM2.5-Audio-1.5B-Q4_0.gguf")
# The plus in this filename is stored as the three characters %2B. Do not decode it.
AUDIO_MMPROJ_GGUF = Path(r"D:\LM Studio\models\mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf")
AUDIO_TOKENIZER_GGUF = Path(r"D:\LM Studio\models\tokenizer-LFM2.5-Audio-1.5B-BF16.gguf")
AUDIO_VOCODER_TOKENIZER_GGUF = Path(
    r"D:\LM Studio\models\vocoder%2Btokenizer-LFM2.5-Audio-1.5-BF16.gguf"
)
AUDIO_VOCODER_GGUF = Path(r"D:\LM Studio\models\vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf")
AUDIO_STACK = (
    AUDIO_GGUF,
    AUDIO_MMPROJ_GGUF,
    AUDIO_TOKENIZER_GGUF,
    AUDIO_VOCODER_TOKENIZER_GGUF,
    AUDIO_VOCODER_GGUF,
)

# One mind. Language GGUF plus the MiniCPM-o towers. Duplex stays off.
MINICPM_GGUF = Path(r"C:\Trypnocore\OmegaPrimeZero\models\MiniCPM-o-4_5-Q4_K_M.gguf")
# Text mind served by runtime/chat.py (operator-selected 2026-09-30).
CHAT_GGUF = Path(r"D:\LM Studio\models\Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf")
MINICPM_BYTES = 5_026_714_400
MINICPM_ID = "openbmb/MiniCPM-o-4_5"
MINICPM_VISION_GGUF = Path(r"C:\Trypnocore\OmegaPrimeZero\models\vision\MiniCPM-o-4_5-vision-F16.gguf")
MINICPM_AUDIO_GGUF = Path(r"C:\Trypnocore\OmegaPrimeZero\models\audio\MiniCPM-o-4_5-audio-F16.gguf")
MINICPM_TTS_GGUF = Path(r"C:\Trypnocore\OmegaPrimeZero\models\tts\MiniCPM-o-4_5-tts-F16.gguf")
MINICPM_PROJECTOR_GGUF = Path(r"C:\Trypnocore\OmegaPrimeZero\models\tts\MiniCPM-o-4_5-projector-F16.gguf")
MINICPM_TOKEN2WAV = (
    Path(r"C:\Trypnocore\OmegaPrimeZero\models\token2wav-gguf\encoder.gguf"),
    Path(r"C:\Trypnocore\OmegaPrimeZero\models\token2wav-gguf\flow_matching.gguf"),
    Path(r"C:\Trypnocore\OmegaPrimeZero\models\token2wav-gguf\flow_extra.gguf"),
    Path(r"C:\Trypnocore\OmegaPrimeZero\models\token2wav-gguf\hifigan2.gguf"),
    Path(r"C:\Trypnocore\OmegaPrimeZero\models\token2wav-gguf\prompt_cache.gguf"),
)
MINICPM_TOWERS = (
    MINICPM_VISION_GGUF,
    MINICPM_AUDIO_GGUF,
    MINICPM_TTS_GGUF,
    MINICPM_PROJECTOR_GGUF,
    *MINICPM_TOKEN2WAV,
)
LLAMA_CLI = Path(r"C:\Trypnocore\OmegaPrimeZero\bin\llama-b11146\llama-cli.exe")
LLAMA_SERVER = Path(r"C:\Trypnocore\OmegaPrimeZero\bin\llama-b11146\llama-server.exe")
LLAMA_OMNI = Path(r"D:\llama.cpp-omni-ninja\bin\llama-omni-cli.exe")
BOOT_PATH = Path(r"C:\Trypnocore\OmegaPrimeZero\AGENTS.md")

MIND_ID = "LiquidAI/LFM2.5-8B-A1B"
VL_ID = "LFM2.5-VL-3B-heretic"
AUDIO_ID = "LiquidAI/LFM2.5-Audio-1.5B"

# Bytes measured when the operator passed the paths. Tests compare stat size, not contents.
MIND_BYTES = 5_870_186_656
VL_BYTES = 1_674_455_200
AUDIO_BYTES = 695_750_880
AUDIO_MMPROJ_BYTES = 219_511_136
AUDIO_TOKENIZER_BYTES = 140_325_984
AUDIO_VOCODER_TOKENIZER_BYTES = 527_485_216
AUDIO_VOCODER_BYTES = 148_508_512
