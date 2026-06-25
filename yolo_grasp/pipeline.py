from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from yolo_grasp.camera import create_camera
from yolo_grasp.config import resolve_path
from yolo_grasp.detection import create_detector
from yolo_grasp.hand import create_hand
from yolo_grasp.language import CommandIntent, CommandParser
from yolo_grasp.perception import ObjectLocalizer
from yolo_grasp.planning import GraspPlanner
from yolo_grasp.robot import create_arm
from yolo_grasp.safety import SafetyValidator
from yolo_grasp.types import GraspCandidate, PipelineError
from yolo_grasp.visualization import draw_debug, save_debug_image

LOGGER = logging.getLogger(__name__)


class GraspPipeline:
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

    def run_once(
        self,
        target_class: Optional[str] = None,
        spatial_hint: Optional[str] = None,
        command_text: Optional[str] = None,
        execute: Optional[bool] = None,
        save_debug: Optional[bool] = None,
    ) -> GraspCandidate:
        execute_motion = bool(self.runtime.get("execute_motion", False)) if execute is None else bool(execute)
        save_debug = bool(self.runtime.get("save_debug_image", True)) if save_debug is None else bool(save_debug)
        output_dir = resolve_path(self.runtime.get("output_dir", "outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)

        self.camera.start()
        try:
            intent = self._parse_command(command_text) if command_text else None
            target_class = target_class or (intent.target_class if intent else None)
            spatial_hint = spatial_hint or (intent.spatial_hint if intent else None)

            frame = self.camera.capture()
            detections = self.detector.detect(frame)
            LOGGER.info("Detected %d objects", len(detections))
            if not detections:
                raise PipelineError("no detections")

            objects = self.localizer.localize(frame, detections)
            LOGGER.info("Localized %d objects", len(objects))
            if not objects:
                raise PipelineError("no localized objects")

            target = self.planner.choose_target(objects, target_class, spatial_hint)
            candidate = self.planner.plan(target)
            self.safety.validate_candidate(candidate)
            LOGGER.info("Planned grasp: %s", candidate.description)

            if save_debug:
                stamp = time.strftime("%Y%m%d_%H%M%S")
                image = draw_debug(frame.color_bgr, detections, objects, candidate)
                debug_path = save_debug_image(output_dir / f"debug_{stamp}.jpg", image)
                LOGGER.info("Saved debug image: %s", debug_path)
                self._write_plan_json(output_dir / f"plan_{stamp}.json", candidate, execute_motion, intent, spatial_hint)

            if execute_motion:
                self.execute(candidate)
            else:
                LOGGER.info("execute_motion=false; planned only, no hardware motion")

            return candidate
        finally:
            self.camera.stop()

    def _parse_command(self, command_text: str) -> CommandIntent:
        intent = self.command_parser.parse(command_text)
        LOGGER.info(
            "Parsed command: target_class=%s spatial_hint=%s matched_alias=%s confidence=%.2f",
            intent.target_class,
            intent.spatial_hint,
            intent.matched_alias,
            intent.confidence,
        )
        for warning in intent.warnings:
            LOGGER.warning("Command parser: %s", warning)
        return intent

    def execute(self, candidate: GraspCandidate) -> None:
        LOGGER.warning("Executing grasp sequence. Keep emergency stop reachable when hardware is enabled.")
        self.arm.connect()
        self.hand.connect()
        try:
            self.hand.open()
            self.arm.move_pose(candidate.pre_grasp_pose_base)
            self.arm.move_pose(candidate.grasp_pose_base)
            self.hand.apply_profile(candidate.hand_profile)
            self.arm.move_pose(candidate.retreat_pose_base)
        except Exception:
            LOGGER.exception("Grasp execution failed; stopping hardware")
            self.arm.stop()
            self.hand.stop()
            raise
        finally:
            self.hand.disconnect()
            self.arm.disconnect()

    def _write_plan_json(
        self,
        path: Path,
        candidate: GraspCandidate,
        execute_motion: bool,
        intent: Optional[CommandIntent] = None,
        spatial_hint: Optional[str] = None,
    ) -> None:
        payload = {
            "execute_motion": execute_motion,
            "language_intent": command_intent_to_dict(intent),
            "spatial_hint": spatial_hint,
            "target_class": candidate.target.class_name,
            "target_score": candidate.target.score,
            "target_center_base_m": candidate.target.center_base_m.tolist(),
            "target_center_camera_m": candidate.target.center_camera_m.tolist(),
            "target_dimensions_base_m": candidate.target.dimensions_base_m.tolist(),
            "point_count": candidate.target.point_count,
            "hand_profile": candidate.hand_profile,
            "grasp_pose_base": candidate.grasp_pose_base.tolist(),
            "pre_grasp_pose_base": candidate.pre_grasp_pose_base.tolist(),
            "retreat_pose_base": candidate.retreat_pose_base.tolist(),
            "description": candidate.description,
            "metadata": candidate.metadata,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def command_intent_to_dict(intent: Optional[CommandIntent]) -> Optional[dict[str, Any]]:
    if intent is None:
        return None
    return {
        "raw_text": intent.raw_text,
        "normalized_text": intent.normalized_text,
        "target_class": intent.target_class,
        "matched_alias": intent.matched_alias,
        "spatial_hint": intent.spatial_hint,
        "confidence": intent.confidence,
        "warnings": list(intent.warnings),
    }
