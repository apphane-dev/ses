"""argparse front-end for the voiceover pipeline (python -m ses)."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from ses.config import PipelineConfig
from ses.logging import log
from ses.parsing.markdown import MarkdownScriptParser
from ses.samples import bundled_voices_dir, choose_sample, find_samples


def build_config(args) -> PipelineConfig:
    return PipelineConfig(
        chunk_timeout_sec=args.chunk_timeout_sec,
        chunk_retries=args.chunk_retries,
        enhance_audio=not args.no_enhance,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Render per-slide voiceover audio using Qwen3-TTS voice cloning.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--sample", metavar="NAME", help="voice sample stem in samples dir (no extension)")
    parser.add_argument("--script", metavar="PATH", default=None, help="markdown script to read")
    parser.add_argument("--slide", type=int, default=None, help="render single slide index (0-based)")
    parser.add_argument("--dry-run", action="store_true", help="parse and print, no audio")
    parser.add_argument("--chunk-timeout-sec", type=int, default=180, help="seconds before retrying a stuck chunk; 0 disables")
    parser.add_argument("--chunk-retries", type=int, default=2, help="retry count per chunk after failures/timeouts")
    parser.add_argument(
        "--show-backend-warnings",
        action="store_true",
        help="show qwen-tts backend warnings that are normally hidden on Apple/MPS",
    )
    parser.add_argument(
        "--no-enhance",
        action="store_true",
        help="skip LavaSR speech enhancement post-processing",
    )
    parser.add_argument("--samples-dir", metavar="PATH", default="in/", help="directory holding voice samples")
    parser.add_argument("--out-dir", metavar="PATH", default="audio/", help="base output directory")
    args = parser.parse_args(argv)

    config = build_config(args)

    script_file = Path(args.script).expanduser().resolve() if args.script else Path("script.md").resolve()
    if not script_file.exists():
        sys.exit(f"❌ Script not found: {script_file}")

    text = script_file.read_text()
    md_parser = MarkdownScriptParser()
    sections = md_parser.parse(text)

    log(f"Parsed {len(sections)} slide sections from {script_file.name}")
    for s in sections:
        log(f"  [{s.index:02d}] {s.heading}  ({len(s.narration)} chars)")

    if args.dry_run:
        log("-- dry run, no audio generated --")
        return

    from ses.tts.qwen3 import Qwen3TTSEngine, require_native_deps

    require_native_deps()

    samples_dir = Path(args.samples_dir).expanduser().resolve()
    samples_dir.mkdir(parents=True, exist_ok=True)

    samples = find_samples(samples_dir)
    if not samples:
        # Empty samples dir → fall back to any samples dropped in examples/voices/
        # so you can render without pointing --samples-dir at them explicitly.
        fallback = bundled_voices_dir()
        if fallback is not None and fallback != samples_dir and find_samples(fallback):
            log(f"No voice samples in {samples_dir}/ — using samples in {fallback}/")
            samples_dir = fallback
            samples = find_samples(fallback)
    sample = choose_sample(samples, args.sample, samples_dir)

    # Timestamp subfolder — every run gets its own directory
    run_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir).expanduser().resolve() / run_ts

    engine = Qwen3TTSEngine(sample, config, show_backend_warnings=args.show_backend_warnings)
    enhancer = None
    if config.enhance_audio:
        from ses.enhance.lavasr import LavaSREnhancer
        enhancer = LavaSREnhancer(config, show_backend_warnings=args.show_backend_warnings)

    from ses.pipeline import run_pipeline

    run_pipeline(
        script_text=text,
        sample=sample,
        out_dir=out_dir,
        config=config,
        parser=md_parser,
        engine=engine,
        enhancer=enhancer,
        sections_filter=args.slide,
    )


if __name__ == "__main__":
    main()
