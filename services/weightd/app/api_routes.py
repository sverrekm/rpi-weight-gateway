from __future__ import annotations
import asyncio
import datetime as dt
import os
import socket
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import List, Callable

from .models import Reading, CalibrateRequest, Config, Health, WiFiInfo


class WeightHub:
    def __init__(self, reader_getter: Callable[[], float], stable_getter: Callable[[], bool]):
        self.reader_getter = reader_getter
        self.stable_getter = stable_getter
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, reading: Reading):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(reading.dict())
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


def create_router(ctx) -> APIRouter:
    router = APIRouter()

    hub = WeightHub(lambda: ctx.read_grams(), lambda: ctx.stable)
    BROKER_CONF_PATH = Path(os.getenv("BROKER_CONF_PATH", "/data/mosquitto.conf"))
    DEFAULT_BROKER_CONF = """
listener 1883 0.0.0.0
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
""".strip() + "\n"

    @router.get("/api/health", response_model=Health)
    async def health():
        info = ctx.health_info()
        return JSONResponse(info.dict())

    @router.get("/api/reading", response_model=Reading)
    async def get_reading():
        grams = ctx.read_grams()
        return Reading(grams=grams, ts=dt.datetime.utcnow().isoformat() + "Z", stable=ctx.stable)

    @router.post("/api/tare")
    async def tare():
        ctx.tare()
        return {"status": "ok"}

    @router.post("/api/zero")
    async def zero():
        ctx.zero()
        return {"status": "ok"}

    @router.post("/api/calibrate")
    async def calibrate(req: CalibrateRequest):
        scale = ctx.calibrate(req.known_grams)
        ctx.save_config()
        return {"status": "ok", "scale": scale}

    @router.get("/api/config", response_model=Config)
    async def get_config():
        return ctx.cfg

    @router.post("/api/config", response_model=Config)
    async def set_config(new_cfg: Config):
        ctx.update_config(new_cfg)
        return ctx.cfg

    @router.get("/api/broker/status")
    async def broker_status():
        host = ctx.cfg.mqtt_host or "127.0.0.1"
        port = int(ctx.cfg.mqtt_port)
        running = False
        try:
            with socket.create_connection((host, port), timeout=1.0):
                running = True
        except Exception:
            running = False
        exists = BROKER_CONF_PATH.exists()
        control_capable = os.path.exists("/var/run/docker.sock")
        return {"running": running, "host": host, "port": port, "config_exists": exists, "control_capable": control_capable}

    @router.get("/api/broker/config")
    async def get_broker_config():
        if not BROKER_CONF_PATH.exists():
            # create default template on first access
            try:
                BROKER_CONF_PATH.write_text(DEFAULT_BROKER_CONF)
            except Exception:
                pass
        content = ""
        try:
            content = BROKER_CONF_PATH.read_text()
        except Exception:
            content = DEFAULT_BROKER_CONF
        return {"content": content}

    @router.post("/api/broker/config")
    async def set_broker_config(payload: dict):
        content = payload.get("content", "")
        if not isinstance(content, str):
            return JSONResponse({"error": "invalid content"}, status_code=400)
        try:
            BROKER_CONF_PATH.write_text(content)
            return {"status": "ok"}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    def _docker_available() -> bool:
        return os.path.exists("/var/run/docker.sock")

    def _run_docker(args: list[str]) -> tuple[int, str]:
        import subprocess
        try:
            proc = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=15)
            rc = proc.returncode
            out = (proc.stdout or "") + (proc.stderr or "")
            return rc, out
        except Exception as e:
            return 1, str(e)

    @router.post("/api/broker/restart")
    async def broker_restart():
        if not _docker_available():
            return JSONResponse({"error": "docker socket not available in container"}, status_code=501)
        rc, out = _run_docker(["compose", "restart", "mqtt"])  # relies on project root and compose in same network namespace
        if rc != 0:
            return JSONResponse({"error": out.strip()}, status_code=500)
        return {"status": "ok"}

    @router.post("/api/broker/start")
    async def broker_start():
        if not _docker_available():
            return JSONResponse({"error": "docker socket not available in container"}, status_code=501)
        rc, out = _run_docker(["compose", "up", "-d", "mqtt"])  # profile-less start
        if rc != 0:
            return JSONResponse({"error": out.strip()}, status_code=500)
        return {"status": "ok"}

    @router.post("/api/broker/stop")
    async def broker_stop():
        if not _docker_available():
            return JSONResponse({"error": "docker socket not available in container"}, status_code=501)
        rc, out = _run_docker(["compose", "stop", "mqtt"]) 
        if rc != 0:
            return JSONResponse({"error": out.strip()}, status_code=500)
        return {"status": "ok"}

    @router.websocket("/ws/weight")
    async def ws_weight(websocket: WebSocket):
        await hub.connect(websocket)
        try:
            while True:
                await asyncio.sleep(max(0.05, 1.0 / max(1, ctx.cfg.sample_rate)))
                grams = ctx.read_grams()
                reading = Reading(grams=grams, ts=dt.datetime.utcnow().isoformat() + "Z", stable=ctx.stable)
                await hub.broadcast(reading)
        except WebSocketDisconnect:
            hub.disconnect(websocket)

    @router.post("/api/display/test")
    async def display_test(payload: dict):
        if not ctx.cfg.display_enabled:
            return JSONResponse({"error": "display not enabled"}, status_code=400)
        try:
            if "text" in payload and isinstance(payload.get("text"), str):
                txt = str(payload.get("text"))[:32]
                ctx.display.send_text(txt)
                return {"status": "ok"}
            if "grams" in payload and isinstance(payload.get("grams"), (int, float)):
                ctx.display.send(float(payload.get("grams")))
                return {"status": "ok"}
            return JSONResponse({"error": "provide text or grams"}, status_code=400)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @router.get("/api/display/ports")
    async def display_ports():
        try:
            try:
                from serial.tools import list_ports  # type: ignore
            except Exception:
                return {"ports": []}
            items = []
            for p in list_ports.comports():
                items.append({"device": getattr(p, "device", None), "name": getattr(p, "description", "")})
            return {"ports": items}
        except Exception:
            return {"ports": []}

    ctx._ws_hub = hub
    return router
