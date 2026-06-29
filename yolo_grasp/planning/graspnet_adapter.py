from __future__ import annotations

import json
import logging
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from yolo_grasp.config import resolve_path
from yolo_grasp.perception.depth_utils import detection_to_mask
from yolo_grasp.planning.transforms import as_transform, transform_to_pose6
from yolo_grasp.types import Frame, GraspCandidate, ObjectPose, PipelineError

LOGGER = logging.getLogger(__name__)


@dataclass
class GraspNetRawCandidate:
    translation_camera_m: np.ndarray
    rotation_camera: np.ndarray
    score: float
    width_m: Optional[float] = None
    depth_m: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class GraspNetAdapter:
    """Adapter between this project and external GraspNet/AnyGrasp inference code.

    The adapter intentionally uses a small file-based protocol because common GraspNet
    implementations are research repos with heavy dependencies. This project prepares
    RGB-D input and consumes grasp candidates; the external runner owns model loading.
    """

    def __init__(self, config: Mapping | None = None):
        self.config = dict(config or {})
        self.backend = str(self.config.get("backend", "disabled")).lower()
        self.request_dir = resolve_path(self.config.get("request_dir", "outputs/graspnet_requests"))
        self.keep_io = bool(self.config.get("keep_io", True))
        self.timeout_s = float(self.config.get("timeout_s", 120.0))
        self.min_score = float(self.config.get("min_score", 0.1))
        self.max_candidates = int(self.config.get("max_candidates", 30))
        self.target_center_tolerance_m = float(self.config.get("target_center_tolerance_m", 0.20))
        self.width_range_m = tuple(float(v) for v in self.config.get("width_range_m", [0.0, 0.16]))
        self.pre_grasp_offset_m = float(self.config.get("pre_grasp_offset_m", 0.12))
        self.retreat_offset_m = float(self.config.get("retreat_offset_m", 0.16))
        self.pregrasp_axis = str(self.config.get("pregrasp_axis", "base_z")).lower()
        self.grasp_to_tcp_transform = as_transform(self.config.get("grasp_to_tcp_transform", np.eye(4).tolist()))

    def plan(
        self,
        frame: Frame,
        target: ObjectPose,
        camera_to_base: np.ndarray,
        hand_profile: str,
    ) -> GraspCandidate:
        camera_to_base = as_transform(camera_to_base)
        raw_candidates = self._run_backend(frame, target)
        raw_candidates = self._filter_candidates(raw_candidates, target)
        if not raw_candidates:
            raise PipelineError("GraspNet produced no valid grasp candidates")

        raw = raw_candidates[0]
        grasp_pose_base = self._candidate_to_tcp_pose(raw, camera_to_base)
        pre = grasp_pose_base.copy()
        retreat = grasp_pose_base.copy()
        approach = self._approach_axis_base(raw, camera_to_base)
        pre[:3] -= approach * self.pre_grasp_offset_m
        retreat[:3] -= approach * self.retreat_offset_m

        return GraspCandidate(
            target=target,
            grasp_pose_base=grasp_pose_base.astype(np.float64),
            pre_grasp_pose_base=pre.astype(np.float64),
            retreat_pose_base=retreat.astype(np.float64),
            hand_profile=hand_profile,
            score=float(raw.score),
            description=(
                f"graspnet grasp on {target.class_name}: score={raw.score:.3f} "
                f"xyz={np.round(grasp_pose_base[:3], 4).tolist()}"
            ),
            metadata={
                "planner": "graspnet",
                "backend": self.backend,
                "raw_score": raw.score,
                "raw_width_m": raw.width_m,
                "raw_depth_m": raw.depth_m,
                "raw_translation_camera_m": raw.translation_camera_m.tolist(),
                "raw_rotation_camera": raw.rotation_camera.tolist(),
                "raw_metadata": raw.metadata,
            },
        )

    def _run_backend(self, frame: Frame, target: ObjectPose) -> list[GraspNetRawCandidate]:
        if self.backend in {"disabled", "none"}:
            raise PipelineError("GraspNet backend is disabled")
        if self.backend == "synthetic":
            return [self._synthetic_candidate(frame, target)]
        if self.backend == "file":
            output_path = resolve_path(self.config["output_path"])
            return self._load_candidates(output_path)
        if self.backend == "command":
            input_path, output_path = self._write_request(frame, target)
            self._run_command(input_path, output_path)
            return self._load_candidates(output_path)
        raise PipelineError(f"Unsupported GraspNet backend: {self.backend}")

    def _write_request(self, frame: Frame, target: ObjectPose) -> tuple[Path, Path]:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.request_dir.mkdir(parents=True, exist_ok=True)
        input_path = self.request_dir / f"graspnet_input_{stamp}.npz"
        output_path = self.request_dir / f"graspnet_output_{stamp}.json"

        mask = detection_to_mask(target.detection, frame.depth_m.shape[:2])
        np.savez_compressed(
            input_path,
            color_bgr=frame.color_bgr,
            depth_m=frame.depth_m.astype(np.float32),
            target_mask=mask.astype(np.uint8),
            bbox_xyxy=np.asarray(target.detection.bbox_xyxy, dtype=np.float32),
            intrinsics=np.asarray(
                [
                    frame.intrinsics.width,
                    frame.intrinsics.height,
                    frame.intrinsics.fx,
                    frame.intrinsics.fy,
                    frame.intrinsics.ppx,
                    frame.intrinsics.ppy,
                ],
                dtype=np.float64,
            ),
            center_camera_m=target.center_camera_m.astype(np.float64),
            center_base_m=target.center_base_m.astype(np.float64),
            class_name=np.asarray([target.class_name]),
        )
        return input_path, output_path

    def _run_command(self, input_path: Path, output_path: Path) -> None:
        command_template = self.config.get("command")
        if not command_template:
            raise PipelineError("grasp.graspnet.command is required for backend=command")

        values = {
            "input_npz": str(input_path),
            "output_json": str(output_path),
            "output_path": str(output_path),
        }
        if isinstance(command_template, str):
            command = shlex.split(command_template.format(**values))
        else:
            command = [str(part).format(**values) for part in command_template]

        cwd = self.config.get("working_dir")
        LOGGER.info("Running GraspNet command: %s", command)
        result = subprocess.run(
            command,
            cwd=str(resolve_path(cwd)) if cwd else None,
            timeout=self.timeout_s,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            LOGGER.info("GraspNet stdout:\n%s", result.stdout)
        if result.stderr:
            LOGGER.warning("GraspNet stderr:\n%s", result.stderr)
        if result.returncode != 0:
            raise PipelineError(f"GraspNet command failed with return code {result.returncode}")
        if not output_path.exists():
            raise PipelineError(f"GraspNet command did not create output file: {output_path}")

    def _load_candidates(self, output_path: Path) -> list[GraspNetRawCandidate]:
        if output_path.suffix.lower() == ".json":
            return self._load_json_candidates(output_path)
        if output_path.suffix.lower() == ".npy":
            return self._load_graspnet_api_npy(output_path)
        raise PipelineError(f"Unsupported GraspNet output format: {output_path}")

    def _load_json_candidates(self, output_path: Path) -> list[GraspNetRawCandidate]:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        grasps = payload.get("grasps", payload if isinstance(payload, list) else [])
        candidates = []
        for item in grasps:
            candidates.append(parse_json_grasp(item))
        return sorted(candidates, key=lambda item: item.score, reverse=True)[: self.max_candidates]

    def _load_graspnet_api_npy(self, output_path: Path) -> list[GraspNetRawCandidate]:
        try:
            from graspnetAPI import GraspGroup
        except ImportError as exc:
            raise PipelineError("graspnetAPI is required to read .npy GraspGroup outputs") from exc

        group = GraspGroup()
        loaded = group.from_npy(str(output_path))
        if loaded is not None:
            group = loaded

        candidates = []
        for idx in range(len(group)):
            grasp = group[idx]
            candidates.append(
                GraspNetRawCandidate(
                    translation_camera_m=np.asarray(grasp.translation, dtype=np.float64),
                    rotation_camera=np.asarray(grasp.rotation_matrix, dtype=np.float64),
                    score=float(grasp.score),
                    width_m=float(grasp.width),
                    depth_m=float(getattr(grasp, "depth", 0.0)),
                    metadata={"source_index": idx, "format": "graspnetAPI_npy"},
                )
            )
        return sorted(candidates, key=lambda item: item.score, reverse=True)[: self.max_candidates]

    def _filter_candidates(
        self,
        candidates: Sequence[GraspNetRawCandidate],
        target: ObjectPose,
    ) -> list[GraspNetRawCandidate]:
        valid = []
        lo_width, hi_width = self.width_range_m
        for candidate in candidates:
            if candidate.score < self.min_score:
                continue
            if candidate.width_m is not None and not (lo_width <= candidate.width_m <= hi_width):
                continue
            distance = float(np.linalg.norm(candidate.translation_camera_m - target.center_camera_m))
            if distance > self.target_center_tolerance_m:
                continue
            candidate.metadata["target_center_distance_m"] = distance
            valid.append(candidate)
        return sorted(valid, key=lambda item: item.score, reverse=True)[: self.max_candidates]

    def _candidate_to_tcp_pose(self, candidate: GraspNetRawCandidate, camera_to_base: np.ndarray) -> np.ndarray:
        grasp_camera = np.eye(4, dtype=np.float64)
        grasp_camera[:3, :3] = candidate.rotation_camera
        grasp_camera[:3, 3] = candidate.translation_camera_m
        tcp_base = camera_to_base @ grasp_camera @ self.grasp_to_tcp_transform
        return transform_to_pose6(tcp_base)

    def _approach_axis_base(self, candidate: GraspNetRawCandidate, camera_to_base: np.ndarray) -> np.ndarray:
        if self.pregrasp_axis == "base_z":
            return np.asarray([0.0, 0.0, -1.0], dtype=np.float64)
        if self.pregrasp_axis == "grasp_z":
            axis_camera = candidate.rotation_camera[:, 2]
            axis_base = camera_to_base[:3, :3] @ axis_camera
            norm = float(np.linalg.norm(axis_base))
            if norm < 1e-9:
                return np.asarray([0.0, 0.0, -1.0], dtype=np.float64)
            return axis_base / norm
        raise PipelineError(f"Unsupported graspnet.pregrasp_axis={self.pregrasp_axis!r}")

    def _synthetic_candidate(self, frame: Frame, target: ObjectPose) -> GraspNetRawCandidate:
        rotation_camera = np.asarray(self.config.get("synthetic_rotation_camera", np.eye(3).tolist()), dtype=np.float64)
        translation = np.asarray(target.center_camera_m, dtype=np.float64).copy()
        z_offset = float(self.config.get("synthetic_z_offset_m", 0.0))
        translation[2] += z_offset
        return GraspNetRawCandidate(
            translation_camera_m=translation,
            rotation_camera=rotation_camera,
            score=float(self.config.get("synthetic_score", 0.80)),
            width_m=float(self.config.get("synthetic_width_m", 0.08)),
            depth_m=float(self.config.get("synthetic_depth_m", 0.04)),
            metadata={"source": "synthetic", "frame_timestamp_s": frame.timestamp_s},
        )


def parse_json_grasp(item: Mapping[str, Any]) -> GraspNetRawCandidate:
    translation = item.get("translation_camera_m", item.get("translation", item.get("center_camera_m")))
    rotation = item.get("rotation_camera", item.get("rotation_matrix", item.get("rotation")))
    pose = item.get("pose_matrix_camera", item.get("pose_matrix"))
    if pose is not None:
        pose_arr = np.asarray(pose, dtype=np.float64)
        if pose_arr.shape != (4, 4):
            raise PipelineError(f"pose_matrix_camera must be 4x4, got {pose_arr.shape}")
        translation = pose_arr[:3, 3]
        rotation = pose_arr[:3, :3]
    if translation is None or rotation is None:
        raise PipelineError("Each GraspNet JSON grasp needs translation_camera_m and rotation_camera")

    rotation_arr = np.asarray(rotation, dtype=np.float64)
    if rotation_arr.shape != (3, 3):
        raise PipelineError(f"rotation_camera must be 3x3, got {rotation_arr.shape}")

    return GraspNetRawCandidate(
        translation_camera_m=np.asarray(translation, dtype=np.float64),
        rotation_camera=rotation_arr,
        score=float(item.get("score", 0.0)),
        width_m=optional_float(item.get("width_m", item.get("width"))),
        depth_m=optional_float(item.get("depth_m", item.get("depth"))),
        metadata=dict(item.get("metadata", {})),
    )


def optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)

