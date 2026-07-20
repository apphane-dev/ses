"""Pipeline orchestration: parse → chunk → synth → gate → enhance → level → concat."""

import contextlib
import gc
import shutil
import signal
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from ses.audio.concat import concatenate_slides
from ses.audio.dsp import (
    apply_edge_fades,
    apply_paragraph_fades,
    level_loudness,
    normalize_rms,
    trim_edge_silence,
)
from ses.audio.quality import chunk_is_garbled, detect_long_pauses
from ses.chunking import split_into_chunks
from ses.config import PipelineConfig
from ses.logging import log
from ses.parsing.base import Section, ScriptParser
from ses.parsing.markdown import MarkdownScriptParser
from ses.samples import VoiceSample
from ses.tts.base import TTSEngine
from ses.enhance.base import Enhancer


class ChunkTimeoutError(TimeoutError):
    """Raised when one TTS chunk exceeds the configured deadline."""


@contextlib.contextmanager
def chunk_deadline(seconds: int, label: str):
    """Interrupt a chunk that appears stuck, then let the caller retry it.

    This uses SIGALRM, which works for the normal Python/transformers generation
    path on macOS. If a native Metal/PyTorch call never yields back to Python,
    the signal may only be delivered once that native call returns.
    """
    if seconds <= 0:
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _handle_timeout(_signum, _frame):
        raise ChunkTimeoutError(f"{label} exceeded {seconds}s")

    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _chunk_label(section: Section, chunk_counter: int, total_chunks: int) -> str:
    return f"slide {section.index:02d} chunk {chunk_counter}/{total_chunks}"


def render_section(
    engine: TTSEngine,
    section: Section,
    config: PipelineConfig,
    output_path: Path,
    sample: VoiceSample,
) -> tuple[float, list[tuple[float, float]]] | None:
    """Generate audio for one slide. Returns (duration, pauses) or None on failure."""
    text = section.narration
    icl_label = "ICL" if sample.transcript else "x-vector"
    log(f"[{section.index:02d}] {section.heading}  ({len(text)} chars, {icl_label})")

    # Split into paragraphs, render each with inter-paragraph silence
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    all_audio: list[np.ndarray] = []
    sample_rate: int | None = None
    max_attempts = max(1, config.chunk_retries + 1)
    total_chunks = sum(len(split_into_chunks(p, config.chunk_size)) for p in paragraphs)
    chunk_counter = 0

    for para_idx, para_text in enumerate(paragraphs):
        chunks = split_into_chunks(para_text, config.chunk_size)
        para_audio_parts: list[np.ndarray] = []

        for i, chunk in enumerate(chunks, 1):
            chunk_counter += 1
            chunk_audio: np.ndarray | None = None
            label = _chunk_label(section, chunk_counter, total_chunks)

            for attempt in range(1, max_attempts + 1):
                started = time.monotonic()
                try:
                    log(
                        f"    chunk {chunk_counter}/{total_chunks} attempt {attempt}/{max_attempts} "
                        f"(timeout {config.chunk_timeout_sec}s)..."
                    )
                    with chunk_deadline(config.chunk_timeout_sec, label):
                        candidate, sr = engine.synthesize(chunk, sample)

                    sample_rate = sr
                    elapsed = time.monotonic() - started
                    # Reject garbled generations (loud burst) and retry if budget remains.
                    if chunk_is_garbled(candidate, sr) and attempt < max_attempts:
                        log(
                            f"    chunk {chunk_counter}/{total_chunks} attempt {attempt}/{max_attempts} "
                            f"⚠ garbled loud burst (peak {np.max(np.abs(candidate)):.2f}); re-rolling"
                        )
                        continue
                    chunk_audio = candidate
                    log(f"    chunk {chunk_counter}/{total_chunks} attempt {attempt}/{max_attempts} ✓ ({elapsed:.1f}s)")
                    break
                except KeyboardInterrupt:
                    log(f"    {label} interrupted by user")
                    raise
                except ChunkTimeoutError as e:
                    elapsed = time.monotonic() - started
                    log(f"    {label} attempt {attempt}/{max_attempts} timed out after {elapsed:.1f}s: {e}")
                except Exception as e:
                    elapsed = time.monotonic() - started
                    log(f"    {label} attempt {attempt}/{max_attempts} failed after {elapsed:.1f}s: {e}")

            if chunk_audio is None:
                log(f"  ❌ giving up on {label}; slide not written")
                return None
            # Trim first so normalization sees only speech, then normalize on the
            # VOICED level for consistent loudness, then fade edges to avoid clicks.
            chunk_audio = trim_edge_silence(chunk_audio, sample_rate)
            chunk_audio = normalize_rms(chunk_audio, sample_rate, config.target_rms)
            chunk_audio = apply_edge_fades(
                chunk_audio, sample_rate, config.sentence_fade_in_ms, config.sentence_fade_out_ms
            )
            para_audio_parts.append(chunk_audio)

        # Join sentences with a short silence gap (no speech overlap → no clicks).
        if para_audio_parts:
            gap_samples = int(sample_rate * config.silence_between_sentences_ms / 1000) if sample_rate else 0
            gap = np.zeros(gap_samples, dtype=np.float32) if gap_samples > 0 else None
            joined: list[np.ndarray] = []
            for idx, part in enumerate(para_audio_parts):
                if idx > 0 and gap is not None:
                    joined.append(gap)
                joined.append(part)
            para_full = np.concatenate(joined)
            para_full = apply_paragraph_fades(
                para_full, sample_rate, config.para_fade_in_ms, config.para_fade_out_ms
            )
            all_audio.append(para_full)

        # Insert inter-paragraph silence after each paragraph (except the last)
        if para_idx < len(paragraphs) - 1 and sample_rate is not None:
            para_silence_samples = int(sample_rate * config.silence_between_paragraphs_ms / 1000)
            all_audio.append(np.zeros(para_silence_samples, dtype=np.float32))

    if not all_audio or sample_rate is None:
        log("  ❌ no audio generated")
        return None

    full = np.concatenate(all_audio)

    # Prepend lead-in silence for a safe, natural start
    lead_in_samples = int(sample_rate * config.slide_lead_in_ms / 1000)
    if lead_in_samples > 0:
        full = np.concatenate([np.zeros(lead_in_samples, dtype=np.float32), full])
    sf.write(str(output_path), full, sample_rate)
    duration = len(full) / sample_rate

    # Quality gate: detect internal dead pauses (skip lead-in silence)
    speech_start = lead_in_samples if lead_in_samples > 0 else 0
    pauses = detect_long_pauses(full[speech_start:], sample_rate, config.max_acceptable_pause_ms)
    if pauses:
        for pstart, pdur in pauses:
            log(f"    ⚠️  internal pause at {pstart:.1f}s ({pdur:.1f}s)")

    log(f"  ✅ {duration:.1f}s → {output_path.name}")
    del all_audio, full
    gc.collect()
    return duration, pauses


@dataclass
class SectionResult:
    section: Section
    path: Path
    duration: float


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _enhance_section(out: Path, enhancer: Enhancer) -> float | None:
    """Run enhancement on the section WAV in place. Returns new duration, or None on failure."""
    try:
        raw_path = out.with_suffix('.raw.wav')
        shutil.copy2(str(out), str(raw_path))
        raw_audio, raw_sr = sf.read(str(out), dtype='float32')
        if raw_audio.ndim > 1:
            raw_audio = raw_audio.mean(axis=1)
        enhanced, enh_sr = enhancer.enhance(raw_audio, raw_sr)
        sf.write(str(out), enhanced, enh_sr)
        duration = len(enhanced) / enh_sr
        log(f"  🔊 enhanced → {duration:.1f}s ({enh_sr / 1000:.0f}kHz)  raw: {raw_path.name}")
        return duration
    except Exception as e:
        log(f"  ⚠️  enhancement failed: {e} — keeping original")
        return None


def _level_section(out: Path) -> None:
    """Final loudness leveling runs LAST (after enhancement)."""
    try:
        final_audio, fsr = sf.read(str(out), dtype='float32')
        if final_audio.ndim > 1:
            final_audio = final_audio.mean(axis=1)
        leveled = level_loudness(final_audio, fsr)
        sf.write(str(out), leveled, fsr)
    except Exception as e:
        log(f"  ⚠️  loudness leveling failed: {e} — keeping pre-level audio")


def run_pipeline(
    script_text: str,
    sample: VoiceSample,
    out_dir: Path,
    config: PipelineConfig,
    parser: ScriptParser | None = None,
    engine: TTSEngine | None = None,
    enhancer: Enhancer | None = None,
    sections_filter: int | None = None,
) -> list[SectionResult]:
    """Run the full render pipeline. Returns a list of result records.

    `sections_filter`, when set, renders only the section at that 0-based index.
    `engine` and `enhancer` default to the Qwen3 / LavaSR adapters and are
    constructed lazily so importing this module needs no heavy deps.
    """
    parser = parser or MarkdownScriptParser()
    sections = parser.parse(script_text)

    log(f"Parsed {len(sections)} slide sections")
    for s in sections:
        log(f"  [{s.index:02d}] {s.heading}  ({len(s.narration)} chars)")

    icl_status = f"ICL mode (+ {sample.transcript.name})" if sample.transcript else "x-vector mode (no transcript)"
    log(f"Sample : {sample.audio.name}")
    log(f"Mode   : {icl_status}")

    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"Output : {out_dir}/")

    to_render = [sections[sections_filter]] if sections_filter is not None else sections

    results: list[SectionResult] = []

    try:
        for section in to_render:
            fname = f"slide-{section.index:02d}-{section.slug}.wav"
            out = out_dir / fname

            # Generate with quality-gate retry for internal pauses
            quality_attempts = 0
            result = None
            while True:
                quality_attempts += 1
                result = render_section(engine, section, config, out, sample)
                if result is None:
                    break
                duration, pauses = result
                if not pauses or quality_attempts > config.max_quality_retries:
                    if pauses and quality_attempts > config.max_quality_retries:
                        log(f"  ⚠️  giving up on pause-free render after {quality_attempts} attempts")
                    break
                log(
                    f"  \U0001f504 re-rendering slide {section.index:02d} due to internal pause "
                    f"(attempt {quality_attempts + 1}/{config.max_quality_retries + 1})"
                )

            if result is not None:
                duration = result[0]
                # Enhance immediately — compare while the next slide renders
                if enhancer is not None:
                    new_duration = _enhance_section(out, enhancer)
                    if new_duration is not None:
                        duration = new_duration
                # Final loudness leveling runs LAST (after enhancement) so LavaSR's
                # non-uniform gain can't re-introduce within-slide volume drift.
                _level_section(out)
                results.append(SectionResult(section=section, path=out, duration=duration))
    finally:
        if engine is not None:
            try:
                engine.close()
            except Exception:
                pass
        if enhancer is not None:
            try:
                enhancer.close()
            except Exception:
                pass
        gc.collect()

    # Concatenate full run (only when every section was rendered)
    full_duration: float | None = None
    if sections_filter is None and results:
        all_files = sorted(f for f in out_dir.glob("slide-*.wav") if '.raw.' not in f.name)
        full_duration = concatenate_slides(all_files, out_dir / "full.wav", config.silence_between_slides_ms)

    # ── Summary ──────────────────────────────────────────────────────────────
    log("─" * 62)
    log(f"  Output : {out_dir}/")
    log("─" * 62)
    col_w = max(len(r.section.heading) for r in results) if results else 20
    total = 0.0
    for r in results:
        total += r.duration
        log(f"  [{r.section.index:02d}] {r.section.heading:<{col_w}}  {_fmt(r.duration):>5}  ({r.duration:.1f}s)")
    if results:
        log("─" * 62)
        log(f"  {'Total':<{col_w + 6}}  {_fmt(total):>5}  ({total:.1f}s)")
        if full_duration is not None:
            log(f"  {'Full (with pauses)':<{col_w + 6}}  {_fmt(full_duration):>5}  ({full_duration:.1f}s)")
    log("─" * 62)

    return results
