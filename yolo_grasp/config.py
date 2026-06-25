from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import yaml


Config = Dict[str, Any]


def load_yaml(path: str | Path) -> Config:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file must contain a YAML mapping: {path}")
    return data


def deep_merge(base: Config, override: Mapping[str, Any]) -> Config:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_config(paths: Iterable[str | Path]) -> Config:
    paths = list(paths)
    if not paths:
        raise ValueError("At least one configuration file is required")

    config: Config = {}
    for path in paths:
        config = deep_merge(config, load_yaml(path))
    return config


def get_by_path(config: Mapping[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = config
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def require(config: Mapping[str, Any], dotted_path: str) -> Any:
    sentinel = object()
    value = get_by_path(config, dotted_path, sentinel)
    if value is sentinel:
        raise KeyError(f"Missing required configuration key: {dotted_path}")
    return value


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_path(path: str | Path, base: str | Path | None = None) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    root = Path(base) if base is not None else project_root()
    return (root / candidate).resolve()

