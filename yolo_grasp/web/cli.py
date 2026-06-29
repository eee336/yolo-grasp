from __future__ import annotations

import argparse
import os

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the YOLO grasp web console")
    parser.add_argument("-c", "--config", action="append", default=[], help="YAML config, can be repeated")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_paths = args.config or ["configs/default.yaml"]
    os.environ["YOLO_GRASP_WEB_CONFIG"] = os.pathsep.join(config_paths)
    uvicorn.run(
        "yolo_grasp.web.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

