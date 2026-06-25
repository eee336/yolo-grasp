#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import socket
from pathlib import Path

from yolo_grasp.validation import (
    DEFAULT_REAL_CONFIGS,
    ValidationError,
    check_tcp_connect,
    fail_with_message,
    info,
    ok,
    require,
    require_key,
    warn,
)
from yolo_grasp.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 03: validate RealSense, UR5e, and DexH13 config values")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--check-network", action="store_true", help="Try TCP connections to UR5e and Modbus hand")
    parser.add_argument("--check-sdk-import", action="store_true", help="Try importing configured DexH13 SDK module")
    parser.add_argument("--allow-mock-hand", action="store_true", help="Allow hand.dexh13.transport=mock")
    parser.add_argument("--timeout-s", type=float, default=2.0)
    args = parser.parse_args()

    try:
        config = load_config(args.config or DEFAULT_REAL_CONFIGS)

        require(require_key(config, "camera.type") == "realsense", "camera.type must be realsense")
        realsense_cfg = require_key(config, "camera.realsense")
        for key in ["width", "height", "fps"]:
            require(int(realsense_cfg[key]) > 0, f"camera.realsense.{key} must be positive")
        ok(
            "RealSense config looks valid: "
            f"{realsense_cfg['width']}x{realsense_cfg['height']}@{realsense_cfg['fps']}fps"
        )

        require(require_key(config, "detector.type") == "yolo", "detector.type must be yolo")
        require_key(config, "detector.yolo.weights")
        ok("Detector is configured for YOLO")

        require(require_key(config, "robot.type") in {"ur_rtde", "ur5e_rtde", "ur5e"}, "robot.type must be ur_rtde")
        host = str(require_key(config, "robot.ur5e.host"))
        require(bool(host), "robot.ur5e.host is required")
        if host == "192.168.1.10":
            warn("robot.ur5e.host is still the example IP; this is OK only if it is your real UR5e IP")
        socket.getaddrinfo(host, None)
        ok(f"UR5e host is configured: {host}")
        if args.check_network:
            check_tcp_connect(host, 30004, args.timeout_s)
            ok(f"UR5e RTDE TCP port reachable: {host}:30004")

        require(require_key(config, "hand.type") in {"dexh13", "dex_h13"}, "hand.type must be dexh13")
        dex_cfg = require_key(config, "hand.dexh13")
        transport = str(dex_cfg.get("transport", "mock")).lower()
        require(
            transport != "mock" or args.allow_mock_hand,
            "hand.dexh13.transport is mock. Set sdk, serial_json, or modbus_tcp, or pass --allow-mock-hand.",
        )
        require(transport in {"mock", "sdk", "serial_json", "modbus_tcp"}, f"Unsupported DexH13 transport: {transport}")

        if transport == "sdk":
            sdk_cfg = dex_cfg.get("sdk", {})
            require(sdk_cfg.get("module"), "hand.dexh13.sdk.module is required")
            require(sdk_cfg.get("class"), "hand.dexh13.sdk.class is required")
            if args.check_sdk_import:
                importlib.import_module(str(sdk_cfg["module"]))
                ok(f"DexH13 SDK module import works: {sdk_cfg['module']}")
        elif transport == "serial_json":
            serial_cfg = dex_cfg.get("serial_json", {})
            port = Path(str(serial_cfg.get("port", "")))
            require(str(port), "hand.dexh13.serial_json.port is required")
            if not port.exists():
                warn(f"Serial port does not exist on this machine right now: {port}")
            ok(f"DexH13 serial_json transport configured: {port}")
        elif transport == "modbus_tcp":
            modbus_cfg = dex_cfg.get("modbus_tcp", {})
            host = str(modbus_cfg.get("host", ""))
            port = int(modbus_cfg.get("port", 502))
            require(host, "hand.dexh13.modbus_tcp.host is required")
            ok(f"DexH13 Modbus TCP configured: {host}:{port}")
            if args.check_network:
                check_tcp_connect(host, port, args.timeout_s)
                ok(f"DexH13 Modbus TCP port reachable: {host}:{port}")
        else:
            info("DexH13 mock transport allowed for this validation run")

        ok("Step 03 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
