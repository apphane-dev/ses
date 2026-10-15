#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p deliverables
R=./target/release/ses-film
"$R" timeline --json > deliverables/timeline.json
"$R" render -o deliverables/ses-master.mp4
ffmpeg -hide_banner -loglevel error -nostdin -y -i deliverables/ses-master.mp4 -map 0:v:0 -c:v copy -an -movflags +faststart deliverables/ses.mp4
python3 scripts/verify.py
