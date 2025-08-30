from __future__ import annotations
import threading
import time
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
ESC = b"\x1B"


class ND5052Display:
    """
    ND5052 Display Controller with full protocol support.
    
    Supports Norsk Display Standard Protocol:
      - Unaddressed: STX + data + CR
      - Addressed:   STX + SOH + AA + STX + data + CR   (AA are two ASCII digits)
    
    Programming mode: Send <Esc>P 16 times to enter config mode at 9600,8,N,1
    Available commands: S, ?, V, C=baudrate, P=parity, D=databits, A=address, DP=decimals
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
        protocol: str = "standard",
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.databits = databits
        self.parity = parity.upper() if parity else "E"
        self.stopbits = stopbits
        self.dp = max(0, int(dp))
        self.unit = unit or ""
        self.address = address if address else None
        self.protocol = protocol
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
                timeout=0.01,  # Very short timeout to prevent blocking
                write_timeout=0.01,  # Very short write timeout
                inter_byte_timeout=0.01,  # Prevent hanging between bytes
            )
            # Test the connection immediately
            if not self._ser.is_open:
                raise RuntimeError("Serial port failed to open")
        except Exception as e:
            self._ser = None
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
            # Format value based on unit setting
            if self.unit.lower() == 'kg':
                kg_value = value / 1000.0
                formatted = f"{kg_value:.1f}".replace('.', ',')
                display_text = f"{formatted} {self.unit}"
            else:
                formatted = f"{value:.2f}".replace('.', ',')
                display_text = f"{formatted} {self.unit}"
            
            # Send formatted text instead of raw value
            self.send_text(display_text)
        except Exception:
            # Silently ignore all display errors
            pass

    def send_text(self, text: str) -> None:
        try:
            payload = text.encode("ascii", errors="ignore")
            frame = self._frame(payload)
            with self._lock:
                # Close and reopen connection each time to prevent hanging
                self.close()
                self._ensure_open()
                if self._ser is None or not self._ser.is_open:
                    return  # Skip if can't open
                
                # Write with immediate timeout
                try:
                    self._ser.write(frame)
                    # Don't flush - it can cause hanging
                except serial.SerialTimeoutException:
                    pass  # Ignore timeout
                except Exception:
                    pass  # Ignore other write errors
                finally:
                    # Always close after write to prevent hanging
                    self.close()
        except Exception:
            # Silently ignore all display errors to prevent system freeze
            pass

    def enter_programming_mode(self) -> bool:
        """
        Enter ND5052 programming mode by sending <Esc>P 16 times.
        Returns True if successful, False otherwise.
        """
        try:
            with self._lock:
                # Close current connection
                self.close()
                
                # Open at current baudrate first
                self._ensure_open()
                if self._ser is None or not self._ser.is_open:
                    return False
                
                # Send <Esc>P 16 times to enter programming mode
                prog_sequence = ESC + b"P"
                for _ in range(16):
                    try:
                        self._ser.write(prog_sequence)
                        time.sleep(0.01)  # Small delay between sends
                    except Exception:
                        pass
                
                # Close and reopen at 9600,8,N,1 for programming
                self.close()
                
                # Open programming connection
                self._ser = serial.Serial(
                    port=self.port,
                    baudrate=9600,
                    bytesize=8,
                    parity=serial.PARITY_NONE if serial else "N",
                    stopbits=1,
                    timeout=0.5,
                    write_timeout=0.5,
                )
                
                # Wait for "Prog" response
                time.sleep(0.5)
                
                return True
                
        except Exception:
            return False

    def send_programming_command(self, command: str) -> Optional[str]:
        """
        Send a programming command and return response.
        Must be in programming mode first.
        """
        try:
            with self._lock:
                if self._ser is None or not self._ser.is_open:
                    return None
                
                # Send command with CR
                cmd_bytes = command.encode('ascii') + b'\r'
                self._ser.write(cmd_bytes)
                
                # Read response with timeout
                response = b""
                for _ in range(50):  # Simple timeout loop
                    if self._ser.in_waiting > 0:
                        chunk = self._ser.read(self._ser.in_waiting)
                        response += chunk
                        if b'\r' in response or b'\n' in response:
                            break
                    time.sleep(0.01)
                
                return response.decode('ascii', errors='ignore').strip()
                
        except Exception:
            return None

    def get_status(self) -> Optional[dict]:
        """Get display status using 'S' command in programming mode."""
        try:
            if not self.enter_programming_mode():
                return None
            
            response = self.send_programming_command("S")
            self.close()
            
            if response:
                # Parse status response into dict
                status = {}
                for line in response.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        status[key.strip()] = value.strip()
                return status
            return None
        except Exception:
            self.close()
            return None

    def configure_display(self, config: dict) -> bool:
        """
        Configure display parameters using programming mode.
        config dict can contain: baudrate, parity, databits, address, decimals
        
        Available commands:
        - C=baudrate (300-19200)
        - P=parity (N,E,O) 
        - D=databits (7 or 8)
        - A=address (00-99, 00=no addressing)
        - DP=decimals (decimal places)
        """
        try:
            if not self.enter_programming_mode():
                return False
            
            success = True
            
            # Configure baudrate
            if 'baudrate' in config:
                response = self.send_programming_command(f"C={config['baudrate']}")
                if response and "OK" not in response:
                    success = False
            
            # Configure parity
            if 'parity' in config:
                response = self.send_programming_command(f"P={config['parity']}")
                if response and "OK" not in response:
                    success = False
            
            # Configure databits
            if 'databits' in config:
                response = self.send_programming_command(f"D={config['databits']}")
                if response and "OK" not in response:
                    success = False
            
            # Configure address
            if 'address' in config:
                addr = config['address'] if config['address'] else "00"
                response = self.send_programming_command(f"A={addr:02}")
                if response and "OK" not in response:
                    success = False
            
            # Configure decimals
            if 'decimals' in config:
                response = self.send_programming_command(f"DP={config['decimals']}")
                if response and "OK" not in response:
                    success = False
            
            # Exit programming mode by closing connection
            self.close()
            
            return success
            
        except Exception:
            self.close()
            return False

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
