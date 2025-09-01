from __future__ import annotations
import asyncio
import datetime as dt
import os
import socket
import time
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Response, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Callable, Union, Tuple, Set, Awaitable
from .models import Reading, CalibrateRequest, Config, Health, WiFiInfo, UserPreferences
from .config import save_config as persist_config
from . import wifi_detect
import subprocess
import logging


class WeightHub:
    def __init__(self, reader_getter: Callable[[], float], stable_getter: Callable[[], bool]):
        self.reader_getter = reader_getter
        self.stable_getter = stable_getter
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        try:
            await websocket.accept()
            self.active.append(websocket)
            logger.info(f"WebSocket connection accepted. Active connections: {len(self.active)}")
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {str(e)}")
            raise

    def disconnect(self, websocket: WebSocket):
        try:
            if websocket in self.active:
                self.active.remove(websocket)
                logger.info(f"WebSocket disconnected. Active connections: {len(self.active)}")
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {str(e)}")

    async def broadcast(self, reading: Reading):
        if not self.active:
            return
            
        dead = []
        data = reading.dict()
        
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"WebSocket send error: {str(e)}")
                dead.append(ws)
                
        for ws in dead:
            try:
                self.disconnect(ws)
            except Exception as e:
                logger.error(f"Error cleaning up dead WebSocket: {str(e)}")


