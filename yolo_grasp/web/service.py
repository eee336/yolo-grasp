from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import cv2
import numpy as np

from yolo_grasp.camera import create_camera
from yolo_grasp.config import resolve_path
from yolo_grasp.detection import create_detector
from yolo_grasp.hand import create_hand
from yolo_grasp.language import CommandIntent, CommandParser
from yolo_grasp.perception import ObjectLocalizer
from yolo_grasp.planning import GraspPlanner
from yolo_grasp.robot import create_arm
from yolo_grasp.safety import SafetyValidator
from yolo_grasp.types import Detection, Frame, GraspCandidate, ObjectPose, PipelineError
from yolo_grasp.visualization import draw_debug, save_debug_image

LOGGER = logging.getLogger(__name__)


@dataclass
class SceneSnapshot:
    frame: Frame
    detections: list[Detection]
    objects: list[ObjectPose]
    captured_at_s: float


class WebGraspService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.runtime = config.get("runtime", {})
        self.camera = create_camera(config.get("camera", {}))
        self.detector = create_detector(config.get("detector", {}))
        self.localizer = ObjectLocalizer(config.get("localization", {}))
        self.planner = GraspPlanner(config.get("grasp", {}))
        self.command_parser = CommandParser(config.get("language", {}))
        self.safety = SafetyValidator(config.get("safety", {}))
        self.arm = create_arm(config.get("robot", {}))
        self.hand = create_hand(config.get("hand", {}))
        self._lock = threading.RLock()
        self._started = False
        self._latest: Optional[SceneSnapshot] = None
        self._last_error: Optional[str] = None

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self.camera.start()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if self._started:
                self.camera.stop()
            self._started = False

    def class_options(self) -> list[dict[str, Any]]:
        language = self.config.get("language", {})
        aliases = language.get("aliases", {})
        yolo = self.config.get("detector", {}).get("yolo", {})
        allowed = list(yolo.get("allowed_classes", []))
        names = sorted(set(aliases.keys()) | set(allowed))
        if not names:
            mock_name = self.config.get("detector", {}).get("mock", {}).get("class_name")
            if mock_name:
                names = [str(mock_name)]
        return [{"class_name": name, "aliases": aliases.get(name, [])} for name in names]

    def capture_scene(self) -> SceneSnapshot:
        with self._lock:
            self.start()
            frame = self.camera.capture()
            detections = self.detector.detect(frame)
            objects = self.localizer.localize(frame, detections) if detections else []
            snapshot = SceneSnapshot(
                frame=frame,
                detections=detections,
                objects=objects,
                captured_at_s=time.time(),
            )
            self._latest = snapshot
            self._last_error = None
            return snapshot

    def latest_or_capture(self, max_age_s: float = 0.25) -> SceneSnapshot:
        with self._lock:
            if self._latest and time.time() - self._latest.captured_at_s <= max_age_s:
                return self._latest
        return self.capture_scene()

    def annotated_jpeg(self, quality: int = 82) -> bytes:
        try:
            snapshot = self.capture_scene()
            image = draw_debug(snapshot.frame.color_bgr, snapshot.detections, snapshot.objects, None)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Could not capture annotated frame")
            self._last_error = str(exc)
            image = error_frame(str(exc))
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            raise PipelineError("Could not encode JPEG frame")
        return encoded.tobytes()

    def scene_status(self) -> dict[str, Any]:
        try:
            snapshot = self.latest_or_capture()
            return {
                "ok": True,
                "error": None,
                "captured_at_s": snapshot.captured_at_s,
                "detections": [detection_to_dict(item) for item in snapshot.detections],
                "objects": [object_to_dict(item) for item in snapshot.objects],
                "classes": self.class_options(),
                "camera": self.config.get("camera", {}).get("type", "unknown"),
                "detector": self.config.get("detector", {}).get("type", "unknown"),
                "grasp_mode": self.config.get("grasp", {}).get("mode", "top_down"),
                "execute_motion_default": bool(self.runtime.get("execute_motion", False)),
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Could not build scene status")
            self._last_error = str(exc)
            return {
                "ok": False,
                "error": str(exc),
                "detections": [],
                "objects": [],
                "classes": self.class_options(),
            }

    def plan_or_execute(
        self,
        target_class: Optional[str] = None,
        spatial_hint: Optional[str] = None,
        command_text: Optional[str] = None,
        execute: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            intent = self.command_parser.parse(command_text) if command_text else None
            target_class = target_class or (intent.target_class if intent else None)
            spatial_hint = spatial_hint or (intent.spatial_hint if intent else None)

            snapshot = self.capture_scene()
            if not snapshot.detections:
                raise PipelineError("no detections")
            if not snapshot.objects:
                raise PipelineError("no localized objects")

            target = self.planner.choose_target(snapshot.objects, target_class, spatial_hint)
            candidate = self.planner.plan(target, frame=snapshot.frame, camera_to_base=self.localizer.camera_to_base)
            self.safety.validate_candidate(candidate)

            output_dir = resolve_path(self.runtime.get("output_dir", "outputs"))
            output_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            debug_image = draw_debug(snapshot.frame.color_bgr, snapshot.detections, snapshot.objects, candidate)
            debug_path = save_debug_image(output_dir / f"web_debug_{stamp}.jpg", debug_image)

            if execute:
                self.execute(candidate)

            return {
                "ok": True,
                "executed": execute,
                "intent": command_intent_to_dict(intent),
                "candidate": candidate_to_dict(candidate),
                "debug_image": str(debug_path),
                "selected_target": object_to_dict(target),
            }

    def execute(self, candidate: GraspCandidate) -> None:
        LOGGER.warning("Executing grasp sequence from web console")
        self.arm.connect()
        self.hand.connect()
        try:
            self.hand.open()
            self.arm.move_pose(candidate.pre_grasp_pose_base)
            self.arm.move_pose(candidate.grasp_pose_base)
            self.hand.apply_profile(candidate.hand_profile)
            self.arm.move_pose(candidate.retreat_pose_base)
        except Exception:
            LOGGER.exception("Web grasp execution failed; stopping hardware")
            self.arm.stop()
            self.hand.stop()
            raise
        finally:
            self.hand.disconnect()
            self.arm.disconnect()


def detection_to_dict(detection: Detection) -> dict[str, Any]:
    return {
        "class_id": detection.class_id,
        "class_name": detection.class_name,
        "confidence": detection.confidence,
        "bbox_xyxy": list(detection.bbox_xyxy),
        "has_mask": detection.mask is not None,
    }


def object_to_dict(obj: ObjectPose) -> dict[str, Any]:
    return {
        "class_name": obj.class_name,
        "confidence": obj.detection.confidence,
        "bbox_xyxy": list(obj.detection.bbox_xyxy),
        "center_camera_m": obj.center_camera_m.tolist(),
        "center_base_m": obj.center_base_m.tolist(),
        "dimensions_base_m": obj.dimensions_base_m.tolist(),
        "point_count": obj.point_count,
        "score": obj.score,
    }


def candidate_to_dict(candidate: GraspCandidate) -> dict[str, Any]:
    return {
        "target_class": candidate.target.class_name,
        "score": candidate.score,
        "description": candidate.description,
        "hand_profile": candidate.hand_profile,
        "grasp_pose_base": candidate.grasp_pose_base.tolist(),
        "pre_grasp_pose_base": candidate.pre_grasp_pose_base.tolist(),
        "retreat_pose_base": candidate.retreat_pose_base.tolist(),
        "metadata": candidate.metadata,
    }


def command_intent_to_dict(intent: Optional[CommandIntent]) -> Optional[dict[str, Any]]:
    if intent is None:
        return None
    return {
        "raw_text": intent.raw_text,
        "target_class": intent.target_class,
        "matched_alias": intent.matched_alias,
        "spatial_hint": intent.spatial_hint,
        "confidence": intent.confidence,
        "warnings": list(intent.warnings),
    }


def error_frame(message: str) -> np.ndarray:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (32, 32, 32)
    cv2.putText(image, "Camera unavailable", (36, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (80, 180, 255), 2)
    wrapped = str(message)[:90]
    cv2.putText(image, wrapped, (36, 252), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (230, 230, 230), 1)
    return image

