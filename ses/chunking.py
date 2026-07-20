"""Sentence/clause splitting for stable TTS prosody."""

import re


def _hard_split_long(sentence: str, max_chars: int) -> list[str]:
    """Split an over-long sentence at clause boundaries (—, ;, ,) then at spaces."""
    if len(sentence) <= max_chars:
        return [sentence]
    parts = re.split(r'(\s*[—;,]\s+)', sentence)
    pieces: list[str] = []
    current = ""
    for i in range(0, len(parts), 2):
        seg = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
        if len(current) + len(seg) > max_chars and current:
            pieces.append(current.strip())
            current = seg
        else:
            current += seg
    if current.strip():
        pieces.append(current.strip())
    # Last resort: anything still too long gets chopped on spaces.
    out: list[str] = []
    for p in pieces:
        while len(p) > max_chars:
            cut = p.rfind(' ', 0, max_chars)
            cut = cut if cut > 0 else max_chars
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            out.append(p)
    return out


def split_into_chunks(text: str, max_chars: int = 240) -> list[str]:
    """One sentence per chunk (stable prosody); over-long sentences split on clauses.

    Very short trailing fragments (e.g. "Thank you.") are merged into the
    previous sentence so they don't get their own clipped TTS pass.
    """
    sentences = re.split(r'([.!?]+(?:\s+|$))', text)
    raw: list[str] = []
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        if i + 1 < len(sentences):
            sentence += sentences[i + 1]
        sentence = sentence.strip()
        if sentence:
            raw.extend(_hard_split_long(sentence, max_chars))

    # Merge tiny fragments (< 16 chars) into the neighbouring chunk.
    chunks: list[str] = []
    for s in raw:
        if chunks and len(s) < 16 and len(chunks[-1]) + len(s) + 1 <= max_chars:
            chunks[-1] = f"{chunks[-1]} {s}"
        else:
            chunks.append(s)
    return chunks
