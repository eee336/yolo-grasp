from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional

import cv2
import numpy as np

from yolo_grasp.config import resolve_path
from yolo_grasp.detection.base import Detector
from yolo_grasp.types import Detection, Frame, HardwareError


class YoloDetector(Detector):
    """Ultralytics YOLO detector/segmenter wrapper."""

    def __init__(self, config: Mapping):
        self.config = config
        weights = resolve_path(str(config.get("weights", "models/bottle_yolo.pt")))
        if not weights.exists():
            raise FileNotFoundError(
                f"YOLO weights not found: {weights}. Put your trained model there or update detector.yolo.weights."
            )

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise HardwareError("ultralytics is required for detector.type=yolo") from exc

        self.model = YOLO(str(weights))
        self.allowed_classes = {str(v) for v in config.get("allowed_classes", [])}
        self.class_aliases: Dict[str, str] = {
            str(key): str(value) for key, value in config.get("class_aliases", {}).items()
        }
        self.conf = float(config.get("conf", 0.45))
        self.iou = float(config.get("iou", 0.5))
        self.imgsz = int(config.get("imgsz", 640))
        self.device = str(config.get("device", "auto"))
        self.max_detections = int(config.get("max_detections", 10))

    def detect(self, frame: Frame) -> List[Detection]:
        predict_kwargs = {
            "source": frame.color_bgr,
            "conf": self.conf,
            "iou": self.iou,
            "imgsz": self.imgsz,
            "verbose": False,
            "max_det": self.max_detections,
        }
        if self.device and self.device != "auto":
            predict_kwargs["device"] = self.device

        results = self.model.predict(**predict_kwargs)
        if not results:
            return []

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return []

        names = result.names or getattr(self.model, "names", {})
        boxes = result.boxes
        xyxy = boxes.xyxy.detach().cpu().numpy()
        confs = boxes.conf.detach().cpu().numpy()
        classes = boxes.cls.detach().cpu().numpy().astype(int)

        masks_np: Optional[np.ndarray] = None
        if result.masks is not None and result.masks.data is not None:
            masks_np = result.masks.data.detach().cpu().numpy()

        detections: List[Detection] = []
        h, w = frame.depth_m.shape[:2]
        for idx, (box, conf, class_id) in enumerate(zip(xyxy, confs, classes)):
            raw_name = str(names.get(int(class_id), int(class_id))) if isinstance(names, dict) else str(class_id)
            class_name = self.class_aliases.get(raw_name, raw_name)
            if self.allowed_classes and class_name not in self.allowed_classes and raw_name not in self.allowed_classes:
                continue

            mask = None
            if masks_np is not None and idx < len(masks_np):
                mask_f = cv2.resize(masks_np[idx].astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)
                mask = mask_f > 0.5

            detections.append(
                Detection(
                    class_id=int(class_id),
                    class_name=class_name,
                    confidence=float(conf),
                    bbox_xyxy=tuple(float(v) for v in box),
                    mask=mask,
                )
            )

        detections.sort(key=lambda item: item.confidence * max(item.area_px, 1.0), reverse=True)
        return detections

