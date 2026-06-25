from __future__ import annotations

import argparse
import logging
from pathlib import Path

from yolo_grasp.config import load_config
from yolo_grasp.language.speech import SpeechRecognizer
from yolo_grasp.logging_utils import configure_logging
from yolo_grasp.pipeline import GraspPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YOLO + RealSense + UR5e + DexH13 grasping pipeline")
    parser.add_argument(
        "-c",
        "--config",
        action="append",
        default=[],
        help="YAML config file. Can be passed multiple times; later files override earlier files.",
    )
    parser.add_argument("--target-class", default=None, help="Optional target class name to grasp")
    parser.add_argument("--command", default=None, help='Natural language command, e.g. "把矿泉水瓶抓起来"')
    parser.add_argument(
        "--spatial-hint",
        default=None,
        choices=["left", "right", "top", "bottom", "nearest", "farthest", "front", "back", "center"],
        help="Optional spatial selector when multiple objects of the same class are visible.",
    )
    parser.add_argument("--listen", action="store_true", help="Listen once from microphone and use ASR text as command")
    parser.add_argument("--execute", action="store_true", help="Execute motion. Overrides runtime.execute_motion=true.")
    parser.add_argument("--plan-only", action="store_true", help="Force planning only. Overrides runtime.execute_motion=false.")
    parser.add_argument("--no-debug", action="store_true", help="Do not save debug image and plan JSON")
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_paths = args.config or ["configs/default.yaml"]
    config = load_config(config_paths)

    runtime = config.get("runtime", {})
    configure_logging(args.log_level or runtime.get("log_level", "INFO"))
    logging.getLogger(__name__).info("Loaded config files: %s", [str(Path(p)) for p in config_paths])

    execute = None
    if args.execute:
        execute = True
    if args.plan_only:
        execute = False

    command_text = args.command
    if args.listen:
        recognizer = SpeechRecognizer(config.get("language", {}).get("speech", {}))
        command_text = recognizer.listen_once()
        logging.getLogger(__name__).info("ASR command: %s", command_text)

    pipeline = GraspPipeline(config)
    candidate = pipeline.run_once(
        target_class=args.target_class,
        spatial_hint=args.spatial_hint,
        command_text=command_text,
        execute=execute,
        save_debug=not args.no_debug,
    )
    logging.getLogger(__name__).info("Done: %s", candidate.description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
