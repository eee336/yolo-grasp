from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from yolo_grasp.types import Detection, Frame


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: Frame) -> List[Detection]:
        """Return detections for one frame."""

