#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Rust comes from mise. Python creates review sheets and validates deliveries.
command -v cargo >/dev/null || { echo 'Install Rust first, or run mise install.' >&2; exit 1; }
# fframes 1.2.0's prebuilt FFmpeg needs x264 ABI 163. Use a genuine Ubuntu
# runtime package in this workspace only on Linux x86_64, never an ABI shim.
if [[ $(uname -sm) == 'Linux x86_64' && ! -f .native/libx264.so.163 ]]; then
  mkdir -p .native
  package=$(mktemp)
  trap 'python3 -c "from pathlib import Path; import sys; Path(sys.argv[1]).unlink(missing_ok=True)" "$package"' EXIT
  curl -fLsS 'https://archive.ubuntu.com/ubuntu/pool/universe/x/x264/libx264-163_0.163.3060+git5db6aa6-2build1_amd64.deb' -o "$package"
  echo "4b6dc88ca9fee6a234b599cfc67ce1042050dd2814f00b5065406bcdc75baf47  $package" | sha256sum -c -
  ar p "$package" data.tar.zst | tar --zstd -x -C .native --strip-components=4 ./usr/lib/x86_64-linux-gnu/libx264.so.163
  ln -sfn libx264.so.163 .native/libx264.so
fi
mkdir -p deliverables
cargo build --release --locked
