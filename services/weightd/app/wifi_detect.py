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
    # Try nmcli on host via docker exec (if available)
    try:
        out = subprocess.check_output(["docker", "exec", "rpi-weight-gateway-host-1", "nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], text=True, timeout=5)
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == "yes":
                return parts[1] or None
    except Exception:
        pass
    
    # Try nmcli locally (if container has network access)
    try:
        out = subprocess.check_output(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], text=True, timeout=5)
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == "yes":
                return parts[1] or None
    except Exception:
        pass
    
    # Try iwgetid locally
    try:
        out = subprocess.check_output(["iwgetid", "-r"], text=True, timeout=5).strip()
        return out or None
    except Exception:
        pass
    
    # Fallback: check if we have internet and assume connected
    if has_internet():
        return "connected"  # Generic indicator
    
    return None


def current_ip() -> Optional[str]:
    try:
        # Try to get container's IP first
        out = subprocess.check_output(["hostname", "-I"], text=True, timeout=5).strip()
        if out:
            return out.split()[0]
    except Exception:
        pass
    
    # Try to get a real IP by connecting to external service
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    
    return None
