"""Newport ESP301/302 multi-axis motion controller driver.

Supports up to 3 axes via RS-232 serial. Uses the Newport
ESP command protocol (ASCII, CR/LF terminated).

Typical connection: 921600 baud, 8N1, RTS/CTS flow control.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

from ..base import MotionController, InstrumentInfo

try:
    import serial
except ImportError:
    serial = None  # type: ignore

logger = logging.getLogger(__name__)


class NewportESP301(MotionController):
    """Driver for Newport ESP301/ESP302 multi-axis controllers.

    Parameters
    ----------
    port : Serial port (e.g. 'COM5', '/dev/ttyUSB0').
    axes : Number of axes (1, 2, or 3).
    baudrate : Serial baud rate (default 921600).
    """

    def __init__(self, port: str = "COM5", axes: int = 3,
                 baudrate: int = 921600, mock: bool = False):
        super().__init__(mock=mock)
        self.port = port
        self.n_axes = axes
        self.baudrate = baudrate
        self._ser: Optional[serial.Serial] = None

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("Newport", "ESP301", description="Mock"))
            return "Connected (mock)"
        if serial is None:
            raise ImportError("pyserial required")
        self._ser = serial.Serial(
            self.port, self.baudrate, timeout=1.0,
            rtscts=True, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
        )
        self._ser.reset_input_buffer()
        info = self.identify()
        self._set_connected(info)
        return f"Connected: {info.model} ({info.serial})"

    def disconnect(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        resp = self._query("VE?")
        return InstrumentInfo(vendor="Newport", model="ESP301", firmware=resp)

    def _send(self, cmd: str) -> None:
        if self._mock:
            return
        self._ser.write(f"{cmd}\r\n".encode("ascii"))
        self._ser.flush()

    def _query(self, cmd: str) -> str:
        if self._mock:
            return "Mock"
        self._send(cmd)
        return self._ser.readline().decode("ascii", errors="replace").strip()

    def _check_error(self) -> str | None:
        err = self._query("TB?")
        if err and not err.startswith("0"):
            return err
        return None

    # ── Motion ───────────────────────────────────────────────────

    @property
    def position(self) -> float:
        return self.get_position(1)

    def get_position(self, axis: int = 1) -> float:
        resp = self._query(f"{axis}TP")
        try:
            return float(resp)
        except ValueError:
            return 0.0

    def move_absolute(self, position_mm: float, axis: int = 1, timeout: float = 30.0) -> None:
        self._send(f"{axis}PA{position_mm:.6f}")
        self._wait_motion_done(axis, timeout)

    def move_relative(self, displacement_mm: float, axis: int = 1, timeout: float = 30.0) -> None:
        self._send(f"{axis}PR{displacement_mm:.6f}")
        self._wait_motion_done(axis, timeout)

    def home(self, axis: int = 1, timeout: float = 60.0) -> None:
        self._send(f"{axis}OR")
        self._wait_motion_done(axis, timeout)

    def stop(self, axis: int = 1) -> None:
        self._send(f"{axis}ST")

    def stop_all(self) -> None:
        self._send("ST")

    def _wait_motion_done(self, axis: int, timeout: float) -> None:
        if self._mock:
            return
        t0 = time.monotonic()
        time.sleep(0.1)
        while time.monotonic() - t0 < timeout:
            resp = self._query(f"{axis}MD?")
            if resp.strip() == "1":
                return
            time.sleep(0.05)
        raise TimeoutError(f"ESP301 axis {axis} motion not done in {timeout}s")

    # ── Configuration ────────────────────────────────────────────

    @property
    def velocity(self) -> float:
        return self.get_velocity(1)

    @velocity.setter
    def velocity(self, value: float) -> None:
        self.set_velocity(value, 1)

    def get_velocity(self, axis: int = 1) -> float:
        resp = self._query(f"{axis}VA?")
        try:
            return float(resp)
        except ValueError:
            return 0.0

    def set_velocity(self, velocity: float, axis: int = 1) -> None:
        self._send(f"{axis}VA{velocity:.6f}")

    def get_acceleration(self, axis: int = 1) -> float:
        resp = self._query(f"{axis}AC?")
        try:
            return float(resp)
        except ValueError:
            return 0.0

    def set_acceleration(self, accel: float, axis: int = 1) -> None:
        self._send(f"{axis}AC{accel:.6f}")

    def motor_on(self, axis: int = 1) -> None:
        self._send(f"{axis}MO")

    def motor_off(self, axis: int = 1) -> None:
        self._send(f"{axis}MF")

    def get_stage_model(self, axis: int = 1) -> str:
        return self._query(f"{axis}ID?")

    def get_all_positions(self) -> dict[int, float]:
        return {ax: self.get_position(ax) for ax in range(1, self.n_axes + 1)}
