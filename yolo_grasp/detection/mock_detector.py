from __future__ import annotations

from typing import List, Mapping

import numpy as np

from yolo_grasp.detection.base import Detector
from yolo_grasp.types import Detection, Frame


class MockDetector(Detector):
    def __init__(self, config: Mapping):
        self.class_name = str(config.get("class_name", "mineral_water_bottle"))
        self.confidence = float(config.get("confidence", 0.99))
        self.bbox_xyxy = tuple(float(v) for v in config.get("bbox_xyxy", [270, 150, 370, 390]))

    def detect(self, frame: Frame) -> List[Detection]:
        x1, y1, x2, y2 = [int(v) for v in self.bbox_xyxy]
        mask = np.zeros(frame.depth_m.shape[:2], dtype=bool)
        h, w = mask.shape
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        mask[y1:y2, x1:x2] = True
        return [
            Detection(
                class_id=0,
                class_name=self.class_name,
                confidence=self.confidence,
                bbox_xyxy=self.bbox_xyxy,
                mask=mask,
            )
        ]

