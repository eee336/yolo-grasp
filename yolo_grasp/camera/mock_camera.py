from __future__ import annotations

import time
from typing import Mapping

import numpy as np

from yolo_grasp.camera.base import CameraBackend
from yolo_grasp.types import CameraIntrinsics, Frame


class MockCamera(CameraBackend):
    """Synthetic RGB-D frame with a single upright bottle-like object."""

    def __init__(self, config: Mapping):
        width = int(config.get("width", 640))
        height = int(config.get("height", 480))
        self.intrinsics = CameraIntrinsics(
            width=width,
            height=height,
            fx=float(config.get("fx", 615.0)),
            fy=float(config.get("fy", 615.0)),
            ppx=float(config.get("ppx", width / 2.0)),
            ppy=float(config.get("ppy", height / 2.0)),
        )
        self.background_depth_m = float(config.get("background_depth_m", 1.2))
        self.object_depth_m = float(config.get("object_depth_m", 0.62))
        self.bbox_xyxy = tuple(config.get("bbox_xyxy", [270, 150, 370, 390]))
        self.class_name = str(config.get("class_name", "mineral_water_bottle"))

    def start(self) -> None:
        return None

    def capture(self) -> Frame:
        h, w = self.intrinsics.height, self.intrinsics.width
        color = np.zeros((h, w, 3), dtype=np.uint8)
        color[:, :] = (38, 38, 38)
        depth = np.full((h, w), self.background_depth_m, dtype=np.float32)

        x1, y1, x2, y2 = [int(v) for v in self.bbox_xyxy]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)

        depth[y1:y2, x1:x2] = self.object_depth_m
        color[y1:y2, x1:x2] = (210, 225, 235)

        cap_h = max(12, int((y2 - y1) * 0.12))
        cap_w = max(18, int((x2 - x1) * 0.45))
        cx = (x1 + x2) // 2
        color[y1 : y1 + cap_h, cx - cap_w // 2 : cx + cap_w // 2] = (30, 90, 220)

        label_h = max(24, int((y2 - y1) * 0.18))
        label_y1 = y1 + int((y2 - y1) * 0.45)
        color[label_y1 : label_y1 + label_h, x1 + 6 : x2 - 6] = (235, 235, 70)

        return Frame(color_bgr=color, depth_m=depth, intrinsics=self.intrinsics, timestamp_s=time.time())

    def stop(self) -> None:
        return None

