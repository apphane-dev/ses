"""Tests for ses.chunking.split_into_chunks."""

from ses.chunking import split_into_chunks


def test_one_sentence_per_chunk():
    # Each sentence is comfortably over the 16-char merge threshold, so each
    # gets its own chunk.
    text = (
        "This is the first standalone sentence. "
        "Here is a second standalone sentence! "
        "And this is the third standalone sentence?"
    )
    chunks = split_into_chunks(text)
    assert len(chunks) == 3
    assert chunks[0] == "This is the first standalone sentence."
    assert chunks[1] == "Here is a second standalone sentence!"
    assert chunks[2] == "And this is the third standalone sentence?"


def test_multi_sentence_splits_on_punctuation():
    text = (
        "The first sentence is nice and long. "
        "The second sentence is also nicely long! "
        "Will the third sentence be long enough? "
        "Definitely the fourth is long enough."
    )
    chunks = split_into_chunks(text)
    assert len(chunks) == 4
    assert chunks[0].startswith("The first sentence")
    assert chunks[1].startswith("The second sentence")
    assert chunks[2].startswith("Will the third sentence")
    assert chunks[3].startswith("Definitely the fourth")


def test_tiny_trailing_fragment_merges_into_previous():
    text = "This is a normal full sentence that stands on its own. Thank you."
    chunks = split_into_chunks(text)
    # "Thank you." is a tiny (< 16 char) trailing fragment and must merge,
    # not get its own clipped TTS pass.
    assert len(chunks) == 1
    assert chunks[0].endswith("Thank you.")


def test_overlong_sentence_splits_at_clause_boundaries():
    max_chars = 60
    # A single long sentence with clause punctuation; well over max_chars.
    sentence = (
        "This is a deliberately long sentence that exceeds the cap; "
        "it contains several clauses — like this one, and this one too — "
        "so that the splitter must break it into smaller pieces."
    )
    assert len(sentence) > max_chars
    chunks = split_into_chunks(sentence, max_chars=max_chars)
    assert len(chunks) >= 2
    # No chunk may exceed the cap.
    for c in chunks:
        assert len(c) <= max_chars
    # Reassembling should preserve the substantive words.
    joined = " ".join(chunks)
    for word in ("deliberately", "exceeds", "clauses", "pieces"):
        assert word in joined
