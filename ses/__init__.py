"""Voiceover pipeline — public surface.

Importing this package must NOT require torch, qwen_tts, or LavaSR. Heavy
dependencies live only inside the adapter modules (`tts/qwen3.py`,
`enhance/lavasr.py`) and are deferred until those adapters are instantiated.
"""

from ses.config import PipelineConfig
from ses.parsing.base import Section
from ses.parsing.markdown import parse_markdown_script
from ses.pipeline import run_pipeline
from ses.samples import VoiceSample

__all__ = [
    "PipelineConfig",
    "Section",
    "VoiceSample",
    "parse_markdown_script",
    "run_pipeline",
]
