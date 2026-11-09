#!/usr/bin/env python3
"""Verify and copy the ses identity and silent film into a website-branch checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELIVERY = ROOT / "marketing/film/deliverables"


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("website", type=Path)
    args = parser.parse_args()
    website = args.website.resolve()
    branch = subprocess.check_output(["git", "-C", str(website), "branch", "--show-current"], text=True).strip()
    remote = subprocess.check_output(["git", "-C", str(website), "remote", "get-url", "origin"], text=True).strip()
    if branch != "website" or not remote.endswith(("apphane-dev/ses.git", "apphane-dev/ses")):
        raise SystemExit("Destination must be this repository's website-branch checkout.")
    run(sys.executable, str(ROOT / "marketing/scripts/brand.py"), "--check")
    run(sys.executable, str(ROOT / "marketing/film/scripts/verify.py"))
    run(sys.executable, str(ROOT / "marketing/film/scripts/verify.py"), "--web")
    run("resvg", str(ROOT / "brand/social.svg"), str(ROOT / "brand/social.png"))
    public = website / "public"
    for source in (ROOT / "brand").rglob("*"):
        if source.is_file() and source.name != "README.md":
            target = public / "brand" / source.relative_to(ROOT / "brand")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    media = public / "media"
    media.mkdir(parents=True, exist_ok=True)
    # The page plays AV1 first. ses.mp4 is the H.264 fallback and the download.
    published = {"ses.av1.mp4": "ses.av1.mp4", "ses.h264.mp4": "ses.mp4", "ses.jpg": "ses-poster.jpg"}
    for source, target in published.items():
        shutil.copyfile(DELIVERY / source, media / target)
    files = [*sorted((public / "brand").rglob("*")), *(media / target for target in published.values())]
    manifest = {"title": "Manuscript to air", "duration_seconds": 32, "audio_tracks": 0,
                "files": {str(path.relative_to(public)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files if path.is_file()}}
    (media / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Synced identity and verified silent film to {public}")


if __name__ == "__main__":
    main()
