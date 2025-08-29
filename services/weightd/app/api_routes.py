from __future__ import annotations
import asyncio
import datetime as dt
import os
import socket
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from typing import List, Callable, Optional, Dict, Any, Tuple

from .models import Reading, CalibrateRequest, Config, Health, WiFiInfo
from .config import save_config as persist_config
from . import wifi_detect


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

    @router.get("/api/debug/raw")
    async def debug_raw():
        try:
            vals = ctx.reader.read_raw_all_modes()
            # ensure plain JSON serializable
            return {"status": "ok", "data": {k: int(v) for k, v in vals.items()}}
        except Exception as e:
            return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

    @router.get("/api/config", response_model=Config)
    async def get_config():
        return ctx.cfg

    @router.post("/api/config", response_model=Config)
    async def set_config(new_cfg: Config):
        """
        Persist quickly and apply in background to avoid blocking the HTTP request
        (GPIO/HX711/MQTT reconfiguration can be slow on some hardware).
        """
        try:
            # Persist immediately so changes survive even if apply fails later
            persist_config(new_cfg)
        except Exception:
            # Non-fatal: apply step below will also persist
            pass
        try:
            # Apply in background thread so this handler returns immediately
            asyncio.create_task(asyncio.to_thread(ctx.update_config, new_cfg))
        except Exception:
            # As a last resort, do it synchronously
            ctx.update_config(new_cfg)
        return new_cfg

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

    def _run_docker(args: List[str], extra_env: Optional[Dict[str, Any]] = None) -> Tuple[int, str]:
        import subprocess
        try:
            env = None
            if extra_env:
                env = os.environ.copy()
                env.update({k: str(v) for k, v in extra_env.items()})
            # Try docker compose first, fallback to docker-compose
            if args[0] == "compose":
                try:
                    proc = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=60, env=env, cwd="/app/..")
                    if proc.returncode != 0 and "unknown command" in (proc.stderr or "").lower():
                        # Fallback to docker-compose binary
                        proc = subprocess.run(["docker-compose"] + args[1:], capture_output=True, text=True, timeout=60, env=env, cwd="/app/..")
                except FileNotFoundError:
                    # Try docker-compose binary directly
                    proc = subprocess.run(["docker-compose"] + args[1:], capture_output=True, text=True, timeout=60, env=env, cwd="/app/..")
            else:
                proc = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=60, env=env, cwd="/app/..")
            rc = proc.returncode
            out = (proc.stdout or "") + (proc.stderr or "")
            return rc, out
        except Exception as e:
            return 1, str(e)

    @router.post("/api/broker/restart")
    async def broker_restart():
        if not _docker_available():
            return JSONResponse({"error": "docker socket not available in container"}, status_code=501)
        rc, out = _run_docker(["compose", "restart", "mqtt"])
        if rc != 0:
            return JSONResponse({"error": out.strip()}, status_code=500)
        return {"status": "ok"}

    @router.post("/api/broker/start")
    async def broker_start():
        if not _docker_available():
            return JSONResponse({"error": "docker socket not available in container"}, status_code=501)
        rc, out = _run_docker(["compose", "up", "-d", "mqtt"])
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

    @router.post("/api/system/update")
    async def system_update(payload: Optional[Dict[str, Any]] = None):
        """
        Update deployment using Docker:
        - docker compose pull (fetch newer images)
        - optionally docker compose build if payload.rebuild is true (for local source changes)
        - docker compose up -d (apply)
        Returns combined log output.
        """
        if not _docker_available():
            return JSONResponse({"error": "docker socket not available in container"}, status_code=501)
        logs: List[str] = []
        # Pull newer images (no-op if building locally)
        rc, out = _run_docker(["compose", "pull"])
        logs.append(out)
        if rc != 0:
            return JSONResponse({"error": out.strip()}, status_code=500)
        # Detect whether any image was actually updated
        lower_out = out.lower()
        updated = any(
            kw in lower_out for kw in [
                "downloaded newer image",
                "downloaded",
                "pulled new image",
                "new image downloaded",
            ]
        )
        # Optional rebuild (manual docker build to avoid BuildKit and ensure correct base)
        rebuild = bool(payload.get("rebuild")) if isinstance(payload, dict) else False
        if rebuild:
            import platform
            arch = platform.machine()
            base = "python:3.9-bookworm"
            if arch == "armv7l":
                base = "arm32v7/python:3.9-bullseye"
            # Build weightd image manually with BASE_IMAGE override
            rc, out = _run_docker([
                "build", "--build-arg", f"BASE_IMAGE={base}",
                "--file", "./services/weightd/Dockerfile",
                "-t", "rpi-weight-gateway-weightd:latest", "."
            ])
            logs.append(out)
            if rc != 0:
                return JSONResponse({"error": out.strip()}, status_code=500)
            # Apply without building
            rc, out = _run_docker(["compose", "up", "-d", "--no-build"])
            logs.append(out)
            if rc != 0:
                return JSONResponse({"error": out.strip()}, status_code=500)
            return {"status": "ok", "action": "rebuilt", "logs": "\n".join(logs)[-4000:]}
        # Apply (no rebuild): only if there were updates
        if not updated:
            return {"status": "ok", "action": "no_update", "logs": "\n".join(logs)[-4000:]}
        rc, out = _run_docker(["compose", "up", "-d"])  # apply only when new images exist
        logs.append(out)
        if rc != 0:
            return JSONResponse({"error": out.strip()}, status_code=500)
        return {"status": "ok", "action": "updated", "logs": "\n".join(logs)[-4000:]}

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

    # --- Wi-Fi management ---
    @router.get("/api/wifi/status")
    async def wifi_status():
        ssid = wifi_detect.current_ssid()
        ip = wifi_detect.current_ip()
        return {"connected": bool(ssid), "ssid": ssid, "ip": ip}

    @router.get("/api/wifi/scan")
    async def wifi_scan():
        import shutil, subprocess
        nets = []
        try:
            if shutil.which("nmcli"):
                out = subprocess.check_output(["nmcli", "-t", "-f", "ssid,signal,security", "dev", "wifi"], text=True, timeout=8)
                seen = set()
                for line in out.splitlines():
                    if not line:
                        continue
                    parts = line.split(":")
                    ssid = parts[0]
                    if ssid in seen:
                        continue
                    seen.add(ssid)
                    sig = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                    sec = parts[2] if len(parts) > 2 else ""
                    nets.append({"ssid": ssid, "signal": sig, "security": sec})
            else:
                # Fallback minimal scan via "iwlist" if available
                if shutil.which("iwlist") and shutil.which("iwgetid"):
                    # Determine interface via iwgetid -r fails? then default wlan0
                    try:
                        iface = subprocess.check_output(["iwgetid", "-r"] , text=True, timeout=3)
                        iface = (iface or "").strip() or "wlan0"
                    except Exception:
                        iface = "wlan0"
                    out = subprocess.check_output(["iwlist", iface, "scan"], text=True, timeout=12, stderr=subprocess.STDOUT)
                    cur_ssid = None
                    for line in out.splitlines():
                        line = line.strip()
                        if line.startswith("ESSID:"):
                            cur_ssid = line.split(":",1)[1].strip().strip('"')
                            nets.append({"ssid": cur_ssid})
                # else: leave empty
        except Exception:
            pass
        # Filter empty SSIDs and sort by signal desc if present
        nets = [n for n in nets if n.get("ssid")]
        nets.sort(key=lambda x: (x.get("signal") or -1), reverse=True)
        return {"networks": nets}

    @router.post("/api/wifi/connect")
    async def wifi_connect(payload: dict):
        import shutil, subprocess
        ssid = payload.get("ssid")
        psk = payload.get("psk")
        if not isinstance(ssid, str) or not ssid:
            return JSONResponse({"error": "ssid required"}, status_code=400)
        # Try nmcli first
        try:
            if shutil.which("nmcli"):
                args = ["nmcli", "dev", "wifi", "connect", ssid]
                if isinstance(psk, str) and psk:
                    args += ["password", psk]
                proc = subprocess.run(args, capture_output=True, text=True, timeout=20)
                if proc.returncode == 0:
                    return {"status": "ok", "tool": "nmcli", "output": (proc.stdout or proc.stderr or "").strip()}
                # If connection exists, try up existing connection
                # nmcli con up id SSID
                proc2 = subprocess.run(["nmcli", "con", "up", "id", ssid], capture_output=True, text=True, timeout=15)
                if proc2.returncode == 0:
                    return {"status": "ok", "tool": "nmcli", "output": (proc2.stdout or proc2.stderr or "").strip()}
        except Exception as e:
            # continue to fallback
            _ = e
        # Fallback to wpa_cli
        try:
            if shutil.which("wpa_cli"):
                iface = "wlan0"
                # add_network
                aid = subprocess.check_output(["wpa_cli", "-i", iface, "add_network"], text=True, timeout=5).strip()
                if not aid.isdigit():
                    return JSONResponse({"error": f"wpa_cli add_network failed: {aid}"}, status_code=500)
                nid = aid
                subprocess.check_output(["wpa_cli", "-i", iface, "set_network", nid, "ssid", f'"{ssid}"'], text=True, timeout=5)
                if isinstance(psk, str) and psk:
                    subprocess.check_output(["wpa_cli", "-i", iface, "set_network", nid, "psk", f'"{psk}"'], text=True, timeout=5)
                else:
                    subprocess.check_output(["wpa_cli", "-i", iface, "set_network", nid, "key_mgmt", "NONE"], text=True, timeout=5)
                subprocess.check_output(["wpa_cli", "-i", iface, "enable_network", nid], text=True, timeout=5)
                subprocess.check_output(["wpa_cli", "-i", iface, "select_network", nid], text=True, timeout=5)
                subprocess.check_output(["wpa_cli", "-i", iface, "save_config"], text=True, timeout=5)
                return {"status": "ok", "tool": "wpa_cli"}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        return JSONResponse({"error": "no supported wifi tools (nmcli/wpa_cli) available"}, status_code=501)

    ctx._ws_hub = hub
    return router
