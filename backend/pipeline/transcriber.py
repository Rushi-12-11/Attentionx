from __future__ import annotations
import os
from faster_whisper import WhisperModel

_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"[Transcriber] Loading faster-whisper '{_MODEL_SIZE}' model…")
        _model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
        print(f"[Transcriber] Model loaded.")
    return _model


def transcribe(video_path: str) -> tuple[str, list[dict]]:
    model = _get_model()
    print(f"[Transcriber] Transcribing: {video_path}")

    # FIX: force-consume the generator with list() so words aren't lazily dropped
    segments, info = model.transcribe(video_path, word_timestamps=True)
    segments = list(segments)

    print(f"[Transcriber] Detected language: {info.language} (probability: {info.language_probability:.2f})")

    full_text     = ""
    word_segments = []

    for seg in segments:
        full_text += seg.text
        if seg.words:
            for word in seg.words:
                word_segments.append({
                    "start": float(word.start),
                    "end":   float(word.end),
                    "text":  word.word.strip(),
                })

    print(f"[Transcriber] Done. {len(word_segments)} words, {len(full_text)} chars.")
    return full_text.strip(), word_segments