from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from yolo_grasp.config import load_config
from yolo_grasp.logging_utils import configure_logging
from yolo_grasp.web.service import WebGraspService


class GraspRequest(BaseModel):
    target_class: Optional[str] = None
    spatial_hint: Optional[str] = None
    command_text: Optional[str] = None
    execute: bool = False
    confirm_motion: bool = False


def create_app(config_paths: list[str] | None = None) -> FastAPI:
    config_paths = config_paths or ["configs/default.yaml"]
    config = load_config(config_paths)
    runtime = config.get("runtime", {})
    configure_logging(runtime.get("log_level", "INFO"))
    service = WebGraspService(config)
    static_dir = Path(__file__).resolve().parent / "static"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            service.start()
        except Exception:
            # Keep the UI available so users can see the error and fix config/hardware.
            pass
        app.state.service = service
        yield
        service.stop()

    app = FastAPI(title="YOLO Grasp Console", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/status")
    async def status() -> JSONResponse:
        return JSONResponse(service.scene_status())

    @app.post("/api/grasp")
    async def grasp(request: GraspRequest) -> JSONResponse:
        if request.execute and not request.confirm_motion:
            raise HTTPException(status_code=400, detail="confirm_motion is required for execution")
        try:
            result = service.plan_or_execute(
                target_class=request.target_class,
                spatial_hint=request.spatial_hint,
                command_text=request.command_text,
                execute=request.execute,
            )
            return JSONResponse(result)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/video.mjpg")
    async def video() -> StreamingResponse:
        async def frames() -> AsyncIterator[bytes]:
            while True:
                jpeg = await asyncio.to_thread(service.annotated_jpeg)
                yield b"--frame\r\nContent-Type: image/jpeg\r\nCache-Control: no-cache\r\n\r\n" + jpeg + b"\r\n"
                await asyncio.sleep(float(runtime.get("web_frame_interval_s", 0.12)))

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    return app
