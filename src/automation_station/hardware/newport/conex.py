"""Newport CONEX-CC / CONEX-AG piezo controller driver.

Compact USB controllers for Newport actuators. Uses ASCII serial
protocol similar to SMC100 but with CONEX-specific commands.
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


class NewportCONEX(MotionController):
    """Driver for Newport CONEX-CC and CONEX-AG controllers.

    Parameters
    ----------
    port : Serial port.
    controller_id : Controller address (default 1).
    baudrate : Default 921600 for CONEX-CC.
    """

    def __init__(self, port: str = "COM6", controller_id: int = 1,
                 baudrate: int = 921600, mock: bool = False):
        super().__init__(mock=mock)
        self.port = port
        self.cid = controller_id
        self.baudrate = baudrate
        self._ser: Optional[serial.Serial] = None

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("Newport", "CONEX-CC", description="Mock"))
            return "Connected (mock)"
        if serial is None:
            raise ImportError("pyserial required")
        self._ser = serial.Serial(self.port, self.baudrate, timeout=1.0)
        self._ser.reset_input_buffer()
        info = self.identify()
        self._set_connected(info)
        # Check if homed
        state = self._get_state()
        if state in ("0A", "0B", "0C", "0D", "0E"):
            logger.info("CONEX not homed — call home() first")
        return f"Connected: {info.model} (state: {state})"

    def disconnect(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        resp = self._query("VE")
        return InstrumentInfo(vendor="Newport", model="CONEX-CC", firmware=resp)

    def _send(self, cmd: str) -> None:
        if self._mock:
            return
        msg = f"{self.cid}{cmd}\r\n"
        self._ser.write(msg.encode("ascii"))
        self._ser.flush()

    def _query(self, cmd: str) -> str:
        if self._mock:
            return "Mock"
        self._send(cmd)
        return self._ser.readline().decode("ascii", errors="replace").strip()

    def _get_state(self) -> str:
        resp = self._query("TS")
        return resp[-2:] if len(resp) >= 2 else "00"

    @property
    def position(self) -> float:
        resp = self._query("TP")
        try:
            # Response: {cid}TP{value}
            val = resp[3:] if len(resp) > 3 else resp
            return float(val)
        except ValueError:
            return 0.0

    def move_absolute(self, position_mm: float, axis: int = 1, timeout: float = 30.0) -> None:
        self._send(f"PA{position_mm:.6f}")
        self._wait_ready(timeout)

    def move_relative(self, displacement_mm: float, axis: int = 1, timeout: float = 30.0) -> None:
        self._send(f"PR{displacement_mm:.6f}")
        self._wait_ready(timeout)

    def home(self, axis: int = 1, timeout: float = 60.0) -> None:
        self._send("OR")
        self._wait_ready(timeout)

    def stop(self, axis: int = 1) -> None:
        self._send("ST")

    def _wait_ready(self, timeout: float) -> None:
        if self._mock:
            return
        t0 = time.monotonic()
        time.sleep(0.1)
        while time.monotonic() - t0 < timeout:
            state = self._get_state()
            if state in ("32", "33", "34"):
                return
            time.sleep(0.05)
        raise TimeoutError(f"CONEX not ready in {timeout}s")

    @property
    def velocity(self) -> float:
        resp = self._query("VA?")
        try:
            return float(resp[4:]) if len(resp) > 4 else 0.0
        except ValueError:
            return 0.0

    @velocity.setter
    def velocity(self, value: float) -> None:
        self._send(f"VA{value:.6f}")
