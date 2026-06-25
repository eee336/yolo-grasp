from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

from yolo_grasp.types import PipelineError


@dataclass(frozen=True)
class CommandIntent:
    raw_text: str
    normalized_text: str
    target_class: Optional[str]
    matched_alias: Optional[str]
    spatial_hint: Optional[str]
    confidence: float
    warnings: List[str] = field(default_factory=list)


class CommandParser:
    """Rule-based Chinese command parser for a small, safety-critical object set."""

    def __init__(self, config: Mapping | None = None):
        config = config or {}
        self.enabled = bool(config.get("enabled", True))
        self.require_known_target = bool(config.get("require_known_target", True))
        self.default_target_class = config.get("default_target_class")
        self.aliases: Dict[str, List[str]] = {
            str(class_name): [str(word) for word in words]
            for class_name, words in config.get("aliases", {}).items()
        }
        self.spatial_keywords: Dict[str, List[str]] = {
            str(name): [str(word) for word in words]
            for name, words in config.get("spatial_keywords", {}).items()
        }

    def parse(self, text: str) -> CommandIntent:
        raw_text = str(text or "").strip()
        if not raw_text:
            raise PipelineError("empty language command")

        normalized = normalize_command_text(raw_text)
        class_name, alias, class_score = self._match_target(normalized)
        spatial_hint, spatial_score = self._match_spatial(normalized)
        warnings: List[str] = []

        if class_name is None and self.default_target_class:
            class_name = str(self.default_target_class)
            warnings.append(f"no target alias matched; using default_target_class={class_name}")

        if class_name is None and self.require_known_target:
            known = ", ".join(sorted(self.aliases))
            raise PipelineError(
                f"could not map command to a known target class: {raw_text!r}. Known classes: {known}"
            )

        confidence = min(1.0, class_score + spatial_score * 0.15)
        return CommandIntent(
            raw_text=raw_text,
            normalized_text=normalized,
            target_class=class_name,
            matched_alias=alias,
            spatial_hint=spatial_hint,
            confidence=confidence,
            warnings=warnings,
        )

    def _match_target(self, normalized_text: str) -> tuple[Optional[str], Optional[str], float]:
        best_class = None
        best_alias = None
        best_len = 0
        for class_name, aliases in self.aliases.items():
            candidates = list(aliases) + [class_name]
            for alias in candidates:
                normalized_alias = normalize_command_text(alias)
                if not normalized_alias:
                    continue
                if normalized_alias in normalized_text and len(normalized_alias) > best_len:
                    best_class = class_name
                    best_alias = alias
                    best_len = len(normalized_alias)

        if best_class is None:
            return None, None, 0.0
        return best_class, best_alias, min(0.95, 0.45 + best_len / max(len(normalized_text), 1))

    def _match_spatial(self, normalized_text: str) -> tuple[Optional[str], float]:
        best_hint = None
        best_len = 0
        for hint, words in self.spatial_keywords.items():
            for word in words:
                normalized_word = normalize_command_text(word)
                if normalized_word and normalized_word in normalized_text and len(normalized_word) > best_len:
                    best_hint = hint
                    best_len = len(normalized_word)
        if best_hint is None:
            return None, 0.0
        return best_hint, min(1.0, 0.4 + best_len / max(len(normalized_text), 1))


def normalize_command_text(text: str) -> str:
    text = str(text).strip().lower()
    drop_chars = set(" \t\r\n,，.。!！?？:：;；\"'“”‘’（）()[]{}<>《》")
    return "".join(ch for ch in text if ch not in drop_chars)

