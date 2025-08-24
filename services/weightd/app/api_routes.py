from __future__ import annotations
import asyncio
import datetime as dt
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
                await ws.send_json(reading.model_dump())
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


def create_router(ctx) -> APIRouter:
    router = APIRouter()

    hub = WeightHub(lambda: ctx.read_grams(), lambda: ctx.stable)

    @router.get("/api/health", response_model=Health)
    async def health():
        info = ctx.health_info()
        return JSONResponse(info.model_dump())

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

    ctx._ws_hub = hub
    return router
