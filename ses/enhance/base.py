"""Enhancer Protocol."""

from typing import Protocol

import numpy as np


class Enhancer(Protocol):
    def enhance(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, int]: ...
