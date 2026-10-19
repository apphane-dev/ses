"""Tests for the audio8-TTS ONNX adapter.

Pure parts (text normalization, sampling, chunk planning) are tested with
numpy + the tokenizer only — no model download, no network, per the repo
testing policy. The end-to-end synthesis test is opt-in via
SES_AUDIO8_E2E=1 because it loads a ~437 MB model.
"""

import os

import numpy as np
import pytest

from ses.tts.audio8 import clean_text, format_reference_text, plan_chunks, sample_token


# ── text normalization ───────────────────────────────────────────────────────


def test_clean_text_strips_control_chars_and_collapses_whitespace():
    assert clean_text("\x00 Hello   world \n\n") == "Hello world"
    assert clean_text("  multiple\tspaces\tand\nnewlines  ") == "multiple spaces and newlines"


def test_clean_text_joins_cjk_lines_without_space():
    assert clean_text("你好\n世界") == "你好世界"
    assert clean_text("你好\nworld") == "你好 world"


def test_clean_text_empty():
    assert clean_text("") == ""
    assert clean_text("  \n\t ") == ""
    assert clean_text("\x00\x01") == ""


def test_format_reference_text_adds_speaker_tag():
    assert format_reference_text("hello") == "<|speaker:0|>hello"
    assert format_reference_text("<|speaker:2|>hello") == "<|speaker:2|>hello"


# ── sampling ─────────────────────────────────────────────────────────────────


def test_sample_token_greedy_when_one_option():
    rng = np.random.default_rng(0)
    logits = np.array([-10.0, 10.0, -10.0], dtype=np.float32)
    assert sample_token(logits, 0.7, 0.9, 50, rng) == 1


def test_sample_token_gumbel_max_reproducible():
    logits = np.random.default_rng(1).normal(size=1000).astype(np.float32)
    a = sample_token(logits, 0.7, 0.9, 50, np.random.default_rng(0))
    b = sample_token(logits, 0.7, 0.9, 50, np.random.default_rng(0))
    assert a == b


def test_sample_token_gumbel_max_not_biased_toward_eos():
    # The vendor regression case: with only two options, a -log(U) shortcut
    # draws index 1 at this seed; correct Gumbel-max draws index 0.
    result = sample_token(
        np.asarray([0.0, 1.0], dtype=np.float32),
        temperature=1.0,
        top_p=1.0,
        top_k=2,
        rng=np.random.default_rng(0),
    )
    assert result == 0


def test_sample_token_rejects_non_finite():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        sample_token(np.full(8, np.nan), 0.7, 0.9, 50, rng)
    with pytest.raises(ValueError):
        sample_token(np.array([], dtype=np.float32), 0.7, 0.9, 50, rng)


# ── chunk planning ───────────────────────────────────────────────────────────


def _fake_token_count(word_per_token: bool = False):
    def count(text: str) -> int:
        return len(text.split()) if word_per_token else len(text)

    return count


def test_plan_chunks_keeps_short_text_whole():
    pieces = plan_chunks("Hello world.", _fake_token_count(), prompt_overhead=100, max_seq_len=2048)
    assert pieces == ["Hello world."]


def test_plan_chunks_splits_oversized_text():
    sentence = "This is a fairly long test sentence about many topics. "
    text = sentence * 60  # ~3600 chars, way past the char cap
    pieces = plan_chunks(text, _fake_token_count(), prompt_overhead=100, max_seq_len=2048)
    assert len(pieces) > 1
    assert " ".join(pieces).split() == text.split()  # no words lost
    for piece in pieces:
        assert len(piece) <= 240  # ses.chunking default cap respected


def test_plan_chunks_respects_token_budget():
    # pretend 1 token per char with a tight window
    pieces = plan_chunks(
        "word " * 500,
        _fake_token_count(),
        prompt_overhead=1500,
        max_seq_len=2048,
        min_new_tokens=64,
    )
    assert len(pieces) > 1
    for piece in pieces:
        assert len(piece) <= 2048 - 1500 - 64


def test_plan_chunks_rejects_impossible_budget():
    with pytest.raises(ValueError):
        plan_chunks("Hello.", _fake_token_count(), prompt_overhead=2000, max_seq_len=2048)


def test_plan_chunks_empty_text():
    assert plan_chunks("", _fake_token_count(), prompt_overhead=100, max_seq_len=2048) == []


# ── engine Protocol conformance (no model load) ──────────────────────────────


def test_engine_import_is_light():
    """Importing the adapter module must not pull onnxruntime/torch/hub."""
    import ses.tts.audio8 as mod

    assert "onnxruntime" not in vars(mod)
    assert "torch" not in vars(mod)
    assert "huggingface_hub" not in vars(mod)


def test_engine_synthesize_rejects_empty_text_without_loading():
    """Empty text fails fast and cleanly — before any model load/download."""
    from ses.config import PipelineConfig
    from ses.samples import VoiceSample
    from ses.tts.audio8 import Audio8TTSEngine

    engine = Audio8TTSEngine(
        VoiceSample(name="v", audio=__import__("pathlib").Path("v.wav"), transcript=None),
        PipelineConfig(),
    )
    with pytest.raises(ValueError, match="empty"):
        engine.synthesize("   \n\t ", None)  # sample unused before the guard
    assert engine._slow_sess is None  # nothing was loaded


def test_engine_close_is_idempotent():
    from ses.config import PipelineConfig
    from ses.samples import VoiceSample
    from ses.tts.audio8 import Audio8TTSEngine

    engine = Audio8TTSEngine(
        VoiceSample(name="v", audio=__import__("pathlib").Path("v.wav"), transcript=None),
        PipelineConfig(),
    )
    engine.close()
    engine.close()


# ── end-to-end (opt-in: SES_AUDIO8_E2E=1, downloads/loads ~437 MB) ───────────


@pytest.fixture()
def _engine():
    import os
    from pathlib import Path

    from ses.config import PipelineConfig
    from ses.samples import VoiceSample
    from ses.tts.audio8 import Audio8TTSEngine

    engine = Audio8TTSEngine(
        VoiceSample(name="default", audio=Path("default.wav"), transcript=None),
        PipelineConfig(),
    )
    yield engine
    engine.close()


@pytest.mark.skipif(
    os.environ.get("SES_AUDIO8_E2E") != "1",
    reason="loads the real 437 MB audio8 model — set SES_AUDIO8_E2E=1 to run",
)
def test_synthesize_short_sentence_returns_non_silent_audio(_engine):
    audio, sr = _engine.synthesize("Hello world, this is a simple test.", None)

    assert isinstance(audio, np.ndarray) and audio.ndim == 1
    assert sr == 44100
    assert audio.dtype == np.float32
    assert audio.size > sr // 2  # at least half a second of audio
    rms = float(np.sqrt(np.mean(audio**2)))
    assert rms > 1e-3  # non-silent
    assert float(np.max(np.abs(audio))) <= 1.0
