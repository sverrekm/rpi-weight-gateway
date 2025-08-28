from __future__ import annotations
import json
import os
import logging
from pathlib import Path
from typing import Any, Dict
from .models import Config

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CONFIG_PATH = DATA_DIR / "config.json"


def getenv_int(name: str, default: int) -> int:
    """Safely get an integer environment variable with fallback to default."""
    value = os.getenv(name)
    if not value or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        logger.warning(f"Invalid integer value for {name}='{value}', using default {default}")
        return default


def getenv_float(name: str, default: float) -> float:
    """Safely get a float environment variable with fallback to default."""
    value = os.getenv(name)
    if not value or value.strip() == "":
        return default
    try:
        return float(value.strip())
    except ValueError:
        logger.warning(f"Invalid float value for {name}='{value}', using default {default}")
        return default

DEFAULT = Config(
    mqtt_host=os.getenv("MQTT_HOST") or None,
    mqtt_port=getenv_int("MQTT_PORT", 1883),
    mqtt_user=os.getenv("MQTT_USER") or None,
    mqtt_pass=os.getenv("MQTT_PASS") or None,
    weight_topic=os.getenv("WEIGHT_TOPIC", "weight/measure"),
    status_topic=os.getenv("STATUS_TOPIC", "weight/status"),
    cmd_topic=os.getenv("CMD_TOPIC", "weight/cmd"),
    gpio_dout=getenv_int("GPIO_DOUT", 6),
    # HX711 CLK is on mikroBUS PWM; Pi2 Click Socket 1 maps PWM -> GPIO18
    gpio_sck=getenv_int("GPIO_SCK", 18),
    sample_rate=getenv_int("SAMPLE_RATE", 10),
    median_window=getenv_int("MEDIAN_WINDOW", 5),
    scale=getenv_float("SCALE", 1.0),
    offset=getenv_float("OFFSET", 0.0),
    max_capacity_g=getenv_float("MAX_CAPACITY_G", 0.0),
    demo_mode=os.getenv("DEMO_MODE", "false").lower() == "true",
    # Display defaults
    display_enabled=os.getenv("DISPLAY_ENABLED", "false").lower() == "true",
    serial_port=os.getenv("SERIAL_PORT") or None,
    baudrate=getenv_int("SERIAL_BAUD", 9600),
    databits=getenv_int("SERIAL_DATABITS", 7),
    parity=os.getenv("SERIAL_PARITY", "E"),
    stopbits=getenv_int("SERIAL_STOPBITS", 1),
    dp=getenv_int("DISPLAY_DP", 2),
    unit=os.getenv("DISPLAY_UNIT", "kg"),
    address=os.getenv("DISPLAY_ADDR") or None,
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