def create_router(ctx) -> APIRouter:
    router = APIRouter()
    PREFS_FILE = Path("/data/user_prefs.json")

    def load_prefs() -> UserPreferences:
        try:
            if PREFS_FILE.exists():
                return UserPreferences(**json.loads(PREFS_FILE.read_text()))
        except Exception:
            pass
        return UserPreferences()

    def save_prefs(prefs: UserPreferences):
        PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(json.dumps(prefs.dict()))

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
        # Convert to dict and flatten wifi info for easier frontend access
        data = info.dict()
        data['uptime'] = data.get('uptime_s', 0)
        data['wifi_ssid'] = data.get('wifi', {}).get('ssid')
        data['mqtt_connected'] = data.get('mqtt') == 'connected'
        return JSONResponse(data)

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
        from fastapi import BackgroundTasks
        
        async def run_calibration():
            try:
                scale = ctx.calibrate(req.known_grams)
                ctx.save_config()
                return {"status": "ok", "scale": scale}
            except TimeoutError as e:
                logger.error(f"Calibration timeout: {e}")
                return {"status": "error", "message": str(e) or "Calibration timed out"}
            except Exception as e:
                logger.error(f"Calibration error: {e}", exc_info=True)
                return {"status": "error", "message": str(e) or "Calibration failed"}
        
        # Run in a thread to avoid blocking the event loop
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor() as pool:
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    pool, 
                    lambda: asyncio.run(run_calibration())
                )
                return result
            except Exception as e:
                logger.error(f"Failed to run calibration: {e}", exc_info=True)
                return {"status": "error", "message": "Failed to start calibration process"}

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
        # Check if docker socket exists and is accessible
        if not os.path.exists("/var/run/docker.sock"):
            return False
        try:
            # Try to access the socket
            import stat
            st = os.stat("/var/run/docker.sock")
            return stat.S_ISSOCK(st.st_mode)
        except:
            return False

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
        # Check if docker socket is available
        docker_available = _docker_available()
        logs: List[str] = []
        
        if not docker_available:
            # Try alternative approach - restart container from inside
            logs.append("Docker socket not available, attempting container restart...")
            try:
                import subprocess
                # Try to restart the service using systemctl if available
                result = subprocess.run(["systemctl", "restart", "docker"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    logs.append("Service restart attempted")
                    return {"status": "ok", "action": "restart_attempted", "logs": "\n".join(logs)}
                else:
                    logs.append(f"Restart failed: {result.stderr}")
            except Exception as e:
                logs.append(f"Restart attempt failed: {str(e)}")
            
            return JSONResponse({
                "error": "Docker socket not available and restart failed", 
                "logs": "\n".join(logs)
            }, status_code=501)
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
        client_ip = websocket.client.host if websocket.client else 'unknown'
        logger.info(f"WebSocket connection attempt from {client_ip}")
        
        # Initialize error tracking
        last_error_time = 0
        error_count = 0
        max_retries = 5
        retry_delay = 1.0
        
        try:
            # Set a reasonable receive timeout
            websocket.client_state.receive_timeout = 30.0
            
            await websocket.accept()
            logger.info(f"WebSocket accepted from {client_ip}")
            
            # Add to hub after successful accept
            await hub.connect(websocket)
            logger.info(f"WebSocket connected: {client_ip}")
            
            # Initial handshake with client
            try:
                await websocket.send_json({
                    "type": "handshake",
                    "status": "connected",
                    "timestamp": dt.datetime.utcnow().isoformat() + "Z"
                })
            except Exception as e:
                logger.error(f"Error during WebSocket handshake with {client_ip}: {str(e)}")
                raise
            
            last_ping = time.time()
            
            while True:
                try:
                    # Check for client pings or other control messages (with timeout)
                    try:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                        if data == "ping":
                            await websocket.send_text("pong")
                            last_ping = time.time()
                        continue
                    except asyncio.TimeoutError:
                        # Check connection health
                        if time.time() - last_ping > 30:  # 30 seconds since last ping
                            await websocket.send_text("ping")
                            last_ping = time.time()
                        pass
                    except Exception as e:
                        logger.warning(f"Error in WebSocket receive for {client_ip}: {str(e)}")
                        error_count += 1
                        if error_count > max_retries:
                            logger.error(f"Too many errors ({error_count}) from {client_ip}, disconnecting")
                            break
                        await asyncio.sleep(retry_delay)
                        continue
                    
                    # Reset error count on successful operation
                    error_count = 0
                    
                    # Add a small delay to prevent high CPU usage
                    await asyncio.sleep(max(0.05, 1.0 / max(1, ctx.cfg.sample_rate)))
                    
                    # Read weight data
                    try:
                        grams = ctx.read_grams()
                        reading = Reading(
                            grams=grams,
                            ts=dt.datetime.utcnow().isoformat() + "Z",
                            stable=ctx.stable
                        )
                        
                        # Send to this client only with error handling
                        try:
                            await websocket.send_json(reading.dict())
                        except RuntimeError as e:
                            if "WebSocket is not connected" in str(e):
                                logger.info(f"WebSocket disconnected during send: {client_ip}")
                                break
                            raise
                            
                    except Exception as e:
                        current_time = time.time()
                        if current_time - last_error_time > 60:  # Log same error at most once per minute
                            logger.error(f"Error reading weight data for {client_ip}: {str(e)}")
                            last_error_time = current_time
                        await asyncio.sleep(1)  # Prevent tight error loop
                        
                except asyncio.CancelledError:
                    logger.info(f"WebSocket connection cancelled: {client_ip}")
                    break
                    
                except WebSocketDisconnect:
                    logger.info(f"WebSocket client disconnected: {client_ip}")
                    break
                    
                except Exception as e:
                    current_time = time.time()
                    if current_time - last_error_time > 60:  # Log same error at most once per minute
                        logger.error(f"Error in WebSocket loop for {client_ip}: {str(e)}", exc_info=True)
                        last_error_time = current_time
                    
                    # Check for connection errors that require reconnection
                    if any(err in str(e).lower() for err in ["connection reset", "broken pipe", "protocol error"]):
                        logger.warning(f"Connection error with {client_ip}, will attempt to reconnect")
                        break
                        
                    await asyncio.sleep(1)  # Prevent tight error loop
                    
        except Exception as e:
            current_time = time.time()
            if current_time - last_error_time > 60:  # Log same error at most once per minute
                logger.error(f"WebSocket error with {client_ip}: {str(e)}", exc_info=True)
                last_error_time = current_time
                
        finally:
            try:
                await websocket.close()
            except:
                pass
            hub.disconnect(websocket)
            logger.info(f"WebSocket connection closed: {client_ip}")
            

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

    @router.post("/api/display/configure")
    async def display_configure(payload: dict):
        """Configure ND5052 display parameters using programming mode."""
        if not ctx.cfg.display_enabled:
            return JSONResponse({"error": "display not enabled"}, status_code=400)
        try:
            success = ctx.display.configure_display(payload)
            if success:
                return {"status": "ok", "message": "Display configured successfully"}
            else:
                return JSONResponse({"error": "Configuration failed"}, status_code=500)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @router.get("/api/display/status")
    async def display_status():
        """Get ND5052 display status and parameters."""
        if not ctx.cfg.display_enabled:
            return JSONResponse({"error": "display not enabled"}, status_code=400)
        try:
            status = ctx.display.get_status()
            if status:
                return {"status": "ok", "parameters": status}
            else:
                return JSONResponse({"error": "Could not read display status"}, status_code=500)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    class DisplayUnitUpdate(BaseModel):
        unit: str = "kg"

    @router.post("/api/display/unit")
    async def update_display_unit(unit_update: DisplayUnitUpdate):
        """Update the display unit (g/kg)."""
        if not ctx.cfg.display_enabled:
            return JSONResponse({"error": "display not enabled"}, status_code=400)
        try:
            unit = unit_update.unit.lower()
            if unit not in ["g", "kg"]:
                return JSONResponse({"error": "unit must be 'g' or 'kg'"}, status_code=400)
            
            # Update the display configuration
            ctx.display.update_config(
                port=ctx.cfg.serial_port,
                baudrate=ctx.cfg.baudrate,
                databits=ctx.cfg.databits,
                parity=ctx.cfg.parity,
                stopbits=ctx.cfg.stopbits,
                dp=ctx.cfg.dp,
                unit=unit,
                address=ctx.cfg.address
            )
            
            # Update the config file
            ctx.cfg.unit = unit
            await persist_config(ctx.cfg)
            
            return {"status": "ok", "unit": unit}
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
                # First trigger a fresh scan
                try:
                    subprocess.run(["nmcli", "dev", "wifi", "rescan"], timeout=10, capture_output=True)
                except Exception:
                    pass  # Continue even if rescan fails
                
                # Get scan results
                out = subprocess.check_output(["nmcli", "-t", "-f", "ssid,signal,security", "dev", "wifi"], text=True, timeout=8)
                seen = set()
                for line in out.splitlines():
                    if not line:
                        continue
                    parts = line.split(":")
                    ssid = parts[0]
                    if not ssid or ssid in seen:
                        continue
                    seen.add(ssid)
                    sig = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                    sec = parts[2] if len(parts) > 2 else ""
                    nets.append({"ssid": ssid, "signal": sig, "security": sec})
            else:
                # Fallback minimal scan via "iwlist" if available
                if shutil.which("iwlist"):
                    # Try to determine interface
                    iface = "wlan0"
                    try:
                        # Get interface from ip link or iwconfig
                        result = subprocess.check_output(["ip", "link", "show"], text=True, timeout=3)
                        for line in result.splitlines():
                            if "wlan" in line and "state UP" in line:
                                iface = line.split(":")[1].strip().split("@")[0]
                                break
                    except Exception:
                        pass
                    
                    try:
                        out = subprocess.check_output(["iwlist", iface, "scan"], text=True, timeout=12, stderr=subprocess.STDOUT)
                        cur_ssid = None
                        for line in out.splitlines():
                            line = line.strip()
                            if line.startswith("ESSID:"):
                                cur_ssid = line.split(":",1)[1].strip().strip('"')
                                if cur_ssid:
                                    nets.append({"ssid": cur_ssid, "signal": None, "security": ""})
                    except Exception:
                        pass
        except Exception as e:
            # Return error info for debugging
            return {"networks": [], "error": str(e), "debug": "scan failed"}
        
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
    @router.get("/api/preferences")
    async def get_preferences():
        """Get user preferences."""
        return load_prefs()

    @router.post("/api/preferences")
    async def update_preferences(prefs: UserPreferences):
        """Update user preferences."""
        save_prefs(prefs)
        return {"status": "ok"}

    @router.get("/api/wifi/ap/status")
    async def get_ap_status():
        """Get the current status of the WiFi access point"""
        try:
            # Check if hostapd is running
            hostapd_result = subprocess.run(
                ["systemctl", "is-active", "hostapd"],
                capture_output=True,
                text=True
            )
            hostapd_active = hostapd_result.returncode == 0
            
            # Check if dnsmasq is running
            dnsmasq_result = subprocess.run(
                ["systemctl", "is-active", "dnsmasq"],
                capture_output=True,
                text=True
            )
            dnsmasq_active = dnsmasq_result.returncode == 0
            
            # Check if wlan0 is up
            wlan0_up = False
            ip_result = subprocess.run(
                ["ip", "addr", "show", "wlan0", "up"],
                capture_output=True,
                text=True
            )
            if ip_result.returncode == 0:
                wlan0_up = "state UP" in ip_result.stdout
            
            # Get SSID from config if available
            ssid = os.getenv("WIFI_AP_SSID", "rpi-weight-gateway")
            ip_address = "192.168.4.1"  # Default AP IP
            
            # Try to get SSID and channel from config file
            channel = 7  # Default channel
            try:
                if os.path.exists("/etc/hostapd/hostapd.conf"):
                    with open("/etc/hostapd/hostapd.conf", "r") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith("ssid=") and not line.startswith("#"):
                                ssid = line.split("=", 1)[1].strip()
                            elif line.startswith("channel=") and not line.startswith("#"):
                                try:
                                    channel = int(line.split("=", 1)[1].strip())
                                except (ValueError, IndexError):
                                    pass
            except Exception as e:
                logger.warning(f"Error reading hostapd config: {str(e)}")
            
            # Get current IP of wlan0 if available
            try:
                ip_result = subprocess.run(
                    ["ip", "addr", "show", "wlan0"],
                    capture_output=True,
                    text=True
                )
                if ip_result.returncode == 0:
                    import re
                    ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_result.stdout)
                    if ip_match:
                        ip_address = ip_match.group(1)
            except Exception as e:
                logger.warning(f"Error getting wlan0 IP: {str(e)}")
            
            # Check if AP is actually broadcasting
            ap_broadcasting = hostapd_active and dnsmasq_active and wlan0_up
            
            # Determine overall status
            if ap_broadcasting:
                status = "active"
            elif hostapd_active or dnsmasq_active:
                status = "partially_active"
            else:
                status = "inactive"
            
            return {
                "enabled": ap_broadcasting,
                "ssid": ssid,
                "ip_address": ip_address,
                "channel": channel,
                "status": status,
                "services": {
                    "hostapd": {
                        "active": hostapd_active,
                        "status": "running" if hostapd_active else "stopped"
                    },
                    "dnsmasq": {
                        "active": dnsmasq_active,
                        "status": "running" if dnsmasq_active else "stopped"
                    },
                    "wlan0": {
                        "up": wlan0_up,
                        "status": "up" if wlan0_up else "down"
                    }
                },
                "last_updated": dt.datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            error_msg = f"Failed to get AP status: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )

    @router.post("/api/wifi/ap/enable")
    async def enable_ap():
        """Enable the WiFi access point"""
        try:
            logger.info("Enabling WiFi access point...")
            
            # Ensure network interfaces are up
            try:
                subprocess.run(
                    ["ip", "link", "set", "wlan0", "up"], 
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to bring up wlan0: {e.stderr}")
                return {
                    "enabled": False,
                    "status": "error",
                    "error": f"Failed to bring up WiFi interface: {e.stderr}"
                }
            
            # Ensure hostapd and dnsmasq are stopped before starting
            for service in ["hostapd", "dnsmasq"]:
                try:
                    subprocess.run(
                        ["systemctl", "stop", service],
                        check=False,
                        capture_output=True,
                        text=True
                    )
                except Exception as e:
                    logger.warning(f"Could not stop {service}: {str(e)}")
            
            # Run the setup script to ensure proper configuration
            try:
                setup_result = subprocess.run(
                    ["/usr/local/bin/setup_ap.sh"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.debug(f"AP setup output: {setup_result.stdout}")
            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to configure AP: {e.stderr}"
                logger.error(error_msg)
                return {
                    "enabled": False,
                    "status": "error",
                    "error": f"Access point configuration failed: {e.stderr}"
                }
            
            # Start required services in order
            services = ["dnsmasq", "hostapd"]
            for service in services:
                try:
                    # Enable and start the service
                    subprocess.run(
                        ["systemctl", "enable", "--now", service],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    logger.info(f"Started and enabled {service} service")
                except subprocess.CalledProcessError as e:
                    error_msg = f"Failed to start {service}: {e.stderr}"
                    logger.error(error_msg)
                    return {
                        "enabled": False,
                        "status": "error",
                        "error": error_msg
                    }
            
            # Verify services are running
            time.sleep(2)  # Give services time to start
            
            for service in services:
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    error_msg = f"Service {service} failed to start: {result.stderr}"
                    logger.error(error_msg)
                    return {
                        "enabled": False,
                        "status": "error",
                        "error": error_msg
                    }
            
            logger.info("WiFi access point enabled successfully")
            
            # Get updated status
            status = await get_ap_status()
            return status
            
        except Exception as e:
            error_msg = f"Failed to enable access point: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )

    @router.post("/api/wifi/ap/disable")
    async def disable_ap():
        """Disable the WiFi access point"""
        try:
            logger.info("Disabling WiFi access point...")
            
            # Stop and disable services in reverse order
            services = ["hostapd", "dnsmasq"]
            for service in services:
                try:
                    # Stop the service
                    subprocess.run(
                        ["systemctl", "stop", service], 
                        check=False,  # Don't fail if already stopped
                        capture_output=True,
                        text=True
                    )
                    # Disable from starting on boot
                    subprocess.run(
                        ["systemctl", "disable", service], 
                        check=False,  # Don't fail if already disabled
                        capture_output=True,
                        text=True
                    )
                    logger.info(f"Stopped and disabled {service} service")
                except Exception as e:
                    logger.warning(f"Error managing {service}: {str(e)}")
            
            # Flush iptables rules to clean up NAT and forwarding
            try:
                cmds = [
                    ["iptables", "-t", "nat", "-D", "POSTROUTING", "-o", "eth0", "-j", "MASQUERADE"],
                    ["iptables", "-D", "FORWARD", "-i", "eth0", "-o", "wlan0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                    ["iptables", "-D", "FORWARD", "-i", "wlan0", "-o", "eth0", "-j", "ACCEPT"]
                ]
                for cmd in cmds:
                    result = subprocess.run(
                        cmd,
                        check=False,  # Don't fail if rules don't exist
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0 and "No chain/target/match" not in result.stderr:
                        logger.warning(f"Failed to remove iptables rule: {result.stderr}")
                
                # Also flush the FORWARD chain
                subprocess.run(
                    ["iptables", "-F", "FORWARD"],
                    check=False,
                    capture_output=True
                )
                
                logger.info("Cleaned up iptables rules")
            except Exception as e:
                logger.warning(f"Error cleaning up iptables: {str(e)}")
            
            # Ensure wlan0 is down
            try:
                subprocess.run(
                    ["ip", "link", "set", "wlan0", "down"],
                    check=False,
                    capture_output=True
                )
            except Exception as e:
                logger.warning(f"Could not bring down wlan0: {str(e)}")
            
            logger.info("WiFi access point disabled successfully")
            
            # Get updated status
            status = await get_ap_status()
            return status
            
        except Exception as e:
            error_msg = f"Failed to disable access point: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )

    return router
