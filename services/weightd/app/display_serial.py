from __future__ import annotations
import threading
from typing import Optional

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover
    serial = None  # pyserial may not be installed at dev time

PARITY_MAP = {
    "N": getattr(serial, "PARITY_NONE", "N") if serial else "N",
    "E": getattr(serial, "PARITY_EVEN", "E") if serial else "E",
    "O": getattr(serial, "PARITY_ODD", "O") if serial else "O",
}

STOPBITS_MAP = {
    1: getattr(serial, "STOPBITS_ONE", 1) if serial else 1,
    2: getattr(serial, "STOPBITS_TWO", 2) if serial else 2,
}

BYTESIZE_MAP = {
    7: getattr(serial, "SEVENBITS", 7) if serial else 7,
    8: getattr(serial, "EIGHTBITS", 8) if serial else 8,
}

STX = b"\x02"
SOH = b"\x01"
CR = b"\x0D"


class DisplaySerial:
    """
    Simple RS-232/RS-485 sender for ND5052-like displays.
    Formats frames:
      - Unaddressed: STX + data + CR
      - Addressed:   STX + SOH + AA + STX + data + CR   (AA are two ASCII digits)
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 9600,
        databits: int = 7,
        parity: str = "E",
        stopbits: int = 1,
        dp: int = 2,
        unit: str = "kg",
        address: Optional[str] = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.databits = databits
        self.parity = parity.upper() if parity else "E"
        self.stopbits = stopbits
        self.dp = max(0, int(dp))
        self.unit = unit or ""
        self.address = address if address else None
        self._ser: Optional[serial.Serial] = None  # type: ignore[attr-defined]
        self._lock = threading.Lock()

    def _ensure_open(self) -> None:
        if serial is None:
            raise RuntimeError("pyserial not installed")
        if not self.port:
            raise RuntimeError("serial port not configured")
        if self._ser and self._ser.is_open:
            return
        try:
            self._ser = serial.Serial(  # type: ignore[attr-defined]
                port=self.port,
                baudrate=self.baudrate,
                bytesize=BYTESIZE_MAP.get(int(self.databits), BYTESIZE_MAP[7]),
                parity=PARITY_MAP.get(self.parity.upper(), PARITY_MAP["E"]),
                stopbits=STOPBITS_MAP.get(int(self.stopbits), STOPBITS_MAP[1]),
                timeout=0.1,  # Reduced timeout to prevent blocking
                write_timeout=0.2,  # Reduced write timeout
            )
        except Exception as e:
            raise RuntimeError(f"Failed to open serial port {self.port}: {e}")

    def close(self) -> None:
        with self._lock:
            try:
                if self._ser and self._ser.is_open:
                    self._ser.close()
            except Exception:
                pass
            finally:
                self._ser = None

    def update_config(
        self,
        port: Optional[str],
        baudrate: int,
        databits: int,
        parity: str,
        stopbits: int,
        dp: int,
        unit: str,
        address: Optional[str],
    ) -> None:
        with self._lock:
            self.port = port
            self.baudrate = baudrate
            self.databits = databits
            self.parity = parity.upper() if parity else "E"
            self.stopbits = stopbits
            self.dp = max(0, int(dp))
            self.unit = unit or ""
            self.address = address if address else None
            # Reopen on next send
            self.close()

    def _format_payload(self, value: float) -> bytes:
        fmt = f"{{:.{self.dp}f}}"
        txt = fmt.format(value)
        if self.unit:
            txt = f"{txt} {self.unit}"
        return txt.encode("ascii", errors="ignore")

    def _frame(self, payload: bytes) -> bytes:
        if self.address and len(self.address) == 2 and self.address.isdigit():
            return STX + SOH + self.address.encode("ascii") + STX + payload + CR
        return STX + payload + CR

    def send(self, value: float) -> None:
        try:
            data = self._format_payload(value)
            frame = self._frame(data)
            with self._lock:
                self._ensure_open()
                assert self._ser is not None
                self._ser.write(frame)
                self._ser.flush()
        except Exception:
            # Silently ignore display errors to prevent system freeze
            pass

    def send_text(self, text: str) -> None:
        try:
            payload = text.encode("ascii", errors="ignore")
            frame = self._frame(payload)
            with self._lock:
                self._ensure_open()
                assert self._ser is not None
                self._ser.write(frame)
                self._ser.flush()
        except Exception:
            # Silently ignore display errors to prevent system freeze
            pass
