from __future__ import annotations
import asyncio
import datetime as dt
import os
import signal
import time
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config, save_config
from .hx711 import HX711Reader
from .mqtt_client import MQTTClient
from .wifi_detect import has_internet, current_ip, current_ssid
from .models import Health, WiFiInfo, Config
from .display_process import DisplayProcess
from . import api_routes


class AppContext:
    def __init__(self) -> None:
        self.started = time.time()
        self.cfg = load_config()
        self.reader = HX711Reader(
            gpio_dout=self.cfg.gpio_dout,
            gpio_sck=self.cfg.gpio_sck,
            sample_rate=self.cfg.sample_rate,
            median_window=self.cfg.median_window,
            scale=self.cfg.scale,
            offset=self.cfg.offset,
            demo_mode=self.cfg.demo_mode,
        )
        self._last_vals = []  # recent grams to compute stability
        self.stable = False
        self.version = os.getenv("VERSION", "0.0.0")
        self._ws_hub = None  # set by router
        self.mqtt = MQTTClient(
            host=self.cfg.mqtt_host,
            port=self.cfg.mqtt_port,
            username=self.cfg.mqtt_user,
            password=self.cfg.mqtt_pass,
            on_cmd=self._on_cmd,
            cmd_topic=self.cfg.cmd_topic,
        )
        self._publisher_task: Optional[asyncio.Task] = None
        # Display process
        self.display_process = DisplayProcess({
            "serial_port": self.cfg.serial_port,
            "baudrate": self.cfg.baudrate,
            "databits": self.cfg.databits,
            "parity": self.cfg.parity,
            "stopbits": self.cfg.stopbits,
            "dp": self.cfg.dp,
            "unit": self.cfg.unit,
            "address": self.cfg.address,
        })
        if self.cfg.display_enabled:
            self.display_process.start()
        self._last_display_value: Optional[float] = None

    def _on_cmd(self, payload: dict) -> None:
        action = payload.get("action")
        value = payload.get("value")
        if action == "tare":
            self.tare()
        elif action == "zero":
            self.zero()
        elif action == "calibrate" and isinstance(value, (int, float)):
            self.calibrate(float(value))
            self.save_config()

    def read_grams(self) -> float:
        g = self.reader.read_grams()
        # stability: stddev over last N values small
        self._last_vals.append(g)
        if len(self._last_vals) > max(5, int(self.cfg.sample_rate)):
            self._last_vals = self._last_vals[-max(5, int(self.cfg.sample_rate)) :]
        if len(self._last_vals) >= 5:
            mean = sum(self._last_vals) / len(self._last_vals)
            var = sum((x - mean) ** 2 for x in self._last_vals) / len(self._last_vals)
            self.stable = var ** 0.5 < max(0.5, 5.0 / max(1, self.cfg.scale))
        else:
            self.stable = False
        return g

    def tare(self) -> None:
        self.reader.tare()
        self.cfg.offset = self.reader.offset
        self.save_config()

    def zero(self) -> None:
        self.reader.zero()
        self.cfg.offset = self.reader.offset
        self.save_config()

    def calibrate(self, known_grams: float) -> float:
        scale = self.reader.calibrate(known_grams)
        self.cfg.scale = scale
        return scale

    def update_config(self, new_cfg: Config):
        """Update configuration and restart components if needed."""
        # Save old values for comparison
        old_cfg = self.cfg
        self.cfg = new_cfg
        
        # Check if display settings changed
        display_settings_changed = (
            old_cfg.serial_port != new_cfg.serial_port
            or old_cfg.baudrate != new_cfg.baudrate
            or old_cfg.databits != new_cfg.databits
            or old_cfg.parity != new_cfg.parity
            or old_cfg.stopbits != new_cfg.stopbits
            or old_cfg.dp != new_cfg.dp
            or old_cfg.unit != new_cfg.unit
            or old_cfg.address != new_cfg.address
        )
        
        # Update HX711 if needed
        if (
            old_cfg.gpio_dout != new_cfg.gpio_dout
            or old_cfg.gpio_sck != new_cfg.gpio_sck
            or old_cfg.sample_rate != new_cfg.sample_rate
            or old_cfg.median_window != new_cfg.median_window
            or old_cfg.scale != new_cfg.scale
            or old_cfg.offset != new_cfg.offset
            or old_cfg.demo_mode != new_cfg.demo_mode
        ):
            self.reader.close()
            self.reader = HX711Reader(
                gpio_dout=new_cfg.gpio_dout,
                gpio_sck=new_cfg.gpio_sck,
                sample_rate=new_cfg.sample_rate,
                median_window=new_cfg.median_window,
                scale=new_cfg.scale,
                offset=new_cfg.offset,
                demo_mode=new_cfg.demo_mode,
            )
        else:
            self.reader.scale = new_cfg.scale
            self.reader.offset = new_cfg.offset
            self.reader.sample_rate = new_cfg.sample_rate
            self.reader.median_window = new_cfg.median_window
            
        # Update MQTT client
        self.mqtt.stop()
        self.mqtt = MQTTClient(
            host=new_cfg.mqtt_host,
            port=new_cfg.mqtt_port,
            username=new_cfg.mqtt_user,
            password=new_cfg.mqtt_pass,
            on_cmd=self._on_cmd,
            cmd_topic=new_cfg.cmd_topic,
        )
        self.mqtt.start()
        
        # Save the configuration
        save_config(self.cfg)
        
        # Handle display process updates
        if display_settings_changed or not old_cfg.display_enabled and new_cfg.display_enabled:
            # Stop the display process if it's running
            if old_cfg.display_enabled:
                self.display_process.stop()
                
            # Update display configuration
            self.display_process.update_config({
                "serial_port": new_cfg.serial_port,
                "baudrate": new_cfg.baudrate,
                "databits": new_cfg.databits,
                "parity": new_cfg.parity,
                "stopbits": new_cfg.stopbits,
                "dp": new_cfg.dp,
                "unit": new_cfg.unit,
                "address": new_cfg.address,
            })
            
            # Start the display process if enabled
            if new_cfg.display_enabled:
                self.display_process.start()
        elif new_cfg.display_enabled and display_settings_changed:
            # Just update the configuration without restarting the process
            self.display_process.update_config({
                "serial_port": new_cfg.serial_port,
                "baudrate": new_cfg.baudrate,
                "databits": new_cfg.databits,
                "parity": new_cfg.parity,
                "stopbits": new_cfg.stopbits,
                "dp": new_cfg.dp,
                "unit": new_cfg.unit,
                "address": new_cfg.address,
            })

    def save_config(self) -> None:
        save_config(self.cfg)

    def health_info(self) -> Health:
        wifi = WiFiInfo(connected=has_internet(), ssid=current_ssid(), ip=current_ip())
        state = "connected" if self.mqtt.connected else "disconnected"
        return Health(uptime_s=int(time.time() - self.started), wifi=wifi, mqtt=state, version=self.version)

    async def start(self):
        # Start MQTT if configured
        self.mqtt.start()
        # Background publisher
        self._publisher_task = asyncio.create_task(self._publisher())

    async def stop(self):
        if self._publisher_task:
            self._publisher_task.cancel()
            try:
                await self._publisher_task
            except Exception:
                pass
        self.reader.close()
        self.mqtt.stop()
        self.display_process.stop()

    async def _publisher(self):
        status_interval = 10.0
        last_status = 0.0
        while True:
            await asyncio.sleep(1.0 / max(1, self.cfg.sample_rate))
            grams = self.read_grams()
            # Publish measurement
            if self.cfg.mqtt_host:
                self.mqtt.publish(
                    self.cfg.weight_topic,
                    {"grams": grams, "ts": dt.datetime.utcnow().isoformat() + "Z", "stable": self.stable},
                    qos=0,
                )
            # Update display if enabled and reading is stable
            if self.cfg.display_enabled and self.stable and abs(grams - (self._last_display_value or 0)) >= 1.0:
                self.display_process.update_display(grams)
                self._last_display_value = grams
            # Status less frequently
            now = time.time()
            if now - last_status > status_interval:
                last_status = now
                if self.cfg.mqtt_host:
                    h = self.health_info()
                    self.mqtt.publish(self.cfg.status_topic, h.dict(), qos=0)


