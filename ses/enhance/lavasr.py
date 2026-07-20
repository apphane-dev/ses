"""LavaSR speech-enhancement adapter with added-noise fallback (reference impl).

Heavy imports (torch, LavaSR) are deferred into methods so importing this
module requires only numpy + soundfile. The model is loaded lazily on the
first `enhance` call.
"""

import gc
import os
import tempfile
import warnings

import numpy as np
import soundfile as sf

from ses.audio.dsp import resample_to
from ses.audio.quality import enhancement_added_noise
from ses.config import PipelineConfig
from ses.logging import log

LAVASR_MODEL_ID = "YatharthS/LavaSR"

# Suppress noisy LavaSR/vocos FutureWarnings.
warnings.filterwarnings("ignore", category=FutureWarning, module="LavaSR")

LAVASR_OUTPUT_SR = 48000


class LavaSREnhancer:
    """Wraps LavaSR load + enhance with added-noise detection and raw-upsample fallback."""

    def __init__(self, config: PipelineConfig, show_backend_warnings: bool = False):
        self.config = config
        self.show_backend_warnings = show_backend_warnings
        self._model = None
        self._device: str | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch

        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        log(f"🔊 Loading LavaSR ({LAVASR_MODEL_ID})...")
        from LavaSR.model import LavaEnhance2

        self._model = LavaEnhance2(LAVASR_MODEL_ID, self._device)
        log("   ✅ LavaSR loaded")

    def enhance(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
        self._ensure_loaded()

        # LavaSR loads audio from a path, so stage the raw render to a temp file.
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tmp_path = tf.name
            sf.write(tmp_path, audio, sr)
            input_audio, _ = self._model.load_audio(tmp_path)
            enhanced = self._model.enhance(input_audio).cpu().numpy().squeeze()
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        # LavaSR sometimes hallucinates high-frequency hash into quiet regions
        # (audible as "corrupted" buzzing). Detect it by comparing zero-crossing
        # rate against the clean raw; if enhancement added significant noise,
        # discard it and upsample the raw instead.
        if enhancement_added_noise(audio, sr, enhanced, LAVASR_OUTPUT_SR):
            enhanced = resample_to(audio, sr, LAVASR_OUTPUT_SR)
            log(f"  ⚠️  enhancement added noise — using upsampled raw instead")
        return enhanced, LAVASR_OUTPUT_SR

    def close(self) -> None:
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
