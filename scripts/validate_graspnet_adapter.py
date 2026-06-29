#!/usr/bin/env python3
from __future__ import annotations

import argparse

from yolo_grasp.config import load_config
from yolo_grasp.pipeline import GraspPipeline
from yolo_grasp.validation import fail_with_message, format_pose, ok, require


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate optional GraspNet planner integration")
    parser.add_argument(
        "-c",
        "--config",
        action="append",
        default=[],
        help="YAML config. For local self-test use: -c configs/default.yaml -c configs/graspnet.mock.yaml",
    )
    parser.add_argument("--command", default="把矿泉水瓶抓起来")
    parser.add_argument("--target-class", default=None)
    parser.add_argument("--require-real-backend", action="store_true")
    args = parser.parse_args()

    try:
        config_paths = args.config or ["configs/default.yaml", "configs/graspnet.mock.yaml"]
        config = load_config(config_paths)
        require(config.get("grasp", {}).get("mode") == "graspnet", "grasp.mode must be graspnet")
        backend = config.get("grasp", {}).get("graspnet", {}).get("backend")
        require(bool(backend), "grasp.graspnet.backend is required")
        require(not args.require_real_backend or backend != "synthetic", "synthetic backend is not a real GraspNet model")

        pipeline = GraspPipeline(config)
        candidate = pipeline.run_once(
            command_text=args.command,
            target_class=args.target_class,
            execute=False,
            save_debug=True,
        )
        require(candidate.metadata.get("planner") == "graspnet", "Planner did not return a GraspNet candidate")
        ok(f"GraspNet backend: {backend}")
        ok(f"Target class: {candidate.target.class_name}")
        ok(f"Grasp pose: {format_pose(candidate.grasp_pose_base)}")
        ok(f"Pre-grasp pose: {format_pose(candidate.pre_grasp_pose_base)}")
        ok(f"Retreat pose: {format_pose(candidate.retreat_pose_base)}")
        ok("GraspNet adapter validation passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())

