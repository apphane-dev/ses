"""Tests for ses.samples — discovery, transcript pairing, bundled fallback."""

from pathlib import Path

import numpy as np
import soundfile as sf

from ses.samples import bundled_voices_dir, find_samples


def _write_wav(path: Path) -> None:
    sf.write(str(path), np.zeros(1200, dtype=np.float32), 24000)


def test_find_samples_pairs_transcripts(tmp_path):
    _write_wav(tmp_path / "a.wav")
    (tmp_path / "a.txt").write_text("hello")
    _write_wav(tmp_path / "b.wav")  # no transcript

    samples = {s.name: s for s in find_samples(tmp_path)}
    assert set(samples) == {"a", "b"}
    assert samples["a"].transcript == tmp_path / "a.txt"
    assert samples["b"].transcript is None


def test_find_samples_accepts_non_wav_formats(tmp_path):
    _write_wav(tmp_path / "w.wav")
    sf.write(str(tmp_path / "f.flac"), np.zeros(1200, dtype=np.float32), 24000)
    sf.write(str(tmp_path / "o.ogg"), np.zeros(1200, dtype=np.float32), 24000)
    names = {s.name: s.audio.suffix for s in find_samples(tmp_path)}
    assert names == {"w": ".wav", "f": ".flac", "o": ".ogg"}


def test_find_samples_prefers_wav_when_stem_collides(tmp_path):
    _write_wav(tmp_path / "dup.wav")
    sf.write(str(tmp_path / "dup.flac"), np.zeros(1200, dtype=np.float32), 24000)
    samples = find_samples(tmp_path)
    assert len(samples) == 1
    assert samples[0].audio.suffix == ".wav"


def test_find_samples_empty_dir_returns_empty(tmp_path):
    assert find_samples(tmp_path) == []


def test_find_samples_missing_dir_returns_empty(tmp_path):
    assert find_samples(tmp_path / "nope") == []


def test_bundled_voices_dir_resolves():
    # examples/voices/ ships empty; the fallback the CLI relies on must still
    # resolve to it so dropped-in samples get picked up.
    bundled = bundled_voices_dir()
    assert bundled is not None
    assert bundled.name == "voices"
    assert bundled.is_dir()
