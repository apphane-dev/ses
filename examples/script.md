# Example narration script

Sections start with `## <timestamp> — Heading`. Narration lives in `>` quoted
lines under each section. A blank `>` line is a paragraph break. Lines that are
just `TODO`/`REDO`/`WIP`/`DRAFT` are skipped, so you can leave notes to yourself
in place without them being read aloud.

## 0:00 — Welcome

> Welcome to ses, a voiceover pipeline. This tool turns a written script into
> narrated audio using a short sample of your own voice.
>
> You write in plain markdown, drop in a voice sample, and get back one WAV per
> section plus a single concatenated render of the whole thing.

## 0:20 — How it works

> Each section is split into sentences and synthesized one sentence at a time,
> which keeps the prosody stable and the pacing even.
>
> Quality gates run automatically. Garbled bursts are re-rolled, over-long dead
> pauses trigger a re-render, and noisy enhancement is discarded in favor of the
> clean raw take.

## 0:45 — Getting started

> TODO
> Point the tool at your sample and your script, then run it. The first run
> downloads the model weights; every run after that works offline.
>
> When you like a section, iterate on just that one with the slide flag instead
> of re-rendering the entire script.
