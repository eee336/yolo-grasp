from __future__ import annotations

from typing import Mapping, Optional, Sequence

import numpy as np

from yolo_grasp.types import GraspCandidate, ObjectPose, PipelineError


class GraspPlanner:
    """Rule-based planner for upright bottle-like objects on a tabletop."""

    def __init__(self, config: Mapping):
        self.config = config
        self.mode = str(config.get("mode", "top_down"))
        self.table_height_m = float(config.get("table_height_m", 0.0))
        self.approach_offset_m = float(config.get("approach_offset_m", 0.12))
        self.lift_offset_m = float(config.get("lift_offset_m", 0.16))
        self.tcp_orientation_rvec = np.asarray(
            config.get("tcp_orientation_rvec", [3.14159, 0.0, 0.0]), dtype=np.float64
        )
        self.default_profile = str(config.get("default_hand_profile", "bottle_cylindrical"))
        self.per_class = config.get("per_class", {})

    def choose_target(
        self,
        objects: Sequence[ObjectPose],
        requested_class: Optional[str] = None,
        spatial_hint: Optional[str] = None,
    ) -> ObjectPose:
        if not objects:
            raise PipelineError("no localized objects available")
        candidates = list(objects)
        if requested_class:
            candidates = [obj for obj in candidates if obj.class_name == requested_class]
            if not candidates:
                names = ", ".join(obj.class_name for obj in objects)
                raise PipelineError(f"requested class {requested_class!r} not found; visible classes: {names}")
        if spatial_hint:
            candidates = rank_by_spatial_hint(candidates, spatial_hint)
        return candidates[0]

    def plan(self, target: ObjectPose) -> GraspCandidate:
        if self.mode != "top_down":
            raise PipelineError(f"Unsupported grasp.mode={self.mode!r}; implemented mode is top_down")

        class_cfg = self.per_class.get(target.class_name, {})
        hand_profile = str(class_cfg.get("hand_profile", self.default_profile))
        xy_offset = np.asarray(class_cfg.get("xy_offset_m", [0.0, 0.0]), dtype=np.float64)
        grasp_height_above_table = float(class_cfg.get("grasp_height_above_table_m", 0.09))
        tcp_z_offset = float(class_cfg.get("tcp_z_offset_m", 0.0))

        xyz = np.asarray(target.center_base_m, dtype=np.float64).copy()
        xyz[:2] += xy_offset
        if bool(class_cfg.get("use_table_height", True)):
            xyz[2] = self.table_height_m + grasp_height_above_table + tcp_z_offset
        else:
            xyz[2] += tcp_z_offset

        pose = np.r_[xyz, self.tcp_orientation_rvec]
        pre = pose.copy()
        pre[2] += self.approach_offset_m
        retreat = pose.copy()
        retreat[2] += self.lift_offset_m

        size = target.dimensions_base_m
        score = float(target.score)
        if np.any(size > np.asarray(class_cfg.get("max_dimensions_m", [0.20, 0.20, 0.35]), dtype=np.float64)):
            score *= 0.75

        return GraspCandidate(
            target=target,
            grasp_pose_base=pose.astype(np.float64),
            pre_grasp_pose_base=pre.astype(np.float64),
            retreat_pose_base=retreat.astype(np.float64),
            hand_profile=hand_profile,
            score=score,
            description=(
                f"top_down grasp on {target.class_name}: "
                f"pre={np.round(pre[:3], 4).tolist()} grasp={np.round(pose[:3], 4).tolist()}"
            ),
            metadata={
                "grasp_height_above_table_m": grasp_height_above_table,
                "target_dimensions_base_m": size.tolist(),
            },
        )


def rank_by_spatial_hint(objects: Sequence[ObjectPose], spatial_hint: str) -> list[ObjectPose]:
    hint = str(spatial_hint).lower()
    objects = list(objects)
    if not objects:
        return []

    if hint == "left":
        return sorted(objects, key=lambda obj: bbox_center_x(obj))
    if hint == "right":
        return sorted(objects, key=lambda obj: bbox_center_x(obj), reverse=True)
    if hint == "top":
        return sorted(objects, key=lambda obj: bbox_center_y(obj))
    if hint == "bottom":
        return sorted(objects, key=lambda obj: bbox_center_y(obj), reverse=True)
    if hint == "nearest":
        return sorted(objects, key=lambda obj: float(np.linalg.norm(obj.center_camera_m)))
    if hint == "farthest":
        return sorted(objects, key=lambda obj: float(np.linalg.norm(obj.center_camera_m)), reverse=True)
    if hint == "front":
        return sorted(objects, key=lambda obj: float(obj.center_base_m[0]))
    if hint == "back":
        return sorted(objects, key=lambda obj: float(obj.center_base_m[0]), reverse=True)
    if hint == "center":
        return sorted(objects, key=lambda obj: abs(bbox_center_x(obj) - 0.5 * bbox_width_reference(objects)))
    raise PipelineError(f"unsupported spatial_hint={spatial_hint!r}")


def bbox_center_x(obj: ObjectPose) -> float:
    x1, _, x2, _ = obj.detection.bbox_xyxy
    return 0.5 * (float(x1) + float(x2))


def bbox_center_y(obj: ObjectPose) -> float:
    _, y1, _, y2 = obj.detection.bbox_xyxy
    return 0.5 * (float(y1) + float(y2))


def bbox_width_reference(objects: Sequence[ObjectPose]) -> float:
    x_values = []
    for obj in objects:
        x_values.extend([float(obj.detection.bbox_xyxy[0]), float(obj.detection.bbox_xyxy[2])])
    return max(x_values) + min(x_values) if x_values else 0.0
