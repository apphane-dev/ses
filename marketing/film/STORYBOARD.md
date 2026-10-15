# ses film storyboard

Silent product film. No music, sound effects or narration. 1920x1080, 30 fps, 32 s, six shots.
Code: `src/ses.rs`. Hit times below are shot-relative and come from `HITS`
in that module; the visuals key off the same constants.

## Design

- Palette: studio dark `#16100d`, panel `#221914`, cream ink `#f3e9da`, dim `#a89886`,
  ember accent `#ff6b2c`; the script page is paper `#efe4d2` with ink `#24190f` and heading
  rust `#a8380f`.
- Type: Instrument Serif 400 for display, IBM Plex Mono 400 for files and script lines.
- Persistent chrome: `ses` wordmark plus "voice-cloning voiceover pipeline" top left, shot
  counter top right, and a film-long tape at y=980 with an ember playhead and shot ticks.
  It stays at full opacity across cuts; shot content fades to the background in the last
  0.25 s (except the closing card).
- Waveforms are ornamental, seeded noise, not real audio.

The example script shown on screen is invented for the film:

```markdown
## 0:00 — Welcome
> Welcome back to the workshop.
> Today we build a bookshelf.
> It takes one afternoon.
> TODO
## 0:20 — Tools
> You need a saw and a square.
## 0:40 — Assembly
> Measure twice. Cut once.
```

## 01 SesInputs — 0:00–0:05 (5 s)

- Text: labels `VOICE SAMPLE`, `SCRIPT.MD`; `in/my_voice.wav`, `in/my_voice.txt`,
  `transcript: enables ICL cloning`; title **Give it a voice and a script.**
- Visual: first frame shows the sample card with a partial waveform and the script page with
  two lines. The title rises in at once and is readable by ~0.6 s. The waveform draws left to
  right; the remaining script lines stagger in. An ember line joins both cards at a pulsing
  node.
- Hits: 0.1 title · 0.6 waveform starts drawing · 3.6 cards linked.
- Facts: README "Inputs" (`.wav` in `in/`, same-name `.txt` transcript enables ICL cloning).

## 02 SesParse — 0:05–0:11 (6 s)

- Text: **Headings become sections.**; `skipped, not narrated`; **TODO lines stay silent.**;
  tiles `slide-00-welcome.wav`, `slide-01-tools.wav`, `slide-02-assembly.wav`.
- Visual: an ember read-head walks the script line by line; headings turn rust when read. The
  `> TODO` line is struck through and dims. Wires grow from each heading at the page edge to
  three file tiles that spring in from the right.
- Hits: 0.8 first heading read · 2.4 TODO struck · 2.9 second heading · 3.8 file tiles.
- Facts: README "Script format" (`## <timestamp> — Heading`, `>` narration, standalone TODO
  skipped, heading becomes the WAV slug); `ses/pipeline.py` names files
  `slide-{index:02d}-{slug}.wav`; `ses/parsing/markdown.py` slugify.

## 03 SesSynth — 0:11–0:17 (6 s)

- Text: **Sentence by sentence, in your voice.**; `my_voice.wav + my_voice.txt`;
  ring `Qwen3-TTS` / `voice clone`; sentence chips; `slide-00-welcome.wav`;
  caption `one sentence at a time, for stable prosody`.
- Visual: three sentence pills fly into the engine ring one at a time; the ring pulses on
  each arrival and a waveform row draws on the right (01, 02, 03). On the last beat the three
  rows close up into one section strip.
- Hits: 1.0 sentence 1 · 2.0 sentence 2 · 3.0 sentence 3 · 4.0 rows merge into the section.
- Facts: README script-format example ("Sentences are split and synthesized one at a time for
  stable prosody"); engine `Qwen/Qwen3-TTS-12Hz-0.6B-Base` voice clone.

## 04 SesGates — 0:17–0:22 (5 s)

- Text: **Bad takes get another pass.**; cells `GARBLE`, `DEAD PAUSE`, `ADDED HASH`;
  outcomes **Re-roll the chunk.** · **Re-render the section.** · **Keep the raw take.**;
  caption `gates tuned to Qwen3-TTS and LavaSR`.
- Visual: an ember playhead runs a rail over three cells and lands on each at its hit.
  Garble: an ember burst inside the take; the take flips and comes back clean. Dead pause: a
  dotted gap; the section flips and comes back continuous. Added hash: an ember fuzz layer
  drops away from the raw take. A check mark lands per cell.
- Hits: 0.9 garble · 2.1 dead pause · 3.3 added hash.
- Facts: README intro (garbled generations re-rolled, dead-pause sections re-rendered,
  enhancement that injects high-frequency hash thrown away for the raw take); `docs/DESIGN.md`
  "Quality gates".

## 05 SesOutput — 0:22–0:27 (5 s)

- Text: **One WAV per section. One full render.**; the three file names; `full.wav`;
  caption `offline after the first model download`.
- Visual: file names sit dim from the first frame; each lights and its waveform slides in.
  On the merge beat the three waveforms travel down and butt together into one ember
  `full.wav` strip with small silence dots between sections.
- Hits: 0.6 / 1.0 / 1.4 section files · 2.6 merge into `full.wav`.
- Facts: README "Outputs" (per-section WAVs plus concatenated `full.wav`); `concat.py` joins
  with configured silence; README note that weights download on first run, every run
  afterward is offline.

## 06 SesOutro — 0:27–0:32 (5 s, CTA holds ~4 s)

- Text: **ses**; **Your script, in a cloned voice.**;
  `python -m ses --script script.md --sample my_voice`; **ses.apphane.dev**;
  `MIT · runs locally · Qwen3-TTS + LavaSR`.
- Visual: a large ember waveform breathes on the right from the first frame; the wordmark
  rises, then tagline, command pill and URL. Everything settles by ~1.0 s and holds; no fade
  at the end.
- Hits: 0.5 tagline/URL group lands.
- Facts: README Quickstart command; MIT license; README "runs locally on Apple MPS or CPU".
