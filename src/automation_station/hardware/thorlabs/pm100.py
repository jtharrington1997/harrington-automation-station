"""Thorlabs PM100D / PM400 optical power meter driver.

Uses VISA/SCPI commands over USB. Requires pyvisa + NI-VISA backend
or pyvisa-py for pure-Python USB communication.

Supports power, energy, and frequency measurements with
configurable wavelength, attenuation, and averaging.
"""
from __future__ import annotations

import time
import logging
from typing import Optional, Any

import numpy as np

from ..base import Detector, InstrumentInfo

logger = logging.getLogger(__name__)


class ThorlabsPM100(Detector):
    """Driver for Thorlabs PM100D and PM400 power meters.

    Parameters
    ----------
    resource : VISA resource string (e.g. 'USB0::0x1313::0x8078::...').
        If None, attempts auto-detection.
    """

    def __init__(self, resource: str | None = None, mock: bool = False):
        super().__init__(mock=mock)
        self._resource = resource
        self._inst = None

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("Thorlabs", "PM100D", description="Mock"))
            return "Connected (mock)"
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            if self._resource is None:
                resources = rm.list_resources()
                pm_resources = [r for r in resources if "0x1313" in r]
                if not pm_resources:
                    raise ConnectionError("No Thorlabs power meter found")
                self._resource = pm_resources[0]
            self._inst = rm.open_resource(self._resource)
            self._inst.timeout = 5000
            info = self.identify()
            self._set_connected(info)
            return f"Connected: {info.model} (S/N: {info.serial})"
        except ImportError:
            raise ImportError("pyvisa required: pip install pyvisa pyvisa-py")

    def disconnect(self) -> None:
        if self._inst:
            try:
                self._inst.close()
            except Exception:
                pass
        self._inst = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        if self._mock:
            return InstrumentInfo("Thorlabs", "PM100D", "MOCK001")
        resp = self._inst.query("*IDN?").strip()
        parts = resp.split(",")
        return InstrumentInfo(
            vendor=parts[0].strip() if len(parts) > 0 else "Thorlabs",
            model=parts[1].strip() if len(parts) > 1 else "PM100",
            serial=parts[2].strip() if len(parts) > 2 else "",
            firmware=parts[3].strip() if len(parts) > 3 else "",
        )

    def read(self, n_avg: int = 1, delay: float = 0.05) -> float:
        if self._mock:
            return 0.001 + np.random.normal(0, 1e-5)
        readings = []
        for _ in range(n_avg):
            val = float(self._inst.query("MEAS:POW?"))
            readings.append(val)
            if n_avg > 1:
                time.sleep(delay)
        return float(np.mean(readings))

    @property
    def units(self) -> str:
        if self._mock:
            return "W"
        return self._inst.query("SENS:POW:UNIT?").strip()

    def read_energy(self, n_avg: int = 1) -> float:
        """Read energy measurement (for pulsed sources)."""
        if self._mock:
            return 1e-6 + np.random.normal(0, 1e-8)
        self._inst.write("CONF:ENER")
        readings = []
        for _ in range(n_avg):
            readings.append(float(self._inst.query("MEAS:ENER?")))
        return float(np.mean(readings))

    def read_frequency(self) -> float:
        """Read pulse frequency (Hz)."""
        if self._mock:
            return 10000.0
        return float(self._inst.query("MEAS:FREQ?"))

    # ── Configuration ────────────────────────────────────────────

    @property
    def wavelength_nm(self) -> float:
        if self._mock:
            return 1030.0
        return float(self._inst.query("SENS:CORR:WAV?"))

    @wavelength_nm.setter
    def wavelength_nm(self, value: float) -> None:
        if not self._mock:
            self._inst.write(f"SENS:CORR:WAV {value:.1f}")

    @property
    def auto_range(self) -> bool:
        if self._mock:
            return True
        return self._inst.query("SENS:POW:RANG:AUTO?").strip() == "1"

    @auto_range.setter
    def auto_range(self, value: bool) -> None:
        if not self._mock:
            self._inst.write(f"SENS:POW:RANG:AUTO {'ON' if value else 'OFF'}")

    @property
    def averaging(self) -> int:
        if self._mock:
            return 1
        return int(self._inst.query("SENS:AVER:COUN?"))

    @averaging.setter
    def averaging(self, count: int) -> None:
        if not self._mock:
            self._inst.write(f"SENS:AVER:COUN {count}")

    def set_attenuation(self, db: float) -> None:
        """Set beam attenuation in dB."""
        if not self._mock:
            self._inst.write(f"SENS:CORR:LOSS:INP:MAGN {db}")

    def zero(self) -> None:
        """Zero the sensor (dark current subtraction)."""
        if not self._mock:
            self._inst.write("SENS:CORR:COLL:ZERO:INIT")
            time.sleep(3.0)  # zeroing takes a few seconds

    @property
    def sensor_info(self) -> dict:
        """Query connected sensor head information."""
        if self._mock:
            return {"type": "S121C", "range_w": 500e-3}
        return {
            "type": self._inst.query("SYST:SENS:IDN?").strip(),
        }

    def read_burst(self, n_samples: int, rate_hz: float = 10.0) -> list[float]:
        """High-speed burst read using hardware averaging."""
        if self._mock:
            return [0.001 + np.random.normal(0, 1e-5) for _ in range(n_samples)]
        results = []
        dt = 1.0 / rate_hz
        for _ in range(n_samples):
            results.append(float(self._inst.query("MEAS:POW?")))
            time.sleep(dt)
        return results
