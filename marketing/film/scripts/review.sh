#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
R=./target/release/ses-film
mkdir -p deliverables/{scenes,frames}
"$R" timeline --json > deliverables/timeline.json
"$R" inspect --all-frames --fail-on warning --json > deliverables/inspect.json
"$R" strip -n 18 --columns 3 --width 640 -o deliverables/strip.png
for scene in 0 1 2 3 4 5; do
  "$R" strip "#$scene" -n 8 --columns 4 --width 480 -o "deliverables/scenes/$scene.png"
done
"$R" frame '#0@0,#0@50%,#1@50%,#2@50%,#3@50%,#4@50%,#5@50%,end' -o deliverables/frames
