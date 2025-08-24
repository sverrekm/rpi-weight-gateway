# rpi-weight-gateway

A Dockerized Raspberry Pi 3 gateway that reads weight from HX711 (Load Cell Click on Pi2 Click Shield), publishes to MQTT, and serves a web UI for live viewing, tare/zero, calibration, and settings. Includes optional captive-portal Wi‑Fi setup (balena wifi-connect) and optional embedded Mosquitto broker.

- Backend: FastAPI (`services/weightd`) exposes REST + WebSocket and serves the static web UI on port 8080
- Web UI: React + Vite, built and copied into the backend image
- MQTT: Optional via Compose profile `mqtt`
- Wi‑Fi captive portal: Optional via Compose profile `wifi`
- Config and calibration persisted under `./data`

## One-line install

Replace <REPO_URL_RAW> with your raw Git URL to `install.sh` if needed.

```bash
curl -fsSL https://<REPO_URL_RAW>/install.sh | sudo bash
```

Flags:
- `--with-mqtt` to enable internal Mosquitto
- `--with-wifi` to enable captive portal (host mode, requires Wi‑Fi)

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

## Compose profiles

- `mqtt`: Eclipse Mosquitto on host network, config in `services/mqtt/mosquitto.conf`
- `wifi`: balenablocks/wifi-connect, host mode, captive portal SSID from `.env`

## Building images (on Pi)

```bash
./install.sh --with-mqtt --with-wifi
# or manually
DOCKER_DEFAULT_PLATFORM=linux/arm/v7 docker compose build
DOCKER_DEFAULT_PLATFORM=linux/arm/v7 docker compose up -d --profile mqtt --profile wifi
```

## Troubleshooting

- UI not loading: check `weightd` logs `docker logs weightd`
- Healthcheck failing: ensure port 8080 is free on host and curl is available (installed in image)
- GPIO errors: verify pins, run on actual Pi, and `privileged: true`
- MQTT not connected: set `MQTT_HOST` or start internal broker via profile `mqtt`
- Wi‑Fi portal: requires host networking and Wi‑Fi adapter; connect to the AP SSID and configure network

## License

MIT. See `LICENSE`.
