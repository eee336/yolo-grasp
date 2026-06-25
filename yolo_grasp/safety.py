from __future__ import annotations

from typing import Mapping

from yolo_grasp.types import GraspCandidate, MotionLimits, SafetyError


class SafetyValidator:
    def __init__(self, config: Mapping):
        self.enabled = bool(config.get("enabled", True))
        self.workspace_limits = MotionLimits.from_sequence(
            config.get("workspace_limits_m", [[0.15, 0.75], [-0.45, 0.45], [0.02, 0.55]])
        )
        self.min_grasp_z_m = float(config.get("min_grasp_z_m", 0.035))

    def validate_candidate(self, candidate: GraspCandidate) -> None:
        if not self.enabled:
            return
        self._validate_pose(candidate.pre_grasp_pose_base, "pre_grasp_pose_base")
        self._validate_pose(candidate.grasp_pose_base, "grasp_pose_base")
        self._validate_pose(candidate.retreat_pose_base, "retreat_pose_base")
        if float(candidate.grasp_pose_base[2]) < self.min_grasp_z_m:
            raise SafetyError(
                f"grasp z={candidate.grasp_pose_base[2]:.3f} is below min_grasp_z_m={self.min_grasp_z_m:.3f}"
            )

    def _validate_pose(self, pose, name: str) -> None:
        if not self.workspace_limits.contains(pose[:3]):
            raise SafetyError(f"{name} xyz={pose[:3].tolist()} is outside configured workspace limits")

