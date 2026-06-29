from __future__ import annotations

import os

from yolo_grasp.web.app import create_app


def config_paths_from_env() -> list[str]:
    raw = os.environ.get("YOLO_GRASP_WEB_CONFIG", "configs/default.yaml")
    return [item for item in raw.split(os.pathsep) if item]


app = create_app(config_paths_from_env())

