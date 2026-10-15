# ses visual identity

The identity comes from the approved silent fframes film, *Manuscript to air*.
It uses a dark recording-room palette, a cream serif wordmark, manuscript-colored
script pages, rounded waveform strokes, and one ember-orange playhead.

`tokens.json` is the source of truth. `tokens.css`, the outlined SVG assets, and
`marketing/film/src/identity.rs` are generated from it. The product code does not
import any marketing dependencies.

## Palette

| Role | Color | Use |
| --- | --- | --- |
| Background | `#16100d` | Canvas and page |
| Panel | `#221914` | Samples, file tiles, terminals |
| Line | `#3f3129` | Dividers and tape marks, not small text |
| Cream | `#f3e9da` | Primary text and waveforms |
| Muted | `#a89886` | Supporting text on dark surfaces |
| Ember | `#ff6b2c` | Playhead, connections, links, selection |
| Paper | `#efe4d2` | Manuscript panels |
| Ink | `#24190f` | Text on paper |
| Heading | `#a8380f` | Headings on paper |

Instrument Serif Regular is the display face and wordmark. IBM Plex Mono Regular
is for commands, paths, body copy, and labels. Both font binaries are unchanged;
their SIL Open Font Licenses are in `licenses/`. The SVG lettering is outlined so
GitHub can render it without downloading a font.

## Assets

- `wordmark.svg`: transparent cream wordmark for dark backgrounds.
- `icon.svg`: waveform favicon.
- `banner.svg`: 1280 x 420 README banner.
- `social.svg`, `social.png`: 1200 x 630 sharing image.
- `tokens.css`: self-hosted fonts and `--ses-*` CSS variables.

Keep the lowercase wordmark. Use cream on dark and dark ink on paper. Ember
marks an action or signal, not every decoration. Do not add gradients, blue/cyan
accents, synthetic bold serif text, or extra display families. The waveforms are
illustrations, not audio output or evidence of synthesis quality.

Film motion uses short ease-outs, lightly damped entrances, left-to-right signal
reveals, and a persistent tape. Web motion respects reduced-motion preferences.
The film is silent by design. There must be no audio stream, not just a muted
player. `marketing/film/scripts/verify.py` and the regression tests enforce this.

## Regenerate

```sh
uv pip install --python .venv/bin/python -r marketing/requirements.txt
.venv/bin/python marketing/scripts/brand.py
resvg brand/social.svg brand/social.png
.venv/bin/python marketing/scripts/brand.py --check
```

The website lives on the separate `website` branch of this same repository.
After rendering and reviewing the film, sync the generated assets into its
checkout with `marketing/scripts/site-assets.py`. See the film README.

## Provenance

Extracted on October 15, 2026 from apphane's approved ses campaign film at
revision `d57f7ea`, originally authored in the central marketing workspace.
Only ses code, its two fonts, and its reviewed snapshots were copied here.
The other products and the reference workspace remain unchanged.
