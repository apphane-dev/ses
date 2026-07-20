"""Decode arbitrary audio sample files to a mono WAV the TTS engine can read.

Voice samples don't have to be WAV. libsndfile (via soundfile) decodes WAV,
FLAC, OGG, AIFF, and MP3 directly; anything it can't handle (e.g. m4a/aac)
falls back to the sox CLI, which `ses` already depends on.
"""

import shutil
import subprocess
from pathlib import Path

import soundfile as sf

# Extensions accepted as voice-sample inputs, in preference order (used both
# for discovery and to pick one file when several share a stem).
AUDIO_EXTS = (".wav", ".flac", ".ogg", ".oga", ".aiff", ".aif", ".mp3", ".m4a", ".aac", ".opus")


def ext_rank(suffix: str) -> int:
    """Preference rank for an extension; lower wins. Unknown → last."""
    s = suffix.lower()
    return AUDIO_EXTS.index(s) if s in AUDIO_EXTS else len(AUDIO_EXTS)


def to_mono_wav(src: Path, dst: Path) -> None:
    """Write `src` (any supported format) to `dst` as a mono WAV.

    Tries libsndfile first, then the sox CLI for formats it can't decode.
    """
    try:
        audio, sr = sf.read(str(src), dtype="float32", always_2d=True)
        sf.write(str(dst), audio.mean(axis=1), sr)
        return
    except Exception:
        pass
    if shutil.which("sox") is None:
        raise RuntimeError(
            f"Cannot decode {src.name}: libsndfile could not read it and sox is not installed."
        )
    subprocess.run(["sox", str(src), "-c", "1", str(dst)], check=True, capture_output=True)
