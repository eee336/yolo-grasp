from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np

from yolo_grasp.types import Detection, GraspCandidate, ObjectPose


def draw_debug(
    color_bgr: np.ndarray,
    detections: Iterable[Detection],
    objects: Iterable[ObjectPose],
    candidate: Optional[GraspCandidate],
) -> np.ndarray:
    image = color_bgr.copy()

    for detection in detections:
        x1, y1, x2, y2 = [int(round(v)) for v in detection.bbox_xyxy]
        cv2.rectangle(image, (x1, y1), (x2, y2), (50, 220, 50), 2)
        label = f"{detection.class_name} {detection.confidence:.2f}"
        cv2.putText(image, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 220, 50), 2)
        if detection.mask is not None:
            overlay = image.copy()
            overlay[detection.mask.astype(bool)] = (80, 180, 255)
            image = cv2.addWeighted(overlay, 0.28, image, 0.72, 0)

    for obj in objects:
        cx = int(round((obj.detection.bbox_xyxy[0] + obj.detection.bbox_xyxy[2]) / 2.0))
        cy = int(round((obj.detection.bbox_xyxy[1] + obj.detection.bbox_xyxy[3]) / 2.0))
        cv2.drawMarker(image, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 18, 2)
        text = f"base xyz {obj.center_base_m[0]:.3f},{obj.center_base_m[1]:.3f},{obj.center_base_m[2]:.3f}"
        cv2.putText(image, text, (cx + 8, cy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 255), 1)

    if candidate is not None:
        pose = candidate.grasp_pose_base
        text = f"grasp {pose[0]:.3f},{pose[1]:.3f},{pose[2]:.3f} profile={candidate.hand_profile}"
        cv2.putText(image, text, (20, image.shape[0] - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2)

    return image


def save_debug_image(path: str | Path, image_bgr: np.ndarray) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), image_bgr)
    if not ok:
        raise IOError(f"Could not write debug image: {path}")
    return path

