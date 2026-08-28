# ses

**A voice-cloning voiceover pipeline for real narration work: give it a voice
sample, a markdown script, and your settings; get back narrated audio in that
voice — one WAV per section plus a single concatenated render.**

`ses` (Turkish for "voice") runs on a deliberately tuned engine stack —
[Qwen3-TTS](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) for
voice-clone synthesis and [LavaSR](https://github.com/ysharma3501/LavaSR) for
speech enhancement. It is **not** engine-agnostic: the quality gates encode
these engines' specific failure modes. Garbled generations are re-rolled,
sections with dead pauses are re-rendered, and enhancement that injects
high-frequency hash is thrown away in favor of the clean raw take. What *is*
open-ended is the usage — any voice sample, any script, your own settings — and
the code itself: modules are small and single-purpose, so the seams are clean if
you want to copy one out and reshape it, up to and including swapping the engines
(with the caveat that new engines mean retuning the gates).

## What it does

**Inputs**

- **A voice sample** — a `.wav` file in `in/` (the default samples dir). Pair it
  with a same-name `.txt` transcript of what the sample says to enable
  in-context-learning (ICL) cloning, which improves fidelity. Without a
  transcript it falls back to x-vector-only cloning.
- **A script** — markdown with `> quoted` narration lines grouped under
  `## <timestamp> — Heading` sections (see [Script format](#script-format)).
- **Settings** — pacing, silence gaps, quality thresholds, and engine behavior,
  all held in one `PipelineConfig`.

**Outputs**

- `slide-NN-<slug>.wav` per section, and a concatenated `full.wav`, written to a
  timestamped run directory under `audio/` (the default output dir).
- Quality gates applied along the way: garble re-roll, dead-pause re-render, and
  enhancement-noise fallback.

The engine is **Qwen3-TTS** (`Qwen/Qwen3-TTS-12Hz-0.6B-Base`) running locally on
Apple MPS or CPU; enhancement is **LavaSR**. Both ship as reference adapters
behind small `Protocol`s — see
[Adapting the engine](#adapting-the-tts-engine-or-enhancer).

## Quickstart

```sh
# 1. Dependencies
pip install -r requirements.txt
brew install sox          # qwen-tts shells out to the SoX executable

# 2. Drop a voice sample in in/ (gitignored)
#    in/my_voice.wav              the sample
#    in/my_voice.txt   (optional) its transcript, for ICL cloning
# Write a script (see examples/script.md), then render
python -m ses --script script.md --sample my_voice
```

You can keep sample voices anywhere and point `--samples-dir` at the folder;
[`examples/voices/`](examples/voices/) is a convenient place to drop them.
`ses` enumerates whatever audio files it finds there, pairing each with an
optional same-name `.txt` transcript for ICL cloning. If `in/` is empty, it
falls back to `examples/voices/` automatically.

```sh
python -m ses --script examples/script.md --sample my_voice --samples-dir examples/voices
```

Useful flags:

- `--dry-run` — parse the script and print the sections without generating any
  audio. Fast way to check your markdown parses the way you expect.
- `--slide N` — render only section index `N` (0-based) so you can tweak one
  section without re-running the whole script.
- `--no-enhance` — skip LavaSR speech enhancement.
- `--samples-dir PATH` / `--out-dir PATH` — override the `in/` and `audio/`
  defaults.
- `--chunk-timeout-sec N` (default `180`) / `--chunk-retries N` (default `2`) —
  tune the per-chunk deadline and retry budget.

> **Model weights download on first run.** The Qwen3-TTS and LavaSR weights are
> fetched from Hugging Face the first time you render (a few hundred MB to a
> couple GB depending on caches); every run afterward is offline. The test suite
> needs none of this — see [Contributing](docs/CONTRIBUTING.md).

## Copying a module into your project

You don't have to take the whole pipeline. The modules are small,
single-purpose, and the pure ones (DSP, quality gates, chunking, parsing) depend
only on numpy — so you can lift one out and drop it into your own codebase.

For example, to take **just the DSP and quality gates** — the trim/fade/normalize
helpers and the garble/pause/noise detectors, all pure-numpy:

```sh
mkdir -p yourproject/audio
cp ses/audio/__init__.py ses/audio/dsp.py ses/audio/quality.py yourproject/audio/
pip install numpy
```

No `torch`, no `qwen_tts`, no pipeline — just the signal processing, now yours to
edit. See [`docs/DESIGN.md`](docs/DESIGN.md) for the module map and each
module's dependencies.

## Adapting the TTS engine or enhancer

The engine stack is tuned, not pluggable — but the seams are clean if you want
to reshape it. Engines and enhancers are plain classes satisfying tiny
`Protocol`s: there is no plugin registry or entry-point magic, you construct your
instance and pass it to `run_pipeline`. Swapping an engine works; just remember
the quality gates were tuned to Qwen3-TTS and LavaSR, so a different engine will
usually need the garble/pause/noise thresholds in `PipelineConfig` retuned.

A TTS engine implements [`ses/tts/base.py`](ses/tts/base.py) and an enhancer
implements [`ses/enhance/base.py`](ses/enhance/base.py):

```python
class TTSEngine(Protocol):  # ses/tts/base.py
    def synthesize(self, text: str, sample: VoiceSample) -> tuple[np.ndarray, int]: ...
    def close(self) -> None: ...

class Enhancer(Protocol):   # ses/enhance/base.py — optional
    def enhance(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, int]: ...
```

Implement one and hand it to the pipeline:

```python
from pathlib import Path

import numpy as np

from ses import PipelineConfig, VoiceSample, run_pipeline

class MyTTS:
    def __init__(self):
        import my_tts_lib               # heavy import stays inside the adapter
        self.model = my_tts_lib.load()

    def synthesize(self, text: str, sample: VoiceSample) -> tuple[np.ndarray, int]:
        audio = self.model.clone(text, ref_wav=str(sample.audio))
        return np.asarray(audio, dtype=np.float32), self.model.sample_rate

    def close(self) -> None:
        pass

run_pipeline(
    script_text=Path("script.md").read_text(),
    sample=VoiceSample(
        name="my_voice",
        audio=Path("in/my_voice.wav"),
        transcript=Path("in/my_voice.txt"),   # or None for x-vector-only cloning
    ),
    out_dir=Path("audio/manual-run"),
    config=PipelineConfig(),
    engine=MyTTS(),
    enhancer=None,                             # skip enhancement, or pass your own
)
```

`run_pipeline` also accepts `parser=` (a `ScriptParser`, defaults to the
markdown parser) and `sections_filter=N` to render a single section. If you'd
rather discover samples from a directory than build `VoiceSample` by hand, use
`find_samples(in_dir)` and `choose_sample(samples, name, in_dir)` from
`ses.samples`.

Keep heavy imports (`torch`, model libraries) inside the adapter's methods so the
DSP, parsing, chunking, and quality modules stay importable with numpy alone.

### audio8-TTS (ONNX INT8, CPU) — second engine

Besides the reference Qwen3 adapter, [`ses/tts/audio8.py`](ses/tts/audio8.py)
ships an `Audio8TTSEngine` running
[`Audio8/audio8-TTS-0.1B-ONNX-INT8`](https://huggingface.co/Audio8/audio8-TTS-0.1B-ONNX-INT8)
entirely on CPU with plain `onnxruntime` — no torch, 44.1 kHz mono FP32
output, Apache-2.0 weights. It reproduces the vendor RAS top-p sampling and
always speaks with the model's packaged reference voice (it does **not**
clone the `VoiceSample`), needs ~437 MB of weights on first use (HF-cached,
`SES_AUDIO8_MODEL_DIR` to point at a local checkout instead), and splits long
input into pieces that fit the model's 2048-token window.

```python
from pathlib import Path

from ses import PipelineConfig, VoiceSample, run_pipeline
from ses.tts.audio8 import Audio8TTSEngine  # onnxruntime/tokenizers load inside

engine = Audio8TTSEngine(
    VoiceSample(name="ignored", audio=Path("in/my_voice.wav"), transcript=None),
    PipelineConfig(),
)
run_pipeline(
    script_text=Path("script.md").read_text(),
    sample=engine.sample,
    out_dir=Path("audio/manual-run"),
    config=PipelineConfig(),
    engine=engine,
)
```

Adapter deps: `onnxruntime`, `tokenizers`, `huggingface_hub` (fetch only —
all optional; the pure test suite and `ses` import skip them). One end-to-end
synthesis test runs when `SES_AUDIO8_E2E=1` is set.

## Script format

Sections are introduced by a heading of the form `## <timestamp> — <Title>`. The
timestamp is free-form (`0:00`, `1:23`, ...) and the dash may be an em dash,
en dash, or hyphen. Narration is written in `>` quoted lines beneath the heading.

```markdown
## 0:00 — Welcome

> First paragraph. Sentences are split and synthesized one at a time
> for stable prosody.
>
> A blank `>` line starts a new paragraph, which gets a slightly longer pause.

## 0:20 — Next section

> TODO
> Standalone TODO / REDO / WIP / DRAFT lines are skipped, so you can leave
> notes in place without them being narrated.
```

Conventions:

- `## <timestamp> — Heading` starts a new section; the heading becomes the WAV
  slug.
- `>` lines are narration; consecutive `>` lines join into one paragraph.
- A blank `>` line (or a non-quote line) ends the current paragraph — paragraphs
  are separated by a longer silence than sentences.
- A `>` line whose entire content is `TODO`, `REDO`, `WIP`, or `DRAFT` (also
  `TBD`, or a run of dots/asterisks) is skipped.
- A trailing `- TODO`/`- WIP`/etc. marker on a heading is stripped from the slug.

See [`examples/script.md`](examples/script.md) for a complete example.

## Architecture

The full module map, contracts, quality-gate rationale, and testing policy live
in [`docs/DESIGN.md`](docs/DESIGN.md). Contributions welcome — see
[`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
