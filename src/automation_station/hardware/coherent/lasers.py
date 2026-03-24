"""Coherent laser drivers.

Astrella one-box Ti:Sapphire amplifier, Chameleon tunable oscillator,
OBIS CW diode laser, Genesis OPSL. All serial RS-232 based.
"""
from __future__ import annotations

import time
import logging
from typing import Any, Optional

from ..base import LaserController, InstrumentInfo

try:
    import serial
except ImportError:
    serial = None  # type: ignore

logger = logging.getLogger(__name__)


class CoherentAstrella(LaserController):
    """Coherent Astrella one-box Ti:Sapphire regenerative amplifier.

    800 nm, ~35 fs, up to 7 mJ @ 1 kHz. Typical pump for Opera OPA.
    Serial RS-232 control at 19200 baud.

    Parameters
    ----------
    port : Serial port.
    """

    def __init__(self, port: str = "COM9", baudrate: int = 19200, mock: bool = False):
        super().__init__(mock=mock)
        self._port = port
        self._baudrate = baudrate
        self._ser = None
        self._emitting = False
        self._power = 0.0
        self._wavelength = 800.0
        self._rep_rate = 1000.0
        self._pulse_energy = 7e-3

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo(
                "Coherent", "Astrella", description="Mock — 800 nm, 7 mJ, 1 kHz"
            ))
            return "Connected (mock)"
        if serial is None:
            raise ImportError("pyserial required")
        try:
            self._ser = serial.Serial(self._port, self._baudrate, timeout=2.0)
            info = self.identify()
            self._set_connected(info)
            return f"Connected: {info.model} (S/N: {info.serial})"
        except Exception as e:
            self._set_error(str(e))
            return f"Failed: {e}"

    def disconnect(self) -> None:
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        if self._mock:
            return InstrumentInfo("Coherent", "Astrella", "MOCK-AST001",
                                  description="800 nm, <35 fs, 7 mJ @ 1 kHz")
        resp = self._query("*IDN?")
        parts = resp.split(",") if resp else ["Coherent", "Astrella"]
        return InstrumentInfo(
            vendor=parts[0].strip() if len(parts) > 0 else "Coherent",
            model=parts[1].strip() if len(parts) > 1 else "Astrella",
            serial=parts[2].strip() if len(parts) > 2 else "",
        )

    def _send(self, cmd: str) -> None:
        if self._mock or not self._ser:
            return
        self._ser.write(f"{cmd}\r\n".encode("ascii"))
        self._ser.flush()

    def _query(self, cmd: str) -> str:
        if self._mock:
            return "Mock"
        self._send(cmd)
        return self._ser.readline().decode("ascii", errors="replace").strip()

    def set_emission(self, on: bool) -> None:
        self._emitting = on
        if not self._mock:
            self._send(f"SHUTTER:{'OPEN' if on else 'CLOSE'}")

    @property
    def is_emitting(self) -> bool:
        return self._emitting

    @property
    def power_w(self) -> float:
        return self._power

    @property
    def wavelength_nm(self) -> float:
        return self._wavelength

    @property
    def rep_rate_hz(self) -> float:
        return self._rep_rate

    @rep_rate_hz.setter
    def rep_rate_hz(self, value: float) -> None:
        self._rep_rate = value
        if not self._mock:
            self._send(f"REPRATE {value:.0f}")

    @property
    def pulse_energy_j(self) -> float:
        return self._pulse_energy

    def get_status(self) -> dict[str, Any]:
        if not self._mock:
            # Query real status
            pass
        return {
            "emitting": self._emitting,
            "power_w": self._power,
            "wavelength_nm": self._wavelength,
            "rep_rate_hz": self._rep_rate,
            "pulse_energy_j": self._pulse_energy,
            "pulse_width_fs": 35.0,
            "medium": "Ti:Sapphire",
        }
