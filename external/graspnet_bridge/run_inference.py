#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description="Template bridge for external GraspNet/AnyGrasp inference")
    parser.add_argument("--input", required=True, help="Input .npz created by yolo_grasp")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--checkpoint", default=None, help="Model checkpoint path used by your real implementation")
    parser.add_argument(
        "--template-synthetic",
        action="store_true",
        help="Write one synthetic candidate for interface testing only. Do not use for real grasping.",
    )
    args = parser.parse_args()

    data = np.load(args.input, allow_pickle=True)
    if not args.template_synthetic:
        raise SystemExit(
            "This is a bridge template. Replace run_inference.py with your GraspNet/AnyGrasp "
            "model call, or pass --template-synthetic only to test the JSON protocol."
        )

    center = data["center_camera_m"].astype(float).tolist()
    output = {
        "grasps": [
            {
                "score": 0.5,
                "translation_camera_m": center,
                "rotation_camera": np.eye(3).tolist(),
                "width_m": 0.08,
                "depth_m": 0.04,
                "metadata": {"source": "template_synthetic"},
            }
        ]
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

