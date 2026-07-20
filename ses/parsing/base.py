"""ScriptParser Protocol and the Section dataclass."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Section:
    index: int
    heading: str
    slug: str
    narration: str  # paragraphs separated by \n\n


class ScriptParser(Protocol):
    def parse(self, text: str) -> list[Section]: ...
