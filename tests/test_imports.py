"""Import-time purity: importing ses and its pure modules must not pull in torch.

Each check runs in a fresh subprocess so the heavy optional dependencies
(torch, qwen_tts, LavaSR) are not already resident from another test.
"""

import subprocess
import sys


def _torch_absent_after(import_line: str) -> None:
    code = (
        "import sys\n"
        f"{import_line}\n"
        'assert "torch" not in sys.modules, "torch was imported by ses"\n'
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"import failed or torch leaked:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_import_ses_top_level_no_torch():
    _torch_absent_after("import ses")


def test_import_chunking_no_torch():
    _torch_absent_after("import ses.chunking")


def test_import_parsing_no_torch():
    _torch_absent_after("import ses.parsing.markdown")


def test_import_audio_dsp_no_torch():
    _torch_absent_after("import ses.audio.dsp")


def test_import_audio_quality_no_torch():
    _torch_absent_after("import ses.audio.quality")
