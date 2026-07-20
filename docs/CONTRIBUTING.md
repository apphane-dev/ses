# Contributing

Thanks for helping improve ses. This project favors small, single-purpose
modules that can be copied out one at a time (see the module map in
[`DESIGN.md`](DESIGN.md)).

## Dev setup

```sh
git clone <your-fork>
cd ses
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install sox            # only needed to actually render with qwen-tts
```

You do **not** need `sox`, model weights, network access, or `torch` to run the
test suite — only to render real audio.

## Running tests

```sh
pytest
```

Tests are pure-numpy: synthetic signals (tones, bursts, silence) exercise the
DSP, quality, chunking, and parsing modules. **No model downloads, no network,
no torch.** If a test needs a model or the network, it is in the wrong layer —
move the logic behind a Protocol and test the pure part.

## Style expectations

- **Small, single-purpose modules.** Each file in the module map does one thing
  and depends only on the modules noted for it in [`DESIGN.md`](DESIGN.md). If
  you add a cross-module dependency, keep it explicit and update the module map.
- **Heavy imports live inside adapter methods.** `torch`, `qwen_tts`, `LavaSR`,
  and any other model library are imported inside the adapter that uses them, at
  instantiation or call time — never at module top level. This keeps the pure
  modules importable and testable with numpy alone.
- **No global state.** Every tunable lives on `PipelineConfig`; pass it through
  rather than reaching for module-level constants.
- **Explicit over magic.** No engine auto-discovery or entry points — engines
  are constructed and passed in.

## Contributing a new engine or enhancer adapter

Adapters are the main extension point. To add one:

1. **Implement the Protocol.** A TTS engine satisfies
   `TTSEngine` in [`ses/tts/base.py`](../ses/tts/base.py)
   (`synthesize(text, sample) -> (audio, sr)` plus `close()`); an enhancer
   satisfies `Enhancer` in [`ses/enhance/base.py`](../ses/enhance/base.py)
   (`enhance(audio, sr) -> (audio, sr)`). Put the module next to the reference
   adapter (`ses/tts/<name>.py` or `ses/enhance/<name>.py`) and keep
   the heavy import inside the methods.
2. **Note it in the module map.** Add your adapter to the module map in
   [`DESIGN.md`](DESIGN.md) with its dependencies and the pip requirements it
   pulls in, so someone can copy it out with just its closure.
3. **Add an example.** Show how to construct and pass the adapter to
   `run_pipeline`, mirroring the sketch in the README. If it changes the script
   or CLI surface, extend [`examples/script.md`](../examples/script.md).

Keep pure logic (DSP, gates, parsing tweaks) covered by numpy tests; adapter
wiring does not need a model in CI.
