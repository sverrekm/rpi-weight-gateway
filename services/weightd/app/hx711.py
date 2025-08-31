from __future__ import annotations
import os
import time
import math
import statistics
from typing import Deque, Optional
from collections import deque

from .gpio_mock import GPIO, GPIO_IS_MOCK


class HX711Reader:
    """
    Simple HX711 bit-banged reader with median and moving-average smoothing.
    In demo_mode, generates synthetic weight values.
    """

    def __init__(
        self,
        gpio_dout: int,
        gpio_sck: int,
        sample_rate: int = 10,
        median_window: int = 5,
        scale: float = 1.0,
        offset: float = 0.0,
        demo_mode: bool = False,
    ) -> None:
        self.dout = gpio_dout
        self.sck = gpio_sck
        self.sample_rate = max(1, min(80, sample_rate))
        self.median_window = max(1, median_window)
        self.scale = scale
        self.offset = offset
        # If running on mock GPIO, force demo mode to avoid blocking reads
        self.demo_mode = demo_mode or GPIO_IS_MOCK
        self._raw_window: Deque[float] = deque(maxlen=self.median_window)
        self._avg_window: Deque[float] = deque(maxlen=max(1, int(self.sample_rate)))
        self._t0 = time.time()

        if not self.demo_mode and GPIO is not None:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.sck, GPIO.OUT)
            GPIO.setup(self.dout, GPIO.IN)
            GPIO.output(self.sck, False)

    def close(self) -> None:
        if not self.demo_mode and GPIO is not None:
            try:
                GPIO.cleanup([self.dout, self.sck])
            except Exception:
                pass

    def tare(self) -> None:
        # Set offset so current reading becomes zero
        self.offset = self._read_raw_average(10)

    def zero(self) -> None:
        # Same user-facing behavior as tare: zero the current load
        self.offset = self._read_raw_average(10)

    def calibrate(self, known_grams: float, samples: int = 20, timeout_sec: float = 2.0) -> float:
        """Place known mass, compute scale so reading equals known_grams.
        
        Args:
            known_grams: Known weight in grams for calibration
            samples: Number of samples to average for calibration
            timeout_sec: Maximum time to wait for calibration to complete
            
        Returns:
            The new scale factor
            
        Raises:
            TimeoutError: If calibration takes longer than timeout_sec
            RuntimeError: If calibration fails (e.g., no change in reading)
        """
        if self.demo_mode:
            self.scale = 1.0
            return self.scale
            
        start_time = time.time()
        raw_readings = []
        
        # Collect samples with timeout
        while len(raw_readings) < samples:
            if time.time() - start_time > timeout_sec:
                raise TimeoutError(f"Calibration timed out after {timeout_sec} seconds")
                
            try:
                raw = self._read_raw()
                raw_readings.append(raw)
            except TimeoutError:
                continue  # Retry on timeout
                
        # Calculate average, excluding outliers
        if not raw_readings:
            raise RuntimeError("No valid readings during calibration")
            
        raw_avg = sum(raw_readings) / len(raw_readings)
        
        # Calculate scale factor
        if abs(raw_avg - self.offset) < 10:  # Threshold to avoid division by near-zero
            raise RuntimeError("Insufficient change in reading for calibration")
            
        self.scale = known_grams / (raw_avg - self.offset)
        return self.scale

    def read_grams(self) -> float:
        raw = self._read_raw()
        self._raw_window.append(raw)
        med = statistics.median(self._raw_window) if len(self._raw_window) else raw
        grams = (med - self.offset) * self.scale
        self._avg_window.append(grams)
        # Simple moving average over last second of samples
        smoothed = sum(self._avg_window) / len(self._avg_window)
        return float(smoothed)

    def _read_raw_average(self, n: int) -> float:
        vals = [self._read_raw() for _ in range(max(1, n))]
        return float(sum(vals) / len(vals))

    def _read_raw(self, timeout_sec: float = 0.1) -> float:
        if self.demo_mode or GPIO is None:
            # Synthetic value: small drifting sine wave with noise
            t = time.time() - self._t0
            return 100.0 + 10.0 * math.sin(t / 3.0) + (math.sin(t * 7) * 0.5)
            
        # Wait for data ready (DOUT goes low) with timeout
        start_time = time.time()
        while GPIO.input(self.dout) == 1:
            if time.time() - start_time > timeout_sec:
                raise TimeoutError("HX711 data ready timeout")
            time.sleep(0.001)  # Small sleep to prevent 100% CPU usage
            
        count = 0
        # 24 pulses to read the data
        for _ in range(24):
            GPIO.output(self.sck, True)
            time.sleep(0.0001)  # Small delay for clock pulse
            count = (count << 1) | GPIO.input(self.dout)
            GPIO.output(self.sck, False)
            time.sleep(0.0001)  # Small delay between clock pulses
            
        # Set gain to 128 (one more pulse)
        GPIO.output(self.sck, True)
        GPIO.output(self.sck, False)
        # convert signed 24-bit
        if count & 0x800000:
            count |= ~0xFFFFFF
        return float(count)

    # --- Debug/raw helpers for selecting channel/gain ---
    # HX711 modes: A128 (1 extra pulse), B32 (2 pulses), A64 (3 pulses)
    _MODE_PULSES = {"A128": 1, "B32": 2, "A64": 3}

    def _read_raw_with_next(self, next_pulses: int) -> int:
        """Read current 24-bit value, then send next_pulses to set next mode.
        Returns signed 24-bit integer.
        """
        if self.demo_mode or GPIO is None:
            # Provide a deterministic-ish triad for demo
            t = time.time() - self._t0
            base = int(100000 + 5000 * math.sin(t / 2.0))
            return base
        # Wait data ready
        timeout = time.time() + 0.1
        while GPIO.input(self.dout) == 1:
            if time.time() > timeout:
                break
        count = 0
        for _ in range(24):
            GPIO.output(self.sck, True)
            count = (count << 1) | GPIO.input(self.dout)
            GPIO.output(self.sck, False)
        # set mode for next conversion
        for _ in range(max(1, min(3, int(next_pulses)))):
            GPIO.output(self.sck, True)
            GPIO.output(self.sck, False)
        # sign extend
        if count & 0x800000:
            count |= ~0xFFFFFF
        return int(count)

    def read_raw_mode(self, mode: str) -> int:
        """Return signed 24-bit raw value for the requested mode ('A128','B32','A64').
        Performs a priming read to switch into the requested mode, then a second
        read to fetch a sample from that mode.
        """
        mode = mode.upper()
        pulses = self._MODE_PULSES.get(mode, 1)
        # prime into requested mode (discard value)
        _ = self._read_raw_with_next(pulses)
        # now read a value while keeping same mode selected for next
        val = self._read_raw_with_next(pulses)
        return val

    def read_raw_all_modes(self) -> dict:
        """Read raw values for B32, A64, and A128 sequentially and return a dict."""
        return {
            "B32": self.read_raw_mode("B32"),
            "A64": self.read_raw_mode("A64"),
            "A128": self.read_raw_mode("A128"),
        }
