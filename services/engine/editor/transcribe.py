"""Transcription provider abstraction (for automatic subtitles).

`SherpaOnnxTransducerProvider` runs fully offline with a free model (e.g. NVIDIA Parakeet-TDT via
sherpa-onnx) when `EDITOR_STT_MODEL_DIR` points at a model folder containing encoder/decoder/joiner
.onnx + tokens.txt (see scripts/download_stt_model.py). Without it, `NoTranscription` is used and the
UI states that captions need a speech-to-text model — nothing is faked."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .config import get_settings
from .media.audio import load_mono


class TranscriptionProvider(ABC):
    name = "none"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def words(self, path: Path, start: float, duration: float) -> list[dict]:
        """Return [{w, t0, t1}] in *source* seconds."""


class NoTranscription(TranscriptionProvider):
    def available(self) -> bool:
        return False

    def words(self, path, start, duration):
        return []


class SherpaOnnxTransducerProvider(TranscriptionProvider):
    name = "sherpa_onnx"
    _rec = None

    def __init__(self, model_dir: Path | None):
        self.dir = model_dir

    def available(self) -> bool:
        if not self.dir or not (self.dir / "tokens.txt").exists():
            return False
        try:
            import sherpa_onnx  # noqa: F401
        except ImportError:
            return False
        return True

    def _recognizer(self):
        if SherpaOnnxTransducerProvider._rec is None:
            import sherpa_onnx

            d = self.dir
            pick = lambda stem: str(next(iter(sorted(d.glob(f"{stem}*.onnx")))))
            SherpaOnnxTransducerProvider._rec = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=pick("encoder"), decoder=pick("decoder"), joiner=pick("joiner"), tokens=str(d / "tokens.txt"),
                model_type="nemo_transducer", num_threads=2)
        return SherpaOnnxTransducerProvider._rec

    def words(self, path: Path, start: float, duration: float) -> list[dict]:
        y = load_mono(path, 16000, start, duration)
        if len(y) < 1600:
            return []
        rec = self._recognizer()
        s = rec.create_stream()
        s.accept_waveform(16000, y)
        rec.decode_stream(s)
        r = s.result
        words: list[dict] = []
        for tok, ts in zip(r.tokens, r.timestamps):
            if tok.startswith(" ") or not words:
                words.append({"w": tok.strip(), "t0": start + ts, "t1": start + ts + 0.25})
            else:
                words[-1]["w"] += tok
        for a, b in zip(words, words[1:]):
            a["t1"] = min(b["t0"], a["t0"] + 1.2)
        return [w for w in words if w["w"]]


def get_transcriber() -> TranscriptionProvider:
    p = SherpaOnnxTransducerProvider(get_settings().stt_model_dir)
    return p if p.available() else NoTranscription()