ctx = AppContext()
app = FastAPI(title="rpi-weight-gateway")

# CORS for local usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes FIRST - must be before static file mounting
app.include_router(api_routes.create_router(ctx))

# Static files - mount AFTER API routes to avoid conflicts
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
print(f"[DEBUG] STATIC_DIR: {STATIC_DIR}, exists: {os.path.isdir(STATIC_DIR)}")

# Force serve our React app at root
@app.get("/")
async def serve_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "React app not found", "static_dir": STATIC_DIR}

if os.path.isdir(STATIC_DIR):
    # Mount static files for assets (js, css, etc.)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    print(f"[DEBUG] Mounted static files at /static")
else:
    print(f"[DEBUG] Static directory not found: {STATIC_DIR}")


@app.on_event("startup")
async def _on_start():
    await ctx.start()


@app.on_event("shutdown")
async def _on_stop():
    await ctx.stop()


# Fallback for SPA when StaticFiles not mounted during uvicorn reload
@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    path = request.url.path
    # Let API and WS pass through
    if path.startswith("/api") or path.startswith("/ws"):
        return await call_next(request)
    # If the path looks like a static asset (has a dot), let StaticFiles handle it
    if "." in os.path.basename(path):
        return await call_next(request)
    # Otherwise, return index.html for SPA client-side routes
    if os.path.isdir(STATIC_DIR):
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    return await call_next(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
