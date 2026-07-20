"""Quality gates: garble detection, long-pause detection, hash detection."""

import numpy as np

from ses.audio.dsp import voiced_rms


def chunk_is_garbled(audio: np.ndarray, sr: int) -> bool:
    """Detect a bad TTS generation: a SUSTAINED loud burst above the sentence body.

    Brief peaks are normal (plosives push crest factor to ~5–7 even in clean
    speech), so peak alone is a poor signal. The corruption signature is a
    loud region held for a few hundred ms: measured sustained-RMS ratio ~1.8×
    the voiced level vs ~1.3–1.6× for clean sentences. Flag when a 300 ms
    window stays well above the chunk's own voiced level.
    """
    voiced = voiced_rms(audio, sr)
    if voiced < 1e-6:
        return False
    win = int(sr * 0.3)
    if len(audio) < win:
        return False
    step = max(1, win // 2)
    sustained_max = max(
        float(np.sqrt(np.mean(audio[i:i + win] ** 2)))
        for i in range(0, len(audio) - win, step)
    )
    # Require BOTH a high sustained/voiced ratio AND an absolute loudness floor:
    # a quiet chunk can have a high ratio without being the loud-burst defect we
    # care about. The real corruption sits well above normal speech RMS (~0.08).
    return sustained_max > 0.22 and (sustained_max / voiced) > 1.7


def hashy_window_count(audio: np.ndarray, sr: int, win_ms: float = 200,
                       voiced_rms: float = 0.035, zcr_hash: float = 0.35) -> int:
    """Count voiced windows whose zero-crossing rate is hashy (≫ normal speech).

    Normal voiced speech ZCR is ~0.02–0.15 even with sibilance. LavaSR noise
    injection pushes localized windows to 0.4–0.6. Counting such windows
    catches LOCALIZED corruption that a whole-file mean would dilute away.
    """
    win = max(1, int(sr * win_ms / 1000))
    count = 0
    for i in range(0, max(1, len(audio) - win), win):
        seg = audio[i:i + win]
        if np.sqrt(np.mean(seg ** 2)) > voiced_rms:
            if np.mean(np.abs(np.diff(np.sign(seg)))) / 2 > zcr_hash:
                count += 1
    return count


def enhancement_added_noise(raw: np.ndarray, raw_sr: int,
                            enhanced: np.ndarray, enh_sr: int) -> bool:
    """True if enhancement injected localized high-frequency hash absent in raw.

    Compares the count of hashy voiced windows. The raw TTS output is clean
    (≈0 hashy windows); when LavaSR corrupts quiet regions, several windows
    spike. Flag when the enhanced has clearly more than the raw.
    """
    raw_hash = hashy_window_count(raw, raw_sr)
    enh_hash = hashy_window_count(enhanced, enh_sr)
    # The raw is essentially always clean (0). Any hash the enhancement adds is
    # an artifact, so fall back as soon as it introduces ≥1 hashy window beyond
    # the raw. (A clean enhancement adds 0.)
    return enh_hash > raw_hash and enh_hash >= 1


def detect_long_pauses(audio: np.ndarray, sr: int, max_pause_ms: int = 850) -> list[tuple[float, float]]:
    """Scan audio for internal silent regions longer than max_pause_ms.

    Returns a list of (start_sec, duration_sec) for each detected pause.
    Used as a quality gate: if any are found, the slide should be re-rendered.
    """
    max_pause = int(sr * max_pause_ms / 1000)
    win = int(sr * 0.025)  # 25ms windows
    thresh = 0.005  # float32 amplitude threshold
    n = len(audio)
    if n < max_pause:
        return []

    pauses: list[tuple[float, float]] = []
    silent_start: int | None = None
    for i in range(0, n - win, win):
        chunk_max = np.max(np.abs(audio[i:i + win]))
        if chunk_max < thresh:
            if silent_start is None:
                silent_start = i
        else:
            if silent_start is not None:
                length = i - silent_start
                if length > max_pause:
                    pauses.append((silent_start / sr, length / sr))
                silent_start = None
    if silent_start is not None:
        length = n - silent_start
        if length > max_pause:
            pauses.append((silent_start / sr, length / sr))
    return pauses
