from __future__ import annotations

import time
from typing import Mapping

import cv2
import numpy as np

from yolo_grasp.camera.base import CameraBackend
from yolo_grasp.types import CameraIntrinsics, Frame, HardwareError


class OpenCVCamera(CameraBackend):
    """Local webcam backend for UI testing.

    Ordinary webcams do not provide metric depth. This backend creates a constant
    depth image so the rest of the RGB-D pipeline can be exercised in mock/local
    UI tests. Do not use this backend for real robot grasp execution.
    """

    def __init__(self, config: Mapping):
        self.config = config
        self.device_index = int(config.get("device_index", 0))
        self.width = int(config.get("width", 640))
        self.height = int(config.get("height", 480))
        self.fps = int(config.get("fps", 30))
        self.constant_depth_m = float(config.get("constant_depth_m", 0.65))
        self.flip_horizontal = bool(config.get("flip_horizontal", False))
        self.cap = None
        self.intrinsics = CameraIntrinsics(
            width=self.width,
            height=self.height,
            fx=float(config.get("fx", 615.0)),
            fy=float(config.get("fy", 615.0)),
            ppx=float(config.get("ppx", self.width / 2.0)),
            ppy=float(config.get("ppy", self.height / 2.0)),
        )

    def start(self) -> None:
        self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            raise HardwareError(f"Could not open local camera device_index={self.device_index}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.stop()
            raise HardwareError(f"Local camera opened but did not return frames: device_index={self.device_index}")

    def capture(self) -> Frame:
        if self.cap is None:
            raise HardwareError("OpenCV camera is not started")
        ok, color_bgr = self.cap.read()
        if not ok or color_bgr is None:
            raise HardwareError("OpenCV camera returned an empty frame")
        if self.flip_horizontal:
            color_bgr = cv2.flip(color_bgr, 1)
        if color_bgr.shape[1] != self.width or color_bgr.shape[0] != self.height:
            color_bgr = cv2.resize(color_bgr, (self.width, self.height), interpolation=cv2.INTER_AREA)
        depth_m = np.full((self.height, self.width), self.constant_depth_m, dtype=np.float32)
        return Frame(color_bgr=color_bgr, depth_m=depth_m, intrinsics=self.intrinsics, timestamp_s=time.time())

    def stop(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self.cap = None

