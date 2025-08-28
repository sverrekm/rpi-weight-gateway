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
    # Maximum capacity (span) in grams; 0 or None means unlimited/not set
    max_capacity_g: float = 0.0
    demo_mode: bool = False

    # Display settings (ND5052 via RS-232/RS-485)
    display_enabled: bool = False
    serial_port: Optional[str] = None  # e.g. /dev/ttyUSB0
    baudrate: int = 9600
    databits: int = 7  # 7 or 8
    parity: str = "E"  # E (even), N, O
    stopbits: int = 1   # 1 or 2
    dp: int = 2         # decimals
    unit: str = "kg"
    address: Optional[str] = None  # '00'-'99' or None for unaddressed

class CalibrateRequest(BaseModel):
    known_grams: float

class DisplayConfigPayload(BaseModel):
    display_enabled: bool
    serial_port: Optional[str] = None
    baudrate: int = 9600
    databits: int = 7
    parity: str = "E"
    stopbits: int = 1
    dp: int = 2
    unit: str = "kg"
    address: Optional[str] = None
