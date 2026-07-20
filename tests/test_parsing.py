"""Tests for ses.parsing.markdown.parse_markdown_script."""

from ses.parsing.markdown import parse_markdown_script


SCRIPT = """## 0:00 — Intro

> Welcome to the course.
> Today we cover the basics.

## 0:45 — Second topic - REDO

> A first paragraph of narration here.

> A second paragraph after a blank quote line.

## 1:30 — Empty section

## 2:00 — Skipped TODO

> TODO
> DRAFT
> WIP
> This line is real narration and should survive.
"""


def test_parses_sections_with_index_heading_slug():
    sections = parse_markdown_script(SCRIPT)
    # The empty section and the all-TODO section are dropped, so three survive.
    assert len(sections) == 3

    first = sections[0]
    assert first.index == 0
    assert first.heading == "Intro"
    assert first.slug == "intro"

    second = sections[1]
    assert second.index == 1
    # "- REDO" stripped from the heading.
    assert second.heading == "Second topic"
    assert second.slug == "second-topic"

    third = sections[2]
    assert third.index == 2
    assert third.heading == "Skipped TODO"
    assert "real narration" in third.narration


def test_blank_quote_line_produces_paragraph_break():
    sections = parse_markdown_script(SCRIPT)
    second = sections[1]
    assert "\n\n" in second.narration
    paras = second.narration.split("\n\n")
    assert len(paras) == 2
    assert paras[0].startswith("A first paragraph")
    assert paras[1].startswith("A second paragraph")


def test_todo_redo_wip_draft_lines_skipped():
    sections = parse_markdown_script(SCRIPT)
    third = sections[2]
    # Only the real narration line survives the skip markers.
    assert "real narration" in third.narration
    for marker in ("TODO", "REDO", "WIP", "DRAFT"):
        assert marker not in third.narration


def test_section_with_no_narration_is_dropped():
    sections = parse_markdown_script(SCRIPT)
    headings = [s.heading for s in sections]
    assert "Empty section" not in headings
