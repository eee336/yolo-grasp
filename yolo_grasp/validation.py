from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from yolo_grasp.config import get_by_path, load_config, resolve_path


class ValidationError(RuntimeError):
    """Raised when a validation step cannot pass."""


DEFAULT_REAL_CONFIGS = ["configs/default.yaml", "configs/hardware.local.yaml"]


def load_validation_config(paths: Sequence[str] | None = None) -> dict[str, Any]:
    return load_config(paths or DEFAULT_REAL_CONFIGS)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def require_key(config: Mapping[str, Any], dotted_path: str) -> Any:
    sentinel = object()
    value = get_by_path(config, dotted_path, sentinel)
    if value is sentinel:
        raise ValidationError(f"Missing required config key: {dotted_path}")
    return value


def require_file(path: str | Path, description: str) -> Path:
    resolved = resolve_path(path)
    if not resolved.exists():
        raise ValidationError(f"{description} does not exist: {resolved}")
    return resolved


def info(message: str) -> None:
    print(f"[INFO] {message}")


def ok(message: str) -> None:
    print(f"[ OK ] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def fail_with_message(exc: BaseException) -> int:
    print(f"[FAIL] {exc}")
    return 1


def check_tcp_connect(host: str, port: int, timeout_s: float = 2.0) -> None:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return
    except OSError as exc:
        raise ValidationError(f"Could not connect to {host}:{port} within {timeout_s:.1f}s: {exc}") from exc


def ensure_motion_confirmed(confirm: bool, what: str) -> None:
    if not confirm:
        raise ValidationError(f"{what} may move hardware. Re-run with --confirm-motion after clearing the workspace.")


def is_identity_matrix(matrix: Sequence[Sequence[float]], atol: float = 1e-6) -> bool:
    arr = np.asarray(matrix, dtype=np.float64)
    return arr.shape == (4, 4) and np.allclose(arr, np.eye(4), atol=atol)


def format_pose(pose: Iterable[float]) -> str:
    return "[" + ", ".join(f"{float(v):.5f}" for v in pose) + "]"

