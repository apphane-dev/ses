"""Voice sample discovery/selection from a samples dir."""

from dataclasses import dataclass
from pathlib import Path

from ses.audio.ingest import AUDIO_EXTS, ext_rank
from ses.logging import log
import sys


@dataclass
class VoiceSample:
    name: str
    audio: Path
    transcript: Path | None


def bundled_voices_dir() -> Path | None:
    """Path to the repo's example voices dir (examples/voices/), if present.

    Resolved relative to this package so it works from a repo checkout. The
    directory ships empty — it's a convenient place to drop your own samples,
    which the CLI enumerates as a fallback when the samples dir is empty. When
    `ses/` has been copied into another project without `examples/`, this
    returns None and callers simply skip the fallback.
    """
    candidate = Path(__file__).resolve().parent.parent / "examples" / "voices"
    return candidate if candidate.is_dir() else None


def find_samples(in_dir: Path) -> list[VoiceSample]:
    """Return voice samples in in_dir with optional paired .txt transcript.

    Any supported audio format is accepted (WAV, FLAC, OGG, AIFF, MP3, and —
    via sox — m4a/aac/opus). When several files share a stem, the
    highest-preference format wins so `foo.wav` shadows `foo.mp3`.
    """
    if not in_dir.exists():
        return []
    by_stem: dict[str, Path] = {}
    for path in sorted(in_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
            continue
        current = by_stem.get(path.stem)
        if current is None or ext_rank(path.suffix) < ext_rank(current.suffix):
            by_stem[path.stem] = path
    samples = []
    for stem in sorted(by_stem):
        audio = by_stem[stem]
        txt = audio.with_suffix(".txt")
        samples.append(
            VoiceSample(
                name=stem,
                audio=audio,
                transcript=txt if txt.exists() else None,
            )
        )
    return samples


def choose_sample(samples: list[VoiceSample], explicit_name: str | None, in_dir: Path) -> VoiceSample:
    """Return the sample to use, prompting interactively if needed."""
    if not samples:
        sys.exit(
            f"❌ No voice samples found in {in_dir}/\n"
            f"   Add a .wav file there (optionally paired with a same-name .txt transcript).\n"
            f"   Example:\n"
            f"     {in_dir}/my_voice.wav\n"
            f"     {in_dir}/my_voice.txt   ← optional ICL transcript"
        )

    if explicit_name is not None:
        match = next((s for s in samples if s.name == explicit_name), None)
        if match is None:
            available = ", ".join(s.name for s in samples)
            sys.exit(f"❌ Sample '{explicit_name}' not found in {in_dir}/\n   Available: {available}")
        return match

    if len(samples) == 1:
        s = samples[0]
        icl = " + transcript (ICL)" if s.transcript else " (x-vector only)"
        log(f"Using sample: {s.name}{icl}")
        return s

    log(f"Voice samples in {in_dir}/:")
    for i, s in enumerate(samples):
        icl = " [+ transcript]" if s.transcript else ""
        log(f"  [{i}] {s.name}{icl}")

    while True:
        raw = input(f"Choose sample [0–{len(samples) - 1}]: ").strip()
        if raw.isdigit() and 0 <= int(raw) < len(samples):
            return samples[int(raw)]
        log("  Invalid choice, try again.")
