# Manuscript to air

The approved ses product film, extracted into this repo with its visual identity.
Six sections, 32 seconds, 1920 x 1080, 30 fps. H.264, fast-start MP4, no audio
stream. There is no soundtrack, sound effect, narration, or audio-generation step.

The vector waveforms and workflow illustrations are not recorded product output.
Product claims follow the README and `ses/pipeline.py`. See `STORYBOARD.md` for the
complete on-screen text and shot timing. The original ses film is preserved;
this is not a new story or a conversion from Remotion.

## Build

The renderer uses fframes 1.2.0 with Skia's Vulkan GPU backend. This checkout is
configured for Linux. Install a working Vulkan driver, Rust, ffmpeg, pkg-config,
Clang, ALSA development libraries, nasm, x264, x265, opus, and ninja. `mise install`
selects Rust 1.99.0. Then:

```sh
cd marketing/film
bash scripts/bootstrap.sh
mise run render
mise run review
mise run test
```

The bootstrap downloads the genuine x264 ABI-163 runtime needed by fframes 1.2.0's
prebuilt FFmpeg on Linux x86_64. It verifies the package's SHA-256 and keeps the
library in the ignored `.native/` directory. It does not change system libraries.

Fonts are embedded from `../../brand/fonts/`; no external audio or remote assets
are needed. `Cargo.lock` is committed. The film and Python CLI have no runtime
code dependencies on one another.

## Watch

```sh
cargo run --release -- preview
# Or open deliverables/ses.mp4 in a video player.
```

The native preview supports space to pause, h/l to seek, j/k to step, and q to
quit. The published website uses a normal video player without autoplay.

## Review

```sh
cargo run --release -- timeline
cargo run --release -- inspect --all-frames --fail-on warning
cargo run --release -- strip -n 18 --columns 3 -o deliverables/strip.png
cargo run --release -- frame '#0@50%,#3@50%,#5@50%'
python3 scripts/verify.py
```

`review` produces a whole-film strip, one eight-frame strip per scene, key frames,
and all-frame diagnostics. The six snapshot baselines were carried over from the
reviewed original. Inspect the PNGs before accepting a visual change with
`FFRAMES_UPDATE_SNAPSHOTS=1`. Verification checks the decoded frame count, size,
codec, duration, absence of audio, full decode, and MP4 fast start.

Generated MP4s and review reports stay in the ignored `deliverables/` directory.
The published video is a release asset and a static file on the `website` branch,
not a binary in the product's main source branch.

## Encode for the web

```sh
mise run encode
```

This runs `vendor/web-video/web-video.sh` on `deliverables/ses.mp4`. It writes
`ses.av1.mp4`, the `ses.h264.mp4` fallback, and the `ses.jpg` poster, then gives
both videos the checks above. The script is vendored unchanged, with its MIT
license, from Evil Martians'
[web-video skill](https://github.com/evilmartians/agent-skills/tree/b964cf1b164bd0a81019fb54fcb11a7dcec522d4/skills/web-video).
The quality flags are pinned in `scripts/encode.sh`. ffmpeg needs SVT-AV1 and
x264, and the AV1 pass takes a few minutes.

## Publish

From the repository root, after review and `mise run encode`:

```sh
# Install fonttools from marketing/requirements.txt for asset generation.
.venv/bin/python marketing/scripts/brand.py --check
# Requires resvg for the social card and ffmpeg for verification.
.venv/bin/python marketing/scripts/site-assets.py ../ses-website
```

The script verifies the master and the web encodes. It copies the brand assets,
the unchanged font licenses, `ses.av1.mp4`, the H.264 encode as `ses.mp4`, and the
poster, then records SHA-256 hashes in the website's `public/media/manifest.json`.
It requires a checkout of this repo's `website` branch. Run that branch's
`mise run build`, review the page, then commit and push `website`. Its existing
GitHub Actions workflow deploys to Cloudflare Pages.

The marketing release tag is `film-2026-10-15`. It is marked as not the latest
software release. The download includes the silent MP4, poster, contact sheet,
validation reports, and a SHA-256 manifest.
