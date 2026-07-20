"""Tests for ses.audio.quality — pure-numpy quality gates."""

import numpy as np

from ses.audio.quality import (
    chunk_is_garbled,
    detect_long_pauses,
    enhancement_added_noise,
    hashy_window_count,
)


SR = 22050


def _tone(freq=200.0, dur=3.0, amp=0.08, sr=SR):
    t = np.arange(int(sr * dur)) / sr
    # A slow amplitude modulation makes it "speech-like" in loudness profile.
    env = 0.8 + 0.2 * np.sin(2 * np.pi * 2.0 * t)
    return (amp * env * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _silence(dur, sr=SR):
    return np.zeros(int(sr * dur), dtype=np.float32)


def test_detect_long_pauses_finds_1_2s_misses_0_4s():
    # Two pauses: 1.2 s (above the 850 ms threshold) and 0.4 s (below it).
    audio = np.concatenate([
        _tone(dur=0.5),
        _silence(1.2),   # detected
        _tone(dur=0.5),
        _silence(0.4),   # not detected
        _tone(dur=0.5),
    ])
    pauses = detect_long_pauses(audio, sr=SR, max_pause_ms=850)
    durations = [round(d, 1) for _, d in pauses]
    assert any(d > 1.0 for d in durations)   # the 1.2 s pause
    assert not any(d > 0.8 for d in durations if d <= 1.0)  # 0.4 s pause absent


def test_detect_long_pauses_clean_signal_has_no_pauses():
    audio = _tone(dur=2.0)
    assert detect_long_pauses(audio, sr=SR) == []


def test_chunk_is_garbled_clean_modulated_tone_is_false():
    audio = _tone(freq=200.0, dur=2.5, amp=0.08)
    assert chunk_is_garbled(audio, sr=SR) is False


def test_chunk_is_garbled_sustained_loud_burst_is_true():
    base = _tone(freq=200.0, dur=2.5, amp=0.08)
    # Inject a sustained (~400 ms) loud burst at amplitude ~0.5.
    burst_len = int(SR * 0.4)
    t = np.arange(burst_len) / SR
    burst = (0.5 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
    start = len(base) // 3
    garbled = base.copy()
    garbled[start:start + burst_len] += burst
    assert chunk_is_garbled(garbled, sr=SR) is True


def test_hashy_window_count_low_for_tone_high_for_noise():
    t = np.arange(int(SR * 2.0)) / SR
    tone = (0.08 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    noise = np.random.RandomState(0).uniform(-1, 1, len(t)).astype(np.float32)
    noise *= (0.08 / (np.sqrt(np.mean(noise ** 2)) + 1e-9))  # scale to voiced level
    low = hashy_window_count(tone, sr=SR)
    high = hashy_window_count(noise, sr=SR)
    assert low <= 1
    assert high > low
    assert high > 5


def test_enhancement_added_noise_true_when_enhanced_is_noise_vs_raw_tone():
    t = np.arange(int(SR * 2.0)) / SR
    raw = (0.08 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    rng = np.random.RandomState(1)
    enhanced = rng.uniform(-1, 1, len(t)).astype(np.float32)
    enhanced *= (0.08 / (np.sqrt(np.mean(enhanced ** 2)) + 1e-9))
    assert enhancement_added_noise(raw, SR, enhanced, SR) is True


def test_enhancement_added_noise_false_when_both_clean():
    t = np.arange(int(SR * 2.0)) / SR
    raw = (0.08 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    enhanced = (0.07 * np.sin(2 * np.pi * 120 * t)).astype(np.float32)
    assert enhancement_added_noise(raw, SR, enhanced, SR) is False
