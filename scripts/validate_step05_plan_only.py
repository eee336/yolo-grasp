#!/usr/bin/env python3
from __future__ import annotations

import argparse

from yolo_grasp.config import load_config
from yolo_grasp.pipeline import GraspPipeline
from yolo_grasp.validation import DEFAULT_REAL_CONFIGS, fail_with_message, format_pose, ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 05: run camera + YOLO + localization + grasp planning only")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--command", default="把矿泉水瓶抓起来")
    parser.add_argument("--target-class", default=None)
    parser.add_argument(
        "--spatial-hint",
        default=None,
        choices=["left", "right", "top", "bottom", "nearest", "farthest", "front", "back", "center"],
    )
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()

    try:
        config = load_config(args.config or DEFAULT_REAL_CONFIGS)
        pipeline = GraspPipeline(config)
        candidate = pipeline.run_once(
            command_text=args.command,
            target_class=args.target_class,
            spatial_hint=args.spatial_hint,
            execute=False,
            save_debug=not args.no_debug,
        )
        ok(f"Plan target class: {candidate.target.class_name}")
        ok(f"Target center base: {format_pose(candidate.target.center_base_m)}")
        ok(f"Pre-grasp pose: {format_pose(candidate.pre_grasp_pose_base)}")
        ok(f"Grasp pose: {format_pose(candidate.grasp_pose_base)}")
        ok(f"Retreat pose: {format_pose(candidate.retreat_pose_base)}")
        ok("Step 05 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
