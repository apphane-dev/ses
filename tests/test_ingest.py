"""Tests for ses.audio.ingest — format tolerance and mono transcoding."""

import numpy as np
import soundfile as sf

from ses.audio.ingest import AUDIO_EXTS, ext_rank, to_mono_wav


def test_ext_rank_prefers_wav_and_orders_known_formats():
    assert ext_rank(".wav") < ext_rank(".mp3")
    assert ext_rank(".WAV") == ext_rank(".wav")   # case-insensitive
    assert ext_rank(".xyz") == len(AUDIO_EXTS)     # unknown sorts last


def test_to_mono_wav_downmixes_stereo_flac(tmp_path):
    # Distinct L/R channels so a mono mixdown is verifiable.
    n = 2400
    left = np.linspace(-0.5, 0.5, n, dtype=np.float32)
    right = np.linspace(0.5, -0.5, n, dtype=np.float32)
    stereo = np.stack([left, right], axis=1)
    src = tmp_path / "stereo.flac"
    sf.write(str(src), stereo, 24000)

    dst = tmp_path / "out.wav"
    to_mono_wav(src, dst)

    mono, sr = sf.read(str(dst), dtype="float32")
    assert sr == 24000
    assert mono.ndim == 1
    assert np.allclose(mono, (left + right) / 2, atol=1e-3)


def test_to_mono_wav_passes_through_mono(tmp_path):
    n = 1200
    tone = (0.1 * np.sin(2 * np.pi * 220 * np.arange(n) / 24000)).astype(np.float32)
    src = tmp_path / "mono.ogg"
    sf.write(str(src), tone, 24000)

    dst = tmp_path / "out.wav"
    to_mono_wav(src, dst)
    mono, sr = sf.read(str(dst), dtype="float32")
    assert sr == 24000
    assert mono.ndim == 1
    assert len(mono) == n
