from __future__ import annotations

from typing import Mapping

from yolo_grasp.camera.base import CameraBackend
from yolo_grasp.camera.image_folder_camera import ImageFolderCamera
from yolo_grasp.camera.mock_camera import MockCamera
from yolo_grasp.camera.realsense_camera import RealSenseCamera


def create_camera(config: Mapping) -> CameraBackend:
    camera_type = str(config.get("type", "mock")).lower()
    if camera_type == "mock":
        return MockCamera(config.get("mock", {}))
    if camera_type == "realsense":
        return RealSenseCamera(config.get("realsense", {}))
    if camera_type in {"image", "image_folder", "file"}:
        return ImageFolderCamera(config.get("image_folder", {}))
    raise ValueError(f"Unsupported camera.type: {camera_type}")

