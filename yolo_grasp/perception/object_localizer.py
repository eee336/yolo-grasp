from __future__ import annotations

import logging
from typing import List, Mapping, Sequence

import numpy as np

from yolo_grasp.perception.depth_utils import (
    detection_to_mask,
    erode_mask,
    masked_point_cloud,
    reject_percentile_outliers,
)
from yolo_grasp.planning.transforms import as_transform, transform_points
from yolo_grasp.types import Detection, Frame, ObjectPose, PipelineError

LOGGER = logging.getLogger(__name__)


class ObjectLocalizer:
    def __init__(self, config: Mapping):
        self.config = config
        self.camera_to_base = as_transform(config.get("transform_camera_to_base", np.eye(4).tolist()))
        self.depth_min_m = float(config.get("depth_min_m", 0.15))
        self.depth_max_m = float(config.get("depth_max_m", 1.6))
        self.mask_erode_px = int(config.get("mask_erode_px", 3))
        self.point_stride = int(config.get("point_stride", 2))
        self.min_points = int(config.get("min_points", 80))
        self.outlier_percentiles = tuple(config.get("outlier_percentiles", [3.0, 97.0]))
        self.workspace_limits = config.get("workspace_limits_m")

    def localize(self, frame: Frame, detections: Sequence[Detection]) -> List[ObjectPose]:
        poses: List[ObjectPose] = []
        for detection in detections:
            try:
                pose = self._localize_one(frame, detection)
            except PipelineError as exc:
                LOGGER.warning("Skipping detection %s: %s", detection.class_name, exc)
                continue
            poses.append(pose)

        poses.sort(key=lambda item: item.score, reverse=True)
        return poses

    def _localize_one(self, frame: Frame, detection: Detection) -> ObjectPose:
        image_shape = frame.depth_m.shape[:2]
        mask = detection_to_mask(detection, image_shape)
        mask = erode_mask(mask, self.mask_erode_px)

        points_camera = masked_point_cloud(
            frame.depth_m,
            mask,
            frame.intrinsics,
            self.depth_min_m,
            self.depth_max_m,
            stride=max(1, self.point_stride),
        )
        if len(points_camera) < self.min_points:
            raise PipelineError(f"not enough valid depth points ({len(points_camera)} < {self.min_points})")

        points_camera = reject_percentile_outliers(
            points_camera,
            lower=float(self.outlier_percentiles[0]),
            upper=float(self.outlier_percentiles[1]),
        )
        if len(points_camera) < self.min_points:
            raise PipelineError(f"not enough points after outlier rejection ({len(points_camera)})")

        points_base = transform_points(self.camera_to_base, points_camera)
        center_camera = np.median(points_camera, axis=0)
        center_base = np.median(points_base, axis=0)
        dimensions = np.percentile(points_base, 95, axis=0) - np.percentile(points_base, 5, axis=0)
        yaw = estimate_yaw_from_points(points_base)
        score = float(detection.confidence) * min(1.0, len(points_base) / 800.0)

        return ObjectPose(
            detection=detection,
            center_camera_m=center_camera.astype(np.float64),
            center_base_m=center_base.astype(np.float64),
            dimensions_base_m=dimensions.astype(np.float64),
            yaw_base_rad=float(yaw),
            point_count=int(len(points_base)),
            score=score,
            metadata={
                "bbox_xyxy": detection.bbox_xyxy,
                "center_camera_m": center_camera.tolist(),
                "dimensions_base_m": dimensions.tolist(),
            },
        )


def estimate_yaw_from_points(points_base: np.ndarray) -> float:
    if len(points_base) < 8:
        return 0.0
    xy = points_base[:, :2]
    xy = xy - np.mean(xy, axis=0)
    cov = xy.T @ xy / max(1, len(xy) - 1)
    eigvals, eigvecs = np.linalg.eigh(cov)
    axis = eigvecs[:, int(np.argmax(eigvals))]
    return float(np.arctan2(axis[1], axis[0]))

