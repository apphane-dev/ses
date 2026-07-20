"""Join section WAVs with configured silence."""

from pathlib import Path

import numpy as np
import soundfile as sf

from ses.logging import log


def concatenate_slides(audio_files: list[Path], output: Path, silence_ms: int = 600) -> float:
    """Join per-slide WAVs with silence. Returns total duration in seconds."""
    # Read first file to get sample rate
    _, first_sr = sf.read(str(audio_files[0]), dtype='float32')
    silence_samples = int(first_sr * silence_ms / 1000)
    silence = np.zeros(silence_samples, dtype=np.float32)

    parts: list[np.ndarray] = []
    for f in audio_files:
        data, _ = sf.read(str(f), dtype='float32')
        parts.append(data)
        parts.append(silence)

    full = np.concatenate(parts)
    sf.write(str(output), full, first_sr)
    duration = len(full) / first_sr
    log(f"✅ Full voiceover: {output.name} ({duration:.1f}s / {duration/60:.1f}min)")
    return duration
