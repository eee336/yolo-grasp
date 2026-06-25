from __future__ import annotations

from typing import Mapping

from yolo_grasp.types import HardwareError


class SpeechRecognizer:
    """Small wrapper around the optional SpeechRecognition package."""

    def __init__(self, config: Mapping | None = None):
        config = config or {}
        self.language = str(config.get("language", "zh-CN"))
        self.timeout_s = float(config.get("timeout_s", 5.0))
        self.phrase_time_limit_s = float(config.get("phrase_time_limit_s", 6.0))
        self.energy_threshold = config.get("energy_threshold")

    def listen_once(self) -> str:
        try:
            import speech_recognition as sr
        except ImportError as exc:
            raise HardwareError("SpeechRecognition is required for --listen") from exc

        recognizer = sr.Recognizer()
        if self.energy_threshold is not None:
            recognizer.energy_threshold = int(self.energy_threshold)

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(
                source,
                timeout=self.timeout_s,
                phrase_time_limit=self.phrase_time_limit_s,
            )
        return recognizer.recognize_google(audio, language=self.language)

