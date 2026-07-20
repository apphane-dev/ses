"""Tests for ses.audio.dsp — pure-numpy DSP primitives."""

import numpy as np

from ses.audio.dsp import (
    apply_edge_fades,
    normalize_rms,
    resample_to,
    trim_edge_silence,
)


SR = 22050


def _sine(freq=220.0, dur=1.0, amp=0.01, sr=SR):
    t = np.arange(int(sr * dur)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_normalize_rms_brings_quiet_sine_to_target_without_clipping():
    target = 0.08
    quiet = _sine(amp=0.005)
    out = normalize_rms(quiet, sr=SR, target_rms=target)
    # No clipping: peak stays well below 0.95.
    assert np.max(np.abs(out)) <= 0.95
    # Voiced RMS lands near the target (within a small tolerance; the voiced
    # median of a steady sine is close to its true RMS).
    voiced = []
    win = max(1, int(SR * 0.02))
    levels = np.array([
        np.sqrt(np.mean(out[i:i + win] ** 2))
        for i in range(0, max(1, len(out) - win), win)
    ])
    voiced = levels[levels > 0.02]
    med = float(np.median(voiced)) if len(voiced) else float(np.sqrt(np.mean(out ** 2)))
    assert abs(med - target) < 0.015


def test_normalize_rms_preserves_near_silent_input():
    silent = np.zeros(SR, dtype=np.float32)
    out = normalize_rms(silent, sr=SR, target_rms=0.08)
    assert np.allclose(out, 0.0)


def test_trim_edge_silence_removes_long_silence_keeps_margin():
    tone = _sine(dur=0.3, amp=0.05)
    # 0.5 s silence, tone, 0.5 s silence.
    audio = np.concatenate([
        np.zeros(int(SR * 0.5), dtype=np.float32),
        tone,
        np.zeros(int(SR * 0.5), dtype=np.float32),
    ])
    trimmed = trim_edge_silence(audio, sr=SR)
    assert len(trimmed) < len(audio)
    # Generous tail margin (~110 ms) kept after the tone's last voiced window.
    assert len(trimmed) > len(tone)
    # And a smaller but nonzero lead margin kept.
    assert abs(trimmed[0]) < 0.01


def test_trim_edge_silence_all_silence_returned_unchanged():
    audio = np.zeros(SR, dtype=np.float32)
    trimmed = trim_edge_silence(audio, sr=SR)
    assert np.array_equal(trimmed, audio)


def test_apply_edge_fades_starts_and_ends_near_zero():
    tone = _sine(dur=1.0, amp=0.5)
    faded = apply_edge_fades(tone, sr=SR, fade_in_ms=20, fade_out_ms=20)
    assert abs(faded[0]) < 1e-6
    assert abs(faded[-1]) < 1e-6
    # Middle is untouched.
    mid = len(faded) // 2
    assert np.isclose(faded[mid], tone[mid])


def test_resample_to_changes_length_by_sample_rate_ratio():
    sr_from, sr_to = 22050, 48000
    n = int(sr_from * 1.0)
    t = np.arange(n) / sr_from
    audio = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    out = resample_to(audio, sr_from, sr_to)
    expected = int(round(n * sr_to / sr_from))
    assert len(out) == expected
