# ses — architecture

An open-source voice-cloning voiceover pipeline. The engine stack is a
**deliberate choice**, not a plug-in slot: Qwen3-TTS for voice-clone
synthesis and LavaSR for speech enhancement, tuned together (the quality
gates below encode their specific failure modes). What is agnostic is the
**usage**: any voice sample, any script, your settings — and the code is
organized so you can copy and reshape any part of it, including the
engines, for your own needs. You give it:

1. **A voice sample** — a `.wav` file, optionally paired with a same-name
   `.txt` transcript of what the sample says (improves cloning fidelity).
2. **A script** — a text document to narrate (default format: markdown with
   `> quoted` narration lines grouped under headings).
3. **Settings** — pacing, silence gaps, quality thresholds, engine choice.

It produces per-section WAV files plus a concatenated full render, with
quality gates (garble detection, dead-pause detection) and optional speech
enhancement.

## Copying modules

This is **not** a pip package you depend on — you can copy the modules you need
into your own project and adapt them. The code is organized so that is
practical:

- Every module is small and single-purpose. The pure ones (DSP, quality gates,
  chunking, parsing) depend only on numpy; the heavy engine adapters are
  isolated behind `Protocol`s so you can leave them behind.
- The module map below lists what each component is and what it depends on, so
  you can pull one out with just its closure.
- No framework, no plugin magic: engines and parsers are plain classes
  satisfying tiny `Protocol`s. The Protocols exist to keep the seams clean
  and the pure modules testable — not to promise engine neutrality. If you
  swap the engine, expect to retune the quality gates.

## Module map

```
ses/
  __init__.py        # public surface re-exports
  config.py          # PipelineConfig dataclass — every tunable, one place
  logging.py         # timestamped log()
  samples.py         # VoiceSample discovery/selection from a samples dir
  chunking.py        # sentence/clause splitting for stable TTS prosody
  parsing/
    base.py          # ScriptParser Protocol, Section dataclass
    markdown.py      # default markdown parser (headings + > narration)
  audio/
    dsp.py           # trim, fades, RMS normalize, loudness leveling, resample
    quality.py       # garble detection, long-pause detection, hash detection
    concat.py        # join section WAVs with configured silence
  tts/
    base.py          # TTSEngine Protocol (synthesize(text, sample) -> audio)
    qwen3.py         # Qwen3-TTS voice-clone adapter (reference impl)
  enhance/
    base.py          # Enhancer Protocol (enhance(audio, sr) -> audio, sr)
    lavasr.py        # LavaSR adapter with added-noise fallback (reference impl)
  pipeline.py        # orchestration: parse → chunk → synth → gate → enhance → level
  cli.py             # argparse front-end; python -m ses
```

### Contracts

```python
class Section(...):        # parsing/base.py
    index: int; heading: str; slug: str; narration: str  # paragraphs = \n\n

class ScriptParser(Protocol):
    def parse(self, text: str) -> list[Section]: ...

class TTSEngine(Protocol):  # tts/base.py
    def synthesize(self, text: str, sample: VoiceSample) -> tuple[np.ndarray, int]: ...

class Enhancer(Protocol):   # enhance/base.py
    def enhance(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, int]: ...
```

Heavy imports (`torch`, `qwen_tts`, `LavaSR`) live **only** inside the adapter
modules and only at instantiation time — the DSP, parsing, chunking, and
quality modules are importable and testable with numpy alone.

### Config

`PipelineConfig` is a frozen dataclass holding every tunable constant (silence
gaps, fade times, RMS target, retry budgets, chunk size, timeouts). The CLI maps
flags onto it; library users construct it directly. No global state.

## Quality gates

- **Garble gate** — sustained loud-burst detection per chunk; re-roll on hit.
- **Pause gate** — internal silences > threshold trigger a section re-render.
- **Enhancement noise gate** — if the enhancer injects high-frequency hash
  absent in the raw render, discard enhancement and upsample the raw instead.

## Testing policy

Tests are pure-numpy: synthetic signals (tones, bursts, silence) exercise
dsp/quality/chunking/parsing. **No model downloads, no network, no torch
required** to run the suite.

## Non-goals

- Not a hosted service, not a GUI.
- No engine auto-discovery/entry-points; explicit imports are the plugin API.
- The CLI is the supported interface; there is no stable API beyond the
  documented surface.
