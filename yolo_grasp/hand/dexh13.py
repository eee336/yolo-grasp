from __future__ import annotations

import importlib
import json
import logging
import time
from typing import Any, Mapping

from yolo_grasp.hand.base import HandController
from yolo_grasp.types import HardwareError

LOGGER = logging.getLogger(__name__)


class DexH13Hand(HandController):
    """DexH13 adapter with pluggable transports.

    Supported transports:
      - mock: logs commands only
      - serial_json: writes JSON commands to a serial bridge
      - modbus_tcp: writes configured registers using pymodbus
      - sdk: calls a vendor Python SDK through configured method names
    """

    def __init__(self, config: Mapping):
        super().__init__(config.get("profiles", {}))
        self.config = config
        self.transport = str(config.get("transport", "mock")).lower()
        self.open_profile = str(config.get("open_profile", "open"))
        self.enable_motion = bool(config.get("enable_motion", False))
        self.client = None
        self.sdk = None

    def connect(self) -> None:
        if self.transport == "mock":
            LOGGER.info("DexH13 mock transport connected")
            return
        if self.transport == "serial_json":
            self._connect_serial_json()
            return
        if self.transport == "modbus_tcp":
            self._connect_modbus_tcp()
            return
        if self.transport == "sdk":
            self._connect_sdk()
            return
        raise ValueError(f"Unsupported DexH13 transport: {self.transport}")

    def open(self) -> None:
        if self.open_profile in self.profiles:
            self.apply_profile(self.open_profile)
        else:
            self._send_command({"cmd": "open"})

    def apply_profile(self, name: str) -> None:
        profile = dict(self.get_profile(name))
        LOGGER.info("DexH13 apply_profile name=%s transport=%s", name, self.transport)
        if self.transport != "mock" and not self.enable_motion:
            LOGGER.warning("DexH13 enable_motion=false; profile logged but not sent")
            return

        command = {"cmd": "profile", "name": name, **profile}
        self._send_command(command)
        settle_s = float(profile.get("settle_s", self.config.get("default_settle_s", 0.8)))
        if settle_s > 0:
            time.sleep(settle_s)

    def stop(self) -> None:
        try:
            self._send_command({"cmd": "stop"})
        except Exception:  # noqa: BLE001
            LOGGER.exception("DexH13 stop failed")

    def disconnect(self) -> None:
        if self.transport == "serial_json" and self.client is not None:
            self.client.close()
        elif self.transport == "modbus_tcp" and self.client is not None:
            self.client.close()
        elif self.transport == "sdk" and self.sdk is not None:
            method_name = self.config.get("sdk", {}).get("methods", {}).get("disconnect")
            if method_name:
                getattr(self.sdk, method_name)()
        self.client = None
        self.sdk = None

    def _connect_serial_json(self) -> None:
        try:
            import serial
        except ImportError as exc:
            raise HardwareError("pyserial is required for DexH13 transport=serial_json") from exc
        serial_cfg = self.config.get("serial_json", {})
        self.client = serial.Serial(
            port=str(serial_cfg.get("port", "/dev/ttyUSB0")),
            baudrate=int(serial_cfg.get("baudrate", 115200)),
            timeout=float(serial_cfg.get("timeout_s", 1.0)),
        )

    def _connect_modbus_tcp(self) -> None:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError as exc:
            raise HardwareError("pymodbus is required for DexH13 transport=modbus_tcp") from exc
        modbus_cfg = self.config.get("modbus_tcp", {})
        self.client = ModbusTcpClient(
            host=str(modbus_cfg.get("host", "192.168.1.20")),
            port=int(modbus_cfg.get("port", 502)),
            timeout=float(modbus_cfg.get("timeout_s", 1.0)),
        )
        if not self.client.connect():
            raise HardwareError("Could not connect to DexH13 Modbus TCP server")

    def _connect_sdk(self) -> None:
        sdk_cfg = self.config.get("sdk", {})
        module = importlib.import_module(str(sdk_cfg["module"]))
        cls = getattr(module, str(sdk_cfg["class"]))
        self.sdk = cls(**dict(sdk_cfg.get("init_kwargs", {})))
        method_name = sdk_cfg.get("methods", {}).get("connect")
        if method_name:
            getattr(self.sdk, method_name)()

    def _send_command(self, command: Mapping[str, Any]) -> None:
        if self.transport == "mock":
            LOGGER.info("DexH13 mock command: %s", command)
            return
        if self.transport == "serial_json":
            self._send_serial_json(command)
            return
        if self.transport == "modbus_tcp":
            self._send_modbus(command)
            return
        if self.transport == "sdk":
            self._send_sdk(command)
            return
        raise ValueError(f"Unsupported DexH13 transport: {self.transport}")

    def _send_serial_json(self, command: Mapping[str, Any]) -> None:
        if self.client is None:
            raise HardwareError("DexH13 serial_json is not connected")
        payload = json.dumps(command, ensure_ascii=True).encode("utf-8") + b"\n"
        self.client.write(payload)
        self.client.flush()

    def _send_modbus(self, command: Mapping[str, Any]) -> None:
        if self.client is None:
            raise HardwareError("DexH13 modbus_tcp is not connected")
        modbus_cfg = self.config.get("modbus_tcp", {})
        registers = modbus_cfg.get("registers", {})
        unit_id = int(modbus_cfg.get("unit_id", 1))

        if command.get("cmd") == "stop" and "command" in registers:
            self.client.write_register(int(registers["command"]), int(modbus_cfg.get("stop_value", 0)), slave=unit_id)
            return
        if command.get("cmd") not in {"profile", "open"}:
            return

        position_start = registers.get("position_start")
        positions = command.get("positions")
        if position_start is not None and positions is not None:
            scaled = scale_register_values(positions, float(modbus_cfg.get("position_scale", 1000.0)))
            self.client.write_registers(int(position_start), scaled, slave=unit_id)

        speed_start = registers.get("speed_start")
        speeds = command.get("speeds", command.get("speed"))
        if speed_start is not None and speeds is not None:
            self.client.write_registers(
                int(speed_start),
                scale_register_values(as_list(speeds), float(modbus_cfg.get("speed_scale", 1000.0))),
                slave=unit_id,
            )

        force_start = registers.get("force_start")
        forces = command.get("forces", command.get("force"))
        if force_start is not None and forces is not None:
            self.client.write_registers(
                int(force_start),
                scale_register_values(as_list(forces), float(modbus_cfg.get("force_scale", 1000.0))),
                slave=unit_id,
            )

        if "command" in registers:
            self.client.write_register(
                int(registers["command"]),
                int(modbus_cfg.get("execute_value", 1)),
                slave=unit_id,
            )

    def _send_sdk(self, command: Mapping[str, Any]) -> None:
        if self.sdk is None:
            raise HardwareError("DexH13 SDK is not connected")
        methods = self.config.get("sdk", {}).get("methods", {})
        if command.get("cmd") == "stop":
            method_name = methods.get("stop")
            if method_name:
                getattr(self.sdk, method_name)()
            return

        apply_method = methods.get("apply_profile")
        if apply_method:
            getattr(self.sdk, apply_method)(dict(command))
            return

        if "positions" in command and methods.get("set_positions"):
            getattr(self.sdk, methods["set_positions"])(command["positions"])
        if "speed" in command and methods.get("set_speed"):
            getattr(self.sdk, methods["set_speed"])(command["speed"])
        if "force" in command and methods.get("set_force"):
            getattr(self.sdk, methods["set_force"])(command["force"])


def as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def scale_register_values(values: Any, scale: float) -> list[int]:
    return [int(round(float(value) * scale)) for value in as_list(values)]

