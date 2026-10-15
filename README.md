# ses website

The landing site for ses.apphane.dev. This checkout is the orphan `website`
branch of `apphane-dev/ses`, deployed to Cloudflare Pages by the existing workflow.

```sh
mise run build
mise run check
mise run dev
```

The visual identity and the silent fframes source live on `main` in `brand/`
and `marketing/film/`. Edit tokens there rather than maintaining a second palette.
The website self-hosts both fonts and their licenses. It embeds the 32-second
1080p film with native controls, a poster, and a direct download. There is no
autoplay, third-party player, or audio stream.

After rendering and reviewing the film in a `main` checkout, copy assets here:

```sh
# Run in the main checkout, with this checkout as the destination.
.venv/bin/python marketing/scripts/site-assets.py ../ses-website
```

`public/media/manifest.json` records the asset hashes. `mise run build` rejects
changes that have not been synced from the canonical identity and verified film.
Commit and push `website` to deploy. The product's Python code stays on `main`.
