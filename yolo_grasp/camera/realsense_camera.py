from __future__ import annotations

import time
from typing import Mapping

import numpy as np

from yolo_grasp.camera.base import CameraBackend
from yolo_grasp.types import CameraIntrinsics, Frame, HardwareError


class RealSenseCamera(CameraBackend):
    """Intel RealSense RGB-D camera using pyrealsense2."""

    def __init__(self, config: Mapping):
        self.config = config
        self.pipeline = None
        self.align = None
        self.depth_scale = 0.001
        self.profile = None
        self._rs = None
        self._filters = []

    def start(self) -> None:
        try:
            import pyrealsense2 as rs
        except ImportError as exc:
            raise HardwareError("pyrealsense2 is required for camera.type=realsense") from exc

        self._rs = rs
        self.pipeline = rs.pipeline()
        cfg = rs.config()

        serial = str(self.config.get("serial", "")).strip()
        if serial:
            cfg.enable_device(serial)

        width = int(self.config.get("width", 640))
        height = int(self.config.get("height", 480))
        fps = int(self.config.get("fps", 30))
        cfg.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        cfg.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)

        self.profile = self.pipeline.start(cfg)
        device = self.profile.get_device()
        depth_sensor = device.first_depth_sensor()
        self.depth_scale = float(depth_sensor.get_depth_scale())

        if bool(self.config.get("align_depth_to_color", True)):
            self.align = rs.align(rs.stream.color)

        filters = self.config.get("filters", {})
        self._filters = []
        if filters.get("decimation", False):
            self._filters.append(rs.decimation_filter())
        if filters.get("spatial", False):
            self._filters.append(rs.spatial_filter())
        if filters.get("temporal", False):
            self._filters.append(rs.temporal_filter())
        if filters.get("hole_filling", False):
            self._filters.append(rs.hole_filling_filter())

        for _ in range(int(self.config.get("warmup_frames", 30))):
            self.pipeline.wait_for_frames()

    def capture(self) -> Frame:
        if self.pipeline is None or self._rs is None:
            raise HardwareError("RealSense camera is not started")

        frames = self.pipeline.wait_for_frames(timeout_ms=int(self.config.get("timeout_ms", 5000)))
        if self.align is not None:
            frames = self.align.process(frames)

        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()
        if not depth_frame or not color_frame:
            raise HardwareError("RealSense returned incomplete frames")

        for frame_filter in self._filters:
            depth_frame = frame_filter.process(depth_frame)

        depth_m = np.asanyarray(depth_frame.get_data()).astype(np.float32) * self.depth_scale
        color_bgr = np.asanyarray(color_frame.get_data()).copy()

        intr = color_frame.profile.as_video_stream_profile().get_intrinsics()
        intrinsics = CameraIntrinsics(
            width=int(intr.width),
            height=int(intr.height),
            fx=float(intr.fx),
            fy=float(intr.fy),
            ppx=float(intr.ppx),
            ppy=float(intr.ppy),
            coeffs=tuple(float(v) for v in intr.coeffs),
            model=str(intr.model),
        )
        return Frame(color_bgr=color_bgr, depth_m=depth_m, intrinsics=intrinsics, timestamp_s=time.time())

    def stop(self) -> None:
        if self.pipeline is not None:
            self.pipeline.stop()
        self.pipeline = None

