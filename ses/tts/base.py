"""TTSEngine Protocol."""

from typing import Protocol

import numpy as np

from ses.samples import VoiceSample


class TTSEngine(Protocol):
    def synthesize(self, text: str, sample: VoiceSample) -> tuple[np.ndarray, int]: ...

    def close(self) -> None: ...
