#!/usr/bin/env python3
"""Verify the encoded film, including silence, every decoded frame, and fast start."""
from __future__ import annotations

import json
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_streams(probe: dict, timeline: dict) -> dict:
    streams = probe["streams"]
    if len(streams) != 1 or streams[0]["codec_type"] != "video":
        raise ValueError("The film must have exactly one video stream and no audio.")
    video = streams[0]
    expected = {
        "codec_name": "h264", "pix_fmt": "yuv420p", "width": 1920,
        "height": 1080, "r_frame_rate": "30/1",
    }
    for key, value in expected.items():
        if video[key] != value:
            raise ValueError(f"{key}: expected {value}, got {video[key]}")
    frames = int(video["nb_read_frames"])
    if frames != timeline["duration_frames"] or frames != 960:
        raise ValueError(f"Unexpected decoded frame count: {frames}")
    duration = float(probe["format"]["duration"])
    if abs(duration - timeline["duration_seconds"]) > .04 or abs(duration - 32) > .04:
        raise ValueError(f"Unexpected duration: {duration}")
    return {"width": 1920, "height": 1080, "fps": 30, "frames": frames,
            "duration_seconds": duration, "audio_tracks": 0, "silent": True}


def atom_order(path: Path) -> list[str]:
    atoms = []
    with path.open("rb") as file:
        while header := file.read(8):
            if len(header) != 8:
                raise ValueError("Truncated MP4 atom header")
            size, kind = struct.unpack(">I4s", header)
            header_size = 8
            if size == 1:
                size = struct.unpack(">Q", file.read(8))[0]
                header_size = 16
            atoms.append(kind.decode("ascii"))
            if size == 0:
                break
            if size < header_size:
                raise ValueError("Invalid MP4 atom size")
            file.seek(size - header_size, 1)
    return atoms


def main() -> None:
    directory = ROOT / "deliverables"
    path = directory / "ses.mp4"
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout)
    report = validate_streams(probe, json.loads((directory / "timeline.json").read_text()))
    atoms = atom_order(path)
    if atoms.index("moov") > atoms.index("mdat"):
        raise ValueError("MP4 is not fast-start. Metadata must precede media.")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"], check=True, capture_output=True)
    report.update({"decode": "passed", "fast_start": True, "bytes": path.stat().st_size})
    (directory / "probe.json").write_text(json.dumps(probe, indent=2) + "\n")
    (directory / "delivery-qa.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
