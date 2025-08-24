from __future__ import annotations
import socket
import subprocess
from typing import Optional


def has_internet(timeout: float = 2.0) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection(("1.1.1.1", 53), timeout=timeout)
        return True
    except Exception:
        return False


def current_ssid() -> Optional[str]:
    # Try nmcli
    try:
        out = subprocess.check_output(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], text=True)
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == "yes":
                return parts[1] or None
    except Exception:
        pass
    # Try iwgetid
    try:
        out = subprocess.check_output(["iwgetid", "-r"], text=True).strip()
        return out or None
    except Exception:
        pass
    return None


def current_ip() -> Optional[str]:
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        return out.split()[0] if out else None
    except Exception:
        return None
