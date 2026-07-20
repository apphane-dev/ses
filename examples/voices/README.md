# Voice samples

A place to keep voice samples for trying out `ses`. This folder ships empty —
drop your own clips here.

Each sample is an audio file (WAV, FLAC, OGG, AIFF, MP3, or — via sox —
m4a/aac/opus), optionally paired with a same-name `.txt` transcript of what the
clip says. Providing the transcript enables ICL (in-context-learning) cloning,
which improves fidelity; without it, cloning falls back to x-vector only.

```
examples/voices/
  my_voice.wav
  my_voice.txt   (optional) transcript, for ICL cloning
```

## Usage

Point `--samples-dir` at this folder and pick a voice by its file stem:

```sh
python -m ses --script examples/script.md --sample my_voice --samples-dir examples/voices
```

If your default samples dir (`in/`) is empty, `ses` falls back to whatever it
finds here automatically.
