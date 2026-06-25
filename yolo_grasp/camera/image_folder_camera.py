from __future__ import annotations

import time
from pathlib import Path
from typing import Mapping

import cv2
import numpy as np

from yolo_grasp.camera.base import CameraBackend
from yolo_grasp.config import resolve_path
from yolo_grasp.types import CameraIntrinsics, Frame


class ImageFolderCamera(CameraBackend):
    """Replay one color/depth pair from disk.

    Depth can be a .npy file in meters or a 16-bit png scaled by depth_scale_m.
    """

    def __init__(self, config: Mapping):
        self.color_path = resolve_path(config["color_path"])
        self.depth_path = resolve_path(config["depth_path"])
        self.depth_scale_m = float(config.get("depth_scale_m", 0.001))
        intr = config["intrinsics"]
        self.intrinsics = CameraIntrinsics(
            width=int(intr["width"]),
            height=int(intr["height"]),
            fx=float(intr["fx"]),
            fy=float(intr["fy"]),
            ppx=float(intr["ppx"]),
            ppy=float(intr["ppy"]),
            coeffs=tuple(float(v) for v in intr.get("coeffs", [])),
            model=str(intr.get("model", "pinhole")),
        )

    def start(self) -> None:
        if not self.color_path.exists():
            raise FileNotFoundError(self.color_path)
        if not self.depth_path.exists():
            raise FileNotFoundError(self.depth_path)

    def capture(self) -> Frame:
        color = cv2.imread(str(self.color_path), cv2.IMREAD_COLOR)
        if color is None:
            raise ValueError(f"Could not read color image: {self.color_path}")

        if self.depth_path.suffix.lower() == ".npy":
            depth_m = np.load(self.depth_path).astype(np.float32)
        else:
            raw = cv2.imread(str(self.depth_path), cv2.IMREAD_UNCHANGED)
            if raw is None:
                raise ValueError(f"Could not read depth image: {self.depth_path}")
            depth_m = raw.astype(np.float32) * self.depth_scale_m

        return Frame(color_bgr=color, depth_m=depth_m, intrinsics=self.intrinsics, timestamp_s=time.time())

    def stop(self) -> None:
        return None

