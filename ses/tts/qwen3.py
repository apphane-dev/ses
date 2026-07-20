"""Qwen3-TTS voice-clone adapter (reference implementation).

Heavy imports (torch, qwen_tts) are deferred into methods so that merely
importing this module — or the `ses` package — requires only numpy +
soundfile. The model is loaded lazily on the first `synthesize` call.
"""

import contextlib
import gc
import io
import os
import re
import shutil
import sys
import tempfile
import warnings

import numpy as np

from ses.audio.ingest import to_mono_wav
from ses.config import PipelineConfig
from ses.logging import log
from ses.samples import VoiceSample

MODEL_NAME = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

# Suppress noisy PyTorch deprecation warnings emitted during generation.
warnings.filterwarnings("ignore", message=".*torch.cuda.amp.autocast.*")
warnings.filterwarnings("ignore", message=".*was resized since it had shape.*")

_EXPECTED_FLASH_ATTN_WARNING = re.compile(
    r"\n?\*{8}\n"
    r"Warning: flash-attn is not installed\. Will only run the manual PyTorch version\. "
    r"Please install flash-attn for faster inference\.\n"
    r"\*{8}\n ?",
)


def require_native_deps() -> None:
    """Fail early with actionable setup help for native tools qwen-tts expects."""
    if shutil.which("sox") is not None:
        return

    sys.exit(
        "❌ Missing native dependency: sox\n"
        "   qwen-tts imports the Python `sox` package, which shells out to the SoX executable.\n"
        "   Install it once, then rerun this script:\n"
        "\n"
        "     brew install sox\n"
    )


def import_qwen_tts_model(show_backend_warnings: bool = False):
    """Import qwen-tts while hiding the expected non-actionable flash-attn warning on MPS/CPU."""
    if show_backend_warnings:
        from qwen_tts import Qwen3TTSModel
        return Qwen3TTSModel

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        from qwen_tts import Qwen3TTSModel

    _replay_import_output(stdout.getvalue(), sys.stdout)
    _replay_import_output(stderr.getvalue(), sys.stderr)
    return Qwen3TTSModel


def _replay_import_output(text: str, stream) -> None:
    cleaned = _EXPECTED_FLASH_ATTN_WARNING.sub("", text)
    if cleaned.strip():
        print(cleaned, file=stream, end="")


def configure_backend_logging(show_backend_warnings: bool = False) -> None:
    """Hide noisy transformers generation notices unless explicitly requested."""
    if show_backend_warnings:
        return
    try:
        from transformers.utils import logging as hf_logging
        hf_logging.set_verbosity_error()
    except Exception:
        # Logging cleanup should never block voiceover generation.
        pass


class Qwen3TTSEngine:
    """Wraps Qwen3-TTS voice cloning with ICL / x-vector branching and MPS cache management."""

    def __init__(self, sample: VoiceSample, config: PipelineConfig, show_backend_warnings: bool = False):
        self.sample = sample
        self.config = config
        self.show_backend_warnings = show_backend_warnings
        self._model = None
        self._device: str | None = None
        self._ref_wav: str | None = None
        self._ref_tmp: str | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch

        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        log(f"🤖 Loading {MODEL_NAME} on {self._device}...")
        Qwen3TTSModel = import_qwen_tts_model(show_backend_warnings=self.show_backend_warnings)
        configure_backend_logging(show_backend_warnings=self.show_backend_warnings)
        self._model = Qwen3TTSModel.from_pretrained(
            MODEL_NAME,
            device_map=self._device,
            dtype=torch.float32,
            attn_implementation=None,
        )
        log("   ✅ model loaded")

    def _ref_audio_path(self, sample: VoiceSample) -> str:
        """Return a WAV path for the reference sample, transcoding once if needed.

        WAV samples are passed straight through (unchanged, proven path). Any
        other format is decoded to a temporary mono WAV the first time and
        reused for every chunk; the temp file is removed in `close()`.
        """
        if self._ref_wav is not None:
            return self._ref_wav
        if sample.audio.suffix.lower() == ".wav":
            self._ref_wav = str(sample.audio)
            return self._ref_wav
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            self._ref_tmp = tf.name
        log(f"   ↻ decoding reference {sample.audio.name} → temporary WAV")
        to_mono_wav(sample.audio, self._ref_tmp)
        self._ref_wav = self._ref_tmp
        return self._ref_wav

    def synthesize(self, text: str, sample: VoiceSample) -> tuple[np.ndarray, int]:
        import torch

        try:
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            self._ensure_loaded()

            ref_audio = self._ref_audio_path(sample)
            ref_text = sample.transcript.read_text().strip() if sample.transcript else None

            kwargs: dict = dict(
                text=text,
                language=self.config.language,
                ref_audio=ref_audio,
                do_sample=True,
                temperature=self.config.temperature,
            )
            if ref_text:
                kwargs["ref_text"] = ref_text
                kwargs["x_vector_only_mode"] = False
            else:
                kwargs["x_vector_only_mode"] = True

            wavs, sr = self._model.generate_voice_clone(**kwargs)
            candidate = wavs[0]
            del wavs
            return candidate, sr
        finally:
            gc.collect()
            try:
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except Exception:
                pass

    def close(self) -> None:
        if self._ref_tmp is not None:
            try:
                os.unlink(self._ref_tmp)
            except OSError:
                pass
            self._ref_tmp = None
        if self._model is not None:
            del self._model
            self._model = None
        gc.collect()
        try:
            import torch
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass
