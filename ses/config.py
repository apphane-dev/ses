"""Every tunable constant in one frozen place. No global state."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    chunk_size: int = 240  # chars — hard cap; most sentences are well under this
    silence_between_slides_ms: int = 600
    silence_between_paragraphs_ms: int = 360  # pause between paragraph groups within a slide
    silence_between_sentences_ms: int = 170   # short breath between sentences within a paragraph
    slide_lead_in_ms: int = 150   # silence prepended to each slide WAV for a safe, natural start
    max_acceptable_pause_ms: int = 850  # internal pauses longer than this trigger a re-render
    max_quality_retries: int = 2  # how many times to re-render for quality issues
    target_rms: float = 0.08  # RMS normalization target for consistent paragraph volumes
    sentence_fade_in_ms: int = 8    # soft fade-in at each sentence start to prevent onset clicks
    sentence_fade_out_ms: int = 25  # soft fade-out at each sentence end to prevent trailing clicks
    para_fade_in_ms: int = 10   # soft fade-in at paragraph start to prevent clicks (short to preserve opening phonemes)
    para_fade_out_ms: int = 80  # soft fade-out at paragraph end to prevent cut syllables
    chunk_timeout_sec: int = 180
    chunk_retries: int = 2
    enhance_audio: bool = True   # run LavaSR speech enhancement as post-processing
    language: str = "English"
    temperature: float = 0.7
