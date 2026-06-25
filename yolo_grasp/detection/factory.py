from __future__ import annotations

from typing import Mapping

from yolo_grasp.detection.base import Detector
from yolo_grasp.detection.mock_detector import MockDetector
from yolo_grasp.detection.yolo_detector import YoloDetector


def create_detector(config: Mapping) -> Detector:
    detector_type = str(config.get("type", "mock")).lower()
    if detector_type == "mock":
        return MockDetector(config.get("mock", {}))
    if detector_type == "yolo":
        return YoloDetector(config.get("yolo", {}))
    raise ValueError(f"Unsupported detector.type: {detector_type}")

