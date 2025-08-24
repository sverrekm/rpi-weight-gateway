from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional

class Reading(BaseModel):
    grams: float
    ts: str
    stable: bool = False

class MQTTStatus(BaseModel):
    state: str = Field(description="connected|disconnected")

class WiFiInfo(BaseModel):
    connected: bool
    ssid: Optional[str] = None
    ip: Optional[str] = None

class Health(BaseModel):
    uptime_s: int
    wifi: WiFiInfo
    mqtt: str
    version: str

class Config(BaseModel):
    mqtt_host: Optional[str] = None
    mqtt_port: int = 1883
    mqtt_user: Optional[str] = None
    mqtt_pass: Optional[str] = None
    weight_topic: str = "weight/measure"
    status_topic: str = "weight/status"
    cmd_topic: str = "weight/cmd"
    gpio_dout: int = 5
    gpio_sck: int = 6
    sample_rate: int = 10
    median_window: int = 5
    scale: float = 1.0
    offset: float = 0.0
    demo_mode: bool = False

class CalibrateRequest(BaseModel):
    known_grams: float
