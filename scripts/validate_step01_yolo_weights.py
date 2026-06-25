#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from yolo_grasp.config import load_config, resolve_path
from yolo_grasp.validation import ValidationError, fail_with_message, info, ok, require, require_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 01: validate YOLO weights and optional test image detection")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--image", default=None, help="Optional image used to test model inference")
    parser.add_argument("--min-detections", type=int, default=1, help="Minimum accepted detections when --image is used")
    args = parser.parse_args()

    try:
        config = load_config(args.config or ["configs/default.yaml"])
        yolo_cfg = config.get("detector", {}).get("yolo", {})
        weights = require_file(yolo_cfg.get("weights", "models/bottle_yolo_seg.pt"), "YOLO weights")

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ValidationError('ultralytics is not installed. Run: pip install -e ".[vision]"') from exc

        model = YOLO(str(weights))
        names = getattr(model, "names", {})
        if isinstance(names, list):
            names = {idx: name for idx, name in enumerate(names)}
        require(bool(names), "YOLO model loaded, but model.names is empty")

        aliases = {str(k): str(v) for k, v in yolo_cfg.get("class_aliases", {}).items()}
        allowed = {str(v) for v in yolo_cfg.get("allowed_classes", [])}
        model_class_names = {str(v) for v in names.values()}
        mapped_model_names = {aliases.get(name, name) for name in model_class_names}
        if allowed:
            overlap = allowed & mapped_model_names
            require(
                bool(overlap),
                (
                    "No overlap between detector.yolo.allowed_classes and model classes after aliases. "
                    f"allowed={sorted(allowed)}, model={sorted(model_class_names)}, aliases={aliases}"
                ),
            )

        ok(f"Loaded YOLO weights: {weights}")
        info("Model classes: " + json.dumps(names, ensure_ascii=False))

        if args.image:
            image_path = require_file(args.image, "Test image")
            results = model.predict(source=str(image_path), conf=float(yolo_cfg.get("conf", 0.45)), verbose=False)
            detections = []
            if results and results[0].boxes is not None:
                boxes = results[0].boxes
                cls_values = boxes.cls.detach().cpu().numpy().astype(int)
                conf_values = boxes.conf.detach().cpu().numpy()
                for class_id, conf in zip(cls_values, conf_values):
                    raw_name = str(names.get(int(class_id), int(class_id)))
                    mapped_name = aliases.get(raw_name, raw_name)
                    if not allowed or mapped_name in allowed or raw_name in allowed:
                        detections.append({"class": mapped_name, "raw_class": raw_name, "confidence": float(conf)})
            require(
                len(detections) >= args.min_detections,
                f"Only {len(detections)} accepted detections on {image_path}, expected >= {args.min_detections}",
            )
            ok(f"Inference accepted {len(detections)} detections on {image_path}")
            info(json.dumps(detections, ensure_ascii=False, indent=2))

        ok("Step 01 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
