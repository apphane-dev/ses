"""Default markdown parser: headings + > narration lines."""

import re

from ses.parsing.base import Section


_SKIP_LINE = re.compile(r'^(TODO|REDO|WIP|DRAFT|TBD|\.{2,}|\*{2,})$', re.IGNORECASE)


def _collect_narration(lines: list[str]) -> str:
    """Collect > quoted lines, preserving paragraph breaks as \n\n."""
    paragraphs: list[list[str]] = []
    current_para: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('>'):
            content = stripped.lstrip('>').strip()
            if content and not _SKIP_LINE.match(content):
                current_para.append(content)
            elif not content and current_para:
                # Empty > line = paragraph break
                paragraphs.append(current_para)
                current_para = []
        else:
            # Non-quote line between paragraphs
            if current_para:
                paragraphs.append(current_para)
                current_para = []
    if current_para:
        paragraphs.append(current_para)
    return '\n\n'.join(' '.join(p) for p in paragraphs)


def _slugify(heading: str) -> str:
    s = heading.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')[:40]


def parse_script(text: str) -> list[Section]:
    sections = []
    current_heading = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = re.match(r'^##\s+[\d:]+\s+[—–-]+\s+(.+)$', line)
        if m:
            if current_heading is not None:
                narration = _collect_narration(current_lines)
                if narration:
                    idx = len(sections)
                    sections.append(
                        Section(
                            index=idx,
                            heading=current_heading,
                            slug=_slugify(current_heading),
                            narration=narration,
                        )
                    )
            heading_raw = m.group(1).strip()
            current_heading = re.sub(
                r'\s*[-–]\s*(REDO|TODO|WIP|DRAFT)\s*$', '', heading_raw, flags=re.IGNORECASE
            )
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        narration = _collect_narration(current_lines)
        if narration:
            sections.append(
                Section(
                    index=len(sections),
                    heading=current_heading,
                    slug=_slugify(current_heading),
                    narration=narration,
                )
            )

    return sections


class MarkdownScriptParser:
    def parse(self, text: str) -> list[Section]:
        return parse_script(text)


def parse_markdown_script(text: str) -> list[Section]:
    """Thin convenience wrapper around the markdown parser."""
    return parse_script(text)
