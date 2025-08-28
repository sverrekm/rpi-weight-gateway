# rpi-weight-gateway

A Dockerized Raspberry Pi 3 gateway that reads weight from HX711 (Load Cell Click on Pi2 Click Shield), publishes to MQTT, and serves a web UI for live viewing, tare/zero, calibration, and settings. Includes optional captive-portal Wi‑Fi setup (balena wifi-connect) and optional embedded Mosquitto broker.

- Backend: FastAPI (`services/weightd`) exposes REST + WebSocket and serves the static web UI on port 8080
- Web UI: React + Vite, built and copied into the backend image
- MQTT: Optional via Compose profile `mqtt`
- Wi‑Fi captive portal: Optional via Compose profile `wifi`
- Config and calibration persisted under `./data`

## One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/sverrekm/rpi-weight-gateway/main/install.sh | sudo bash
```

Flags:
- `--with-mqtt` enable internal Mosquitto
- `--with-wifi` enable captive portal (host mode)
- `--rebuild` build images locally (useful on Raspberry Pi)

## Quick start

1) Clone repo on the Pi 3 and enter the folder:
- Ensure Docker is installed; run `install.sh` if not
- Copy `.env.example` to `.env` and adjust values

2) Start stack:
```bash
docker compose up -d            # backend + UI
# Optionals
docker compose --profile mqtt up -d   # starts Mosquitto
docker compose --profile wifi up -d   # starts wifi-connect captive portal
```

3) Open the UI:
- http://<pi-ip>:8080

## Update/Upgrade

- From the UI: use the panel “System Update”
  - Optional: tick “Rebuild locally” on Raspberry Pi
  - Backend runs `docker compose pull` and optionally a manual `docker build` for `weightd`, then `up -d`
- Or re-run installer:
  - `curl -fsSL https://raw.githubusercontent.com/sverrekm/rpi-weight-gateway/main/install.sh | sudo bash`
  - With local rebuild: add `--rebuild`

## Hardware and GPIO

- Uses RPi BCM pins for HX711: `GPIO_DOUT` and `GPIO_SCK` from `.env`
- Container runs `privileged: true` and `network_mode: host` for simplicity on Pi 3
- If you prefer a stricter setup, grant `/dev/gpiomem` device and set Linux capabilities appropriately

## Demo mode (no hardware)

Set `DEMO_MODE=true` in `.env` to generate synthetic weight data. Helpful for UI testing and development without GPIO.

## Environment variables (`.env`)

```
MQTT_HOST=
MQTT_PORT=1883
MQTT_USER=
MQTT_PASS=
WEIGHT_TOPIC=weight/measure
STATUS_TOPIC=weight/status
CMD_TOPIC=weight/cmd
GPIO_DOUT=5
GPIO_SCK=6
SAMPLE_RATE=10
MEDIAN_WINDOW=5
SCALE=1.0
OFFSET=0.0
WIFI_AP_SSID=WeightGateway-XXXX
WIFI_AP_PASS=weight1234
AP_COUNTRY=NO
DEMO_MODE=false
# Display / Serial (optional)
DISPLAY_ENABLED=false
SERIAL_PORT=/dev/ttyUSB0
SERIAL_BAUD=9600
SERIAL_DATABITS=7
SERIAL_PARITY=E
SERIAL_STOPBITS=1
DISPLAY_DP=2
DISPLAY_UNIT=kg
DISPLAY_ADDR=
# Broker config path (inside weightd container)
BROKER_CONF_PATH=/data/mosquitto.conf
```

## MQTT topics

- Publish measure: `weight/measure` JSON `{ "grams": float, "ts": iso8601, "stable": bool }`
- Publish status: `weight/status` JSON `{ "uptime_s": int, "wifi": {...}, "mqtt": "connected|disconnected", "version": "x.y.z" }`
- Subscribe commands: `weight/cmd` JSON `{ "action": "tare|zero|calibrate", "value": optional }`

## API summary

- `GET /api/health`
- `GET /api/reading`
- `POST /api/tare`
- `POST /api/zero`
- `POST /api/calibrate` body `{ known_grams: float }`
- `GET /api/config` / `POST /api/config`
- `WS /ws/weight` streaming readings
- Display:
  - `GET /api/display/ports` → list available serial ports
  - `POST /api/display/test` body `{ text?: string, grams?: number }`
- Broker:
  - `GET /api/broker/config` → read mosquitto.conf
  - `POST /api/broker/config` body `{ content: string }` → save mosquitto.conf
  - `POST /api/broker/restart|start|stop`
- System:
  - `POST /api/system/update` body `{ rebuild?: boolean }`

## Compose profiles

- `mqtt`: Eclipse Mosquitto on host network, config in `services/mqtt/mosquitto.conf`
- `wifi`: balenablocks/wifi-connect, host mode, captive portal SSID from `.env`

## Display (ND5052)

- Enable in UI under Configuration → Display (ND5052)
- Select serial port (use “Scan” to populate a list)
- Set baud/databits/parity/stopbits, decimal places (DP), unit, and optional address
- Test output via the “Display” panel (send text or grams)

## Building images (on Raspberry Pi)

- Prefer the installer with `--rebuild` (performs a manual docker build with the correct base image for your arch):
  - `./install.sh --rebuild`
- If you must build manually:
  - armv7l: `docker build --build-arg BASE_IMAGE=arm32v7/python:3.9-bullseye -f services/weightd/Dockerfile -t rpi-weight-gateway-weightd:latest . && docker compose up -d --no-build`
  - aarch64: `docker build --build-arg BASE_IMAGE=python:3.9-bookworm -f services/weightd/Dockerfile -t rpi-weight-gateway-weightd:latest . && docker compose up -d --no-build`

## Troubleshooting

- UI not loading: check `weightd` logs `docker logs weightd`
- Healthcheck failing: ensure port 8080 is free on host and curl is available (installed in image)
- GPIO errors: verify pins, run on actual Pi, and `privileged: true`
- MQTT not connected: set `MQTT_HOST` or start internal broker via profile `mqtt`
- Wi‑Fi portal: requires host networking and Wi‑Fi adapter; connect to the AP SSID and configure network
- Rebuild hangs or BuildKit errors on Pi: use installer `--rebuild` or the manual build commands above; avoids BuildKit and selects a compatible Python base image for your architecture

## License

MIT. See `LICENSE`.
