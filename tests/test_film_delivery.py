"""Reject accidental audio tracks even if the MP4 is otherwise valid."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "marketing/film/scripts/verify.py"
SPEC = importlib.util.spec_from_file_location("verify_film", SCRIPT)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def probe():
    return {"streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
                         "width": 1920, "height": 1080, "r_frame_rate": "30/1", "nb_read_frames": "960"}],
            "format": {"duration": "32.0"}}


def test_accepts_the_silent_full_hd_delivery():
    assert VERIFY.validate_streams(probe(), {"duration_frames": 960, "duration_seconds": 32})["silent"]


def test_rejects_an_audio_track():
    data = probe()
    data["streams"].append({"codec_type": "audio"})
    with pytest.raises(ValueError, match="no audio"):
        VERIFY.validate_streams(data, {"duration_frames": 960, "duration_seconds": 32})


def test_rejects_a_truncated_delivery():
    data = probe()
    data["streams"][0]["nb_read_frames"] = "959"
    with pytest.raises(ValueError, match="frame count"):
        VERIFY.validate_streams(data, {"duration_frames": 960, "duration_seconds": 32})
