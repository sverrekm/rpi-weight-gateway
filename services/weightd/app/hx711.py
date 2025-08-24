from __future__ import annotations
import os
import time
import math
import statistics
from typing import Deque, Optional
from collections import deque

from .gpio_mock import GPIO


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
        self.demo_mode = demo_mode
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
        self.offset = self._read_raw_average(10) if not self.demo_mode else 0.0

    def zero(self) -> None:
        self.offset = 0.0

    def calibrate(self, known_grams: float) -> float:
        """Place known mass, compute scale so reading equals known_grams."""
        raw = self._read_raw_average(20) if not self.demo_mode else known_grams
        if raw - self.offset == 0:
            self.scale = 1.0
        else:
            self.scale = known_grams / (raw - self.offset)
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

    def _read_raw(self) -> float:
        if self.demo_mode or GPIO is None:
            # Synthetic value: small drifting sine wave with noise
            t = time.time() - self._t0
            return 100.0 + 10.0 * math.sin(t / 3.0) + (math.sin(t * 7) * 0.5)
        # Wait for data ready (DOUT goes low)
        timeout = time.time() + 0.1
        while GPIO.input(self.dout) == 1:
            if time.time() > timeout:
                break
        count = 0
        # 24 pulses
        for _ in range(24):
            GPIO.output(self.sck, True)
            count = (count << 1) | GPIO.input(self.dout)
            GPIO.output(self.sck, False)
        # set gain 128 (one more pulse)
        GPIO.output(self.sck, True)
        GPIO.output(self.sck, False)
        # convert signed 24-bit
        if count & 0x800000:
            count |= ~0xFFFFFF
        return float(count)
