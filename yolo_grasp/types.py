from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


Array = np.ndarray


@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    ppx: float
    ppy: float
    coeffs: Tuple[float, ...] = ()
    model: str = "pinhole"


@dataclass
class Frame:
    color_bgr: Array
    depth_m: Array
    intrinsics: CameraIntrinsics
    timestamp_s: float = 0.0


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: Tuple[float, float, float, float]
    mask: Optional[Array] = None

    @property
    def area_px(self) -> float:
        x1, y1, x2, y2 = self.bbox_xyxy
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


@dataclass
class ObjectPose:
    detection: Detection
    center_camera_m: Array
    center_base_m: Array
    dimensions_base_m: Array
    yaw_base_rad: float
    point_count: int
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def class_name(self) -> str:
        return self.detection.class_name


@dataclass
class GraspCandidate:
    target: ObjectPose
    grasp_pose_base: Array
    pre_grasp_pose_base: Array
    retreat_pose_base: Array
    hand_profile: str
    score: float
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MotionLimits:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    @classmethod
    def from_sequence(cls, values: Sequence[Sequence[float]]) -> "MotionLimits":
        if len(values) != 3 or any(len(pair) != 2 for pair in values):
            raise ValueError("workspace_limits_m must be [[x_min,x_max],[y_min,y_max],[z_min,z_max]]")
        return cls(
            float(values[0][0]),
            float(values[0][1]),
            float(values[1][0]),
            float(values[1][1]),
            float(values[2][0]),
            float(values[2][1]),
        )

    def contains(self, xyz: Sequence[float]) -> bool:
        x, y, z = map(float, xyz[:3])
        return (
            self.x_min <= x <= self.x_max
            and self.y_min <= y <= self.y_max
            and self.z_min <= z <= self.z_max
        )


class PipelineError(RuntimeError):
    """Base error for recoverable pipeline failures."""


class SafetyError(PipelineError):
    """Raised when a planned motion violates configured safety limits."""


class HardwareError(PipelineError):
    """Raised when a hardware adapter fails."""

