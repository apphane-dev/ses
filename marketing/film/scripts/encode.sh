#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Landing-page encodes of the verified delivery: AV1, H.264 fallback, poster.
# qp 40 / crf 23 instead of the script's 45 / 26: fainter ghosting at hard cuts.
# 28.5 s is the outro wordmark.
bash vendor/web-video/web-video.sh --output-dir deliverables --no-audio --poster-at 28.5 \
  --av1-qp 40 --h264-crf 23 deliverables/ses.mp4
python3 scripts/verify.py --web
