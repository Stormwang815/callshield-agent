"""Optional local Whisper ASR; the model is reused and inference is serialized."""

import io
import math
import os
import threading
import wave
from functools import lru_cache
from pathlib import Path

_LOCK = threading.Lock()


def validate_wav(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            if (
                audio.getnchannels() != 1
                or audio.getsampwidth() != 2
                or audio.getframerate() != 16000
                or audio.getcomptype() != "NONE"
            ):
                raise ValueError("Only 16 kHz mono 16-bit PCM WAV audio is accepted")
            duration = audio.getnframes() / audio.getframerate()
            if not 0.2 <= duration <= 15:
                raise ValueError("Audio segments must be between 0.2 and 15 seconds")
            raw = audio.readframes(audio.getnframes())
            if len(raw) != audio.getnframes() * 2:
                raise ValueError("Incomplete WAV data")
            return duration
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid WAV file") from exc


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        os.getenv("CALLSHIELD_ASR_MODEL", "base"), device="cpu", compute_type="int8"
    )


def transcribe(path: Path) -> tuple[str, float | None]:
    if os.getenv("CALLSHIELD_ASR_ENABLED", "false").lower() != "true":
        raise RuntimeError("ASR disabled")
    with _LOCK:
        parts, _ = _model().transcribe(str(path), vad_filter=True, beam_size=1)
        parts = list(parts)
    text = " ".join(part.text.strip() for part in parts).strip()
    # Whisper log-probability is a model proxy, not a calibrated fraud/ASR accuracy.
    confidence = (
        sum(math.exp(min(0, part.avg_logprob)) for part in parts) / len(parts)
        if parts
        else None
    )
    return text, confidence
