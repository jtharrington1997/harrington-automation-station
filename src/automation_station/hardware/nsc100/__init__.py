"""Newport NSC100 serial communication driver.

Pure-Python serial interface for the Newport NSC100 single-axis
motion controller. Implements the NSC100 command protocol over RS-232
with automatic error handling, state machine tracking, and motion
completion detection.

Usage:
    from automation_station.hardware.nsc100 import NSC100

    stage = NSC100("COM4", axis=1)
    stage.connect()
    stage.home()
    stage.move_absolute(25.0)
    print(stage.position)
    stage.disconnect()
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

try:
    import serial
except ImportError:
    serial = None  # type: ignore

logger = logging.getLogger(__name__)


# ── Controller states (from NSC100 manual Table 4) ──────────────

class ControllerState(str, Enum):
    """NSC100 positioner error and state codes."""
    NOT_REFERENCED_RESET = "0A"
    NOT_REFERENCED_HOMING = "0B"
    NOT_REFERENCED_CONFIGURATION = "0C"
    NOT_REFERENCED_DISABLE = "0D"
    NOT_REFERENCED_READY = "0E"
    NOT_REFERENCED_MOVING = "0F"
    NOT_REFERENCED_JOGGING_POS = "10"
    NOT_REFERENCED_JOGGING_NEG = "11"
    CONFIGURATION = "14"
    HOMING = "1E"
    MOVING = "28"
    READY_HOMED = "32"
    READY_MOVING = "33"
    READY_DISABLE = "34"
    READY_JOGGING_POS = "35"
    READY_JOGGING_NEG = "36"
    DISABLE = "3C"
    # Error states
    ERROR_POSITIVE_LIMIT = "01"
    ERROR_NEGATIVE_LIMIT = "02"

    @property
    def is_ready(self) -> bool:
        return self.value in ("32", "33", "34")

    @property
    def is_moving(self) -> bool:
        return self.value in ("0F", "10", "11", "1E", "28", "33", "35", "36")

    @property
    def is_homed(self) -> bool:
        return self.value.startswith("3") or self.value == "28"

    @property
    def is_error(self) -> bool:
        return self.value in ("01", "02")


# ── Error codes ──────────────────────────────────────────────────

NSC100_ERRORS = {
    "A": "Unknown message code or floating point controller address",
    "B": "Controller address not correct",
    "C": "Parameter missing or out of range",
    "D": "Execution not allowed",
    "E": "Home sequence already started",
    "F": "ESP stage name unknown",
    "G": "Displacement out of limits",
    "H": "Execution not allowed in NOT REFERENCED state",
    "I": "Execution not allowed in CONFIGURATION state",
    "J": "Execution not allowed in DISABLE state",
    "K": "Execution not allowed in READY state",
    "L": "Execution not allowed in HOMING state",
    "M": "Execution not allowed in MOVING state",
    "N": "Current position out of software limit",
    "S": "Communication timeout",
    "U": "Error during EEPROM access",
    "V": "Error during command execution",
}


@dataclass
class NSC100Response:
    """Parsed response from the controller."""
    axis: int
    command: str
    value: str
    raw: str
    error: str | None = None


class NSC100:
    """Driver for Newport NSC100 single-axis motion controller.

    Parameters
    ----------
    port : Serial port (e.g. 'COM4', '/dev/ttyUSB0').
    axis : Controller axis address (typically 1).
    baudrate : Serial baud rate (default 57600 per NSC100 spec).
    timeout : Serial read timeout in seconds.
    """

    def __init__(
        self,
        port: str = "COM4",
        axis: int = 1,
        baudrate: int = 57600,
        timeout: float = 1.0,
    ):
        if serial is None:
            raise ImportError("pyserial is required: pip install pyserial")
        self.port = port
        self.axis = axis
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None
        self._connected = False

    # ── Connection ───────────────────────────────────────────────

    def connect(self) -> str:
        """Open serial connection to the controller."""
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                xonxoff=True,  # NSC100 uses XON/XOFF flow control
            )
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            self._connected = True

            # Query identity
            identity = self.query("VE")
            state = self.state
            logger.info("Connected to NSC100 on %s: %s (state: %s)", self.port, identity, state)
            return f"Connected: {identity} (state: {state.value})"
        except Exception as e:
            self._connected = False
            logger.error("NSC100 connection failed on %s: %s", self.port, e)
            raise ConnectionError(f"NSC100 connect failed on {self.port}: {e}") from e

    def disconnect(self) -> None:
        """Close serial connection."""
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._connected = False
        logger.info("NSC100 disconnected")

    @property
    def connected(self) -> bool:
        return self._connected and self._ser is not None and self._ser.is_open

    # ── Low-level communication ──────────────────────────────────

    def _send(self, command: str) -> None:
        """Send a command string to the controller."""
        if not self.connected:
            raise ConnectionError("NSC100 not connected")
        msg = f"{self.axis}{command}\r\n"
        self._ser.write(msg.encode("ascii"))
        self._ser.flush()
        logger.debug("TX: %s", msg.strip())

    def _receive(self) -> str:
        """Read response line from the controller."""
        if not self.connected:
            raise ConnectionError("NSC100 not connected")
        raw = self._ser.readline().decode("ascii", errors="replace").strip()
        logger.debug("RX: %s", raw)
        return raw

    def _parse_response(self, raw: str) -> NSC100Response:
        """Parse an NSC100 response string."""
        if not raw:
            return NSC100Response(axis=self.axis, command="", value="", raw=raw, error="No response")
        # Response format: {axis}{command}{value}
        # First char(s) = axis, then 2-char command, then value
        try:
            axis = int(raw[0])
            cmd = raw[1:3]
            val = raw[3:]
            return NSC100Response(axis=axis, command=cmd, value=val, raw=raw)
        except (ValueError, IndexError):
            return NSC100Response(axis=self.axis, command="", value=raw, raw=raw)

    def command(self, cmd: str, value: str = "") -> None:
        """Send a command (no response expected)."""
        self._send(f"{cmd}{value}")

    def query(self, cmd: str, value: str = "") -> str:
        """Send a query and return the response value."""
        self._send(f"{cmd}{value}")
        raw = self._receive()
        resp = self._parse_response(raw)
        if resp.error:
            logger.warning("Query %s error: %s", cmd, resp.error)
        return resp.value

    # ── Error checking ───────────────────────────────────────────

    def get_error(self) -> str | None:
        """Query and clear the last error. Returns None if no error."""
        err = self.query("TE")
        if err and err != "@":
            desc = NSC100_ERRORS.get(err, f"Unknown error code: {err}")
            logger.warning("NSC100 error: %s — %s", err, desc)
            return desc
        return None

    # ── State ────────────────────────────────────────────────────

    @property
    def state(self) -> ControllerState:
        """Query current controller state."""
        raw = self.query("TS")
        # Response is error_code + state_code (e.g. "0000001E")
        # Last two hex chars are the state
        code = raw[-2:] if len(raw) >= 2 else raw
        try:
            return ControllerState(code)
        except ValueError:
            logger.warning("Unknown state code: %s", code)
            return ControllerState.NOT_REFERENCED_RESET

    @property
    def is_ready(self) -> bool:
        return self.state.is_ready

    @property
    def is_moving(self) -> bool:
        return self.state.is_moving

    # ── Position ─────────────────────────────────────────────────

    @property
    def position(self) -> float:
        """Query current position in mm."""
        val = self.query("TP")
        try:
            return float(val)
        except ValueError:
            logger.warning("Could not parse position: %s", val)
            return 0.0

    @position.setter
    def position(self, value: float) -> None:
        """Move to absolute position (blocking)."""
        self.move_absolute(value)

    # ── Motion commands ──────────────────────────────────────────

    def home(self, timeout: float = 60.0) -> None:
        """Execute home search and wait for completion."""
        self.command("OR")
        self._wait_for_ready(timeout)

    def move_absolute(self, position_mm: float, timeout: float = 30.0) -> None:
        """Move to absolute position and wait for completion."""
        self.command("PA", f"{position_mm:.6f}")
        self._wait_for_ready(timeout)

    def move_relative(self, displacement_mm: float, timeout: float = 30.0) -> None:
        """Move by relative displacement and wait for completion."""
        self.command("PR", f"{displacement_mm:.6f}")
        self._wait_for_ready(timeout)

    def stop(self) -> None:
        """Immediately stop motion."""
        self.command("ST")

    def _wait_for_ready(self, timeout: float = 30.0) -> None:
        """Poll until controller reaches READY state."""
        t0 = time.monotonic()
        time.sleep(0.1)  # let command propagate
        while time.monotonic() - t0 < timeout:
            st = self.state
            if st.is_ready:
                return
            if st.is_error:
                err = self.get_error()
                raise RuntimeError(f"NSC100 motion error: {err}")
            time.sleep(0.05)
        raise TimeoutError(f"NSC100 did not reach READY within {timeout}s (state: {self.state})")

    # ── Configuration ────────────────────────────────────────────

    @property
    def velocity(self) -> float:
        """Query current velocity setting (mm/s)."""
        val = self.query("VA")
        try:
            return float(val)
        except ValueError:
            return 0.0

    @velocity.setter
    def velocity(self, value: float) -> None:
        """Set motion velocity (mm/s)."""
        self.command("VA", f"{value:.6f}")

    @property
    def acceleration(self) -> float:
        """Query acceleration (mm/s²)."""
        val = self.query("AC")
        try:
            return float(val)
        except ValueError:
            return 0.0

    @acceleration.setter
    def acceleration(self, value: float) -> None:
        """Set acceleration (mm/s²)."""
        self.command("AC", f"{value:.6f}")

    @property
    def negative_limit(self) -> float:
        val = self.query("SL")
        try:
            return float(val)
        except ValueError:
            return 0.0

    @negative_limit.setter
    def negative_limit(self, value: float) -> None:
        self.command("SL", f"{value:.6f}")

    @property
    def positive_limit(self) -> float:
        val = self.query("SR")
        try:
            return float(val)
        except ValueError:
            return 0.0

    @positive_limit.setter
    def positive_limit(self, value: float) -> None:
        self.command("SR", f"{value:.6f}")

    def reset(self) -> None:
        """Reset controller to power-on state."""
        self.command("RS")
        time.sleep(2.0)

    def get_stage_model(self) -> str:
        """Query the configured stage model identifier."""
        return self.query("ID")

    # ── Context manager ──────────────────────────────────────────

    def __enter__(self) -> NSC100:
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        status = "connected" if self.connected else "disconnected"
        return f"NSC100(port={self.port!r}, axis={self.axis}, {status})"
