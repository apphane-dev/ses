"""DSP: trim, fades, RMS normalize, loudness leveling, resample."""

import numpy as np


def voiced_rms(audio: np.ndarray, sr: int, thresh: float = 0.02) -> float:
    """RMS over voiced windows only, so silence/pauses don't skew loudness."""
    win = max(1, int(sr * 0.02))
    levels = np.array([
        np.sqrt(np.mean(audio[i:i + win] ** 2))
        for i in range(0, max(1, len(audio) - win), win)
    ])
    voiced = levels[levels > thresh]
    if len(voiced) == 0:
        return float(np.sqrt(np.mean(audio ** 2)))
    return float(np.median(voiced))


def normalize_rms(audio: np.ndarray, sr: int | None = None, target_rms: float = 0.08) -> np.ndarray:
    """Normalize to a target loudness based on VOICED level for consistent volume.

    Using the voiced median (not whole-signal RMS) keeps every sentence at the
    same perceived loudness regardless of how much internal pause it contains —
    which is what stops sentences from starting too quietly.
    """
    # Remove DC offset first to prevent clicks at boundaries
    audio = audio - np.mean(audio)
    ref = voiced_rms(audio, sr) if sr else np.sqrt(np.mean(audio ** 2))
    if ref < 1e-8:
        return audio
    gain = target_rms / ref
    # Prevent clipping: cap gain so peaks stay below 0.95
    peak = np.max(np.abs(audio))
    max_gain = 0.95 / peak if peak > 1e-8 else gain
    gain = min(gain, max_gain)
    return audio * gain


def level_loudness(audio: np.ndarray, sr: int, target_rms: float = 0.08,
                   win_ms: float = 400, smooth_ms: float = 1500,
                   max_gain: float = 2.0) -> np.ndarray:
    """Even out loudness drift between sentences WITHIN a slide (post-enhancement).

    Per-sentence normalization happens before LavaSR enhancement, which then
    applies its own non-uniform gain — re-introducing volume variation. This
    runs last, on the final audio.

    Approach: measure short-window (≈400 ms, syllable-scale) loudness, derive a
    corrective gain toward target only where there is voice, hold gain flat
    through pauses (never amplify silence), then smooth the gain over ≈1.5 s so
    it tracks sentence-to-sentence drift without pumping inside words.
    """
    n = len(audio)
    if n < sr:  # too short to bother
        return audio
    win = max(1, int(sr * win_ms / 1000))
    hop = max(1, win // 4)

    centres = np.arange(0, n, hop)
    local_rms = np.empty(len(centres), dtype=np.float32)
    for k, c in enumerate(centres):
        seg = audio[max(0, c - win // 2):min(n, c + win // 2)]
        local_rms[k] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0.0

    # Corrective gain only on voiced hops; hold last gain through quiet gaps so
    # pauses keep the surrounding speech's gain instead of being boosted.
    voiced_floor = max(1e-4, target_rms * 0.35)
    gains = np.ones(len(centres), dtype=np.float32)
    last = 1.0
    for k, r in enumerate(local_rms):
        if r > voiced_floor:
            last = float(np.clip(target_rms / r, 1.0 / max_gain, max_gain))
        gains[k] = last

    # Burst suppression: where the SHORT-window level runs hot (a localized
    # loud-burst defect), pull the corrective gain down extra BEFORE smoothing,
    # so the final envelope dips smoothly through the burst (no per-sample knee
    # → no clicks).
    burst_ceiling = target_rms * 2.0
    hot = local_rms > burst_ceiling
    gains[hot] = np.minimum(gains[hot], burst_ceiling / local_rms[hot])

    # Smooth the gain envelope over a fixed ≈smooth_ms window (sentence scale).
    smooth_n = max(1, int((smooth_ms / 1000) * sr / hop))
    kernel = np.ones(smooth_n, dtype=np.float32) / smooth_n
    gains = np.convolve(gains, kernel, mode="same")

    gain_curve = np.interp(np.arange(n), centres, gains).astype(np.float32)
    out = audio * gain_curve

    peak = float(np.max(np.abs(out)))
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def resample_to(audio: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    """Linear resample (good enough for an upsample fallback)."""
    if sr_from == sr_to:
        return audio.astype(np.float32)
    n_to = int(round(len(audio) * sr_to / sr_from))
    x_old = np.linspace(0.0, 1.0, len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, n_to, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def apply_edge_fades(audio: np.ndarray, sr: int, fade_in_ms: float, fade_out_ms: float) -> np.ndarray:
    """Apply soft fade-in/fade-out to avoid abrupt edges (clicks) at boundaries."""
    fade_in_samples = int(sr * fade_in_ms / 1000)
    fade_out_samples = int(sr * fade_out_ms / 1000)
    result = audio.copy()
    if fade_in_samples > 0 and len(result) > fade_in_samples:
        ramp = np.linspace(0.0, 1.0, fade_in_samples, dtype=np.float32)
        result[:fade_in_samples] *= ramp
    if fade_out_samples > 0 and len(result) > fade_out_samples:
        ramp = np.linspace(1.0, 0.0, fade_out_samples, dtype=np.float32)
        result[-fade_out_samples:] *= ramp
    return result


def apply_paragraph_fades(audio: np.ndarray, sr: int, fade_in_ms: float = 10,
                          fade_out_ms: float = 80) -> np.ndarray:
    """Apply soft fade-in/fade-out to avoid abrupt edges at paragraph boundaries."""
    return apply_edge_fades(audio, sr, fade_in_ms, fade_out_ms)


def trim_edge_silence(audio: np.ndarray, sr: int, thresh: float = 0.006,
                      lead_keep_ms: float = 45, tail_keep_ms: float = 110) -> np.ndarray:
    """Trim leading/trailing silence WITHOUT clipping soft consonants.

    Trailing fricatives/plosives ("ship", "thank", "English", "grammar") carry
    very little energy, so an aggressive trim eats them and the word sounds cut.
    We use a low threshold and a generous TAIL margin (≈110 ms) so the final
    consonant and its natural decay survive; the leading margin can be smaller
    since onsets are louder. Returns input unchanged if effectively all silence.
    """
    win = max(1, int(sr * 0.01))  # 10ms windows
    n = len(audio)
    if n < win * 2:
        return audio
    lead_keep = int(sr * lead_keep_ms / 1000)
    tail_keep = int(sr * tail_keep_ms / 1000)

    start = 0
    for i in range(0, n - win, win):
        if np.max(np.abs(audio[i:i + win])) >= thresh:
            start = max(0, i - lead_keep)
            break
    else:
        return audio  # all silence — leave as-is

    end = n
    for i in range(n - win, 0, -win):
        if np.max(np.abs(audio[i:i + win])) >= thresh:
            end = min(n, i + win + tail_keep)
            break
    if end <= start:
        return audio
    return audio[start:end]
