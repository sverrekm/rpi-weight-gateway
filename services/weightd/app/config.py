from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict
from .models import Config

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT = Config(
    mqtt_host=os.getenv("MQTT_HOST") or None,
    mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
    mqtt_user=os.getenv("MQTT_USER") or None,
    mqtt_pass=os.getenv("MQTT_PASS") or None,
    weight_topic=os.getenv("WEIGHT_TOPIC", "weight/measure"),
    status_topic=os.getenv("STATUS_TOPIC", "weight/status"),
    cmd_topic=os.getenv("CMD_TOPIC", "weight/cmd"),
    gpio_dout=int(os.getenv("GPIO_DOUT", "5")),
    gpio_sck=int(os.getenv("GPIO_SCK", "6")),
    sample_rate=int(os.getenv("SAMPLE_RATE", "10")),
    median_window=int(os.getenv("MEDIAN_WINDOW", "5")),
    scale=float(os.getenv("SCALE", "1.0")),
    offset=float(os.getenv("OFFSET", "0.0")),
    demo_mode=os.getenv("DEMO_MODE", "false").lower() == "true",
)


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    ensure_data_dir()
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            return Config(**data)
        except Exception:
            pass
    save_config(DEFAULT)
    return DEFAULT


def save_config(cfg: Config) -> None:
    ensure_data_dir()
    CONFIG_PATH.write_text(json.dumps(cfg.dict(), indent=2))
