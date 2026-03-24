"""Thorlabs optomechanical accessory drivers.

FW102C/FW212C filter wheels, MFF101/102 flip mounts, SC10 shutters,
and ELL14 Elliptec rotation stages. All serial-based.
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


class ThorlabsFilterWheel(MotionController):
    """Thorlabs FW102C (6-pos) or FW212C (12-pos) motorized filter wheel.

    Serial protocol: ASCII commands terminated by CR.
    Default baud: 115200.
    """

    def __init__(self, port: str = "COM7", n_positions: int = 6,
                 baudrate: int = 115200, mock: bool = False):
        super().__init__(mock=mock)
        self.port = port
        self.n_positions = n_positions
        self.baudrate = baudrate
        self._ser: Optional[serial.Serial] = None
        self._labels: dict[int, str] = {}

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("Thorlabs", "FW102C", description="Mock"))
            return "Connected (mock)"
        if serial is None:
            raise ImportError("pyserial required")
        self._ser = serial.Serial(self.port, self.baudrate, timeout=2.0)
        self._ser.reset_input_buffer()
        info = self.identify()
        self._set_connected(info)
        return f"Connected: {info.model}"

    def disconnect(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        resp = self._query("*idn?")
        return InstrumentInfo(vendor="Thorlabs", model="FW102C", firmware=resp)

    def _send(self, cmd: str) -> None:
        if self._mock:
            return
        self._ser.write(f"{cmd}\r".encode("ascii"))
        self._ser.flush()

    def _query(self, cmd: str) -> str:
        if self._mock:
            return "Mock"
        self._send(cmd)
        time.sleep(0.1)
        return self._ser.readline().decode("ascii", errors="replace").strip()

    @property
    def position(self) -> float:
        """Current filter position (1-indexed)."""
        resp = self._query("pos?")
        try:
            return float(resp)
        except ValueError:
            return 1.0

    def move_absolute(self, position_mm: float, axis: int = 1, timeout: float = 10.0) -> None:
        """Move to filter position (1-6 or 1-12)."""
        pos = max(1, min(int(position_mm), self.n_positions))
        self._send(f"pos={pos}")
        time.sleep(1.0)  # wheel rotation time

    def home(self, axis: int = 1, timeout: float = 10.0) -> None:
        self.move_absolute(1)

    def set_label(self, position: int, label: str) -> None:
        """Associate a human-readable label with a filter position."""
        self._labels[position] = label

    def get_label(self, position: int) -> str:
        return self._labels.get(position, f"Position {position}")

    @property
    def speed(self) -> int:
        """Speed setting (0=slow, 1=fast)."""
        resp = self._query("speed?")
        try:
            return int(resp)
        except ValueError:
            return 0

    @speed.setter
    def speed(self, value: int) -> None:
        self._send(f"speed={value}")

    @property
    def trigger_mode(self) -> int:
        """Trigger mode (0=input, 1=output)."""
        resp = self._query("trig?")
        try:
            return int(resp)
        except ValueError:
            return 0

    @trigger_mode.setter
    def trigger_mode(self, value: int) -> None:
        self._send(f"trig={value}")


class ThorlabsFlipMount(MotionController):
    """Thorlabs MFF101/MFF102 motorized flip mount.

    Uses Kinesis .NET SDK (Windows) or APT protocol (cross-platform).
    Positions: 0 (down) and 1 (up), mapped to 0mm and 1mm.
    """

    def __init__(self, serial_no: str = "", mock: bool = False):
        super().__init__(mock=mock)
        self._serial_no = serial_no
        self._device = None
        self._current_pos = 0

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("Thorlabs", "MFF101", description="Mock"))
            return "Connected (mock)"
        try:
            import clr
            clr.AddReference(r"C:\Program Files\Thorlabs\Kinesis\Thorlabs.MotionControl.FilterFlipperCLI.dll")
            from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
            from Thorlabs.MotionControl.FilterFlipperCLI import FilterFlipper
            DeviceManagerCLI.BuildDeviceList()
            self._device = FilterFlipper.CreateFilterFlipper(self._serial_no)
            self._device.Connect(self._serial_no)
            time.sleep(0.5)
            self._device.StartPolling(250)
            self._set_connected(InstrumentInfo("Thorlabs", "MFF101", serial=self._serial_no))
            return f"Connected: MFF101 (S/N {self._serial_no})"
        except Exception as e:
            self._set_error(str(e))
            return f"Failed: {e}"

    def disconnect(self) -> None:
        if self._device:
            try:
                self._device.StopPolling()
                self._device.Disconnect(False)
            except Exception:
                pass
        self._device = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        return InstrumentInfo("Thorlabs", "MFF101", serial=self._serial_no)

    @property
    def position(self) -> float:
        if self._mock:
            return float(self._current_pos)
        try:
            return float(str(self._device.Position))
        except Exception:
            return 0.0

    def move_absolute(self, position_mm: float, axis: int = 1, timeout: float = 5.0) -> None:
        """Flip to position 1 (up) or 2 (down)."""
        pos = 1 if position_mm < 0.5 else 2
        if self._mock:
            self._current_pos = pos
            return
        self._device.SetPosition(pos, int(timeout * 1000))

    def flip(self) -> None:
        """Toggle between positions."""
        current = self.position
        self.move_absolute(2.0 if current < 1.5 else 0.0)

    def home(self, axis: int = 1, timeout: float = 10.0) -> None:
        self.move_absolute(0.0)


class ThorlabsShutter(MotionController):
    """Thorlabs SC10 optical beam shutter controller.

    Serial protocol, default 9600 baud.
    """

    def __init__(self, port: str = "COM8", baudrate: int = 9600, mock: bool = False):
        super().__init__(mock=mock)
        self.port = port
        self.baudrate = baudrate
        self._ser: Optional[serial.Serial] = None
        self._is_open = False

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("Thorlabs", "SC10", description="Mock"))
            return "Connected (mock)"
        if serial is None:
            raise ImportError("pyserial required")
        self._ser = serial.Serial(self.port, self.baudrate, timeout=1.0)
        self._set_connected(InstrumentInfo("Thorlabs", "SC10"))
        return "Connected: SC10"

    def disconnect(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        return InstrumentInfo("Thorlabs", "SC10")

    @property
    def position(self) -> float:
        return 1.0 if self._is_open else 0.0

    def move_absolute(self, position_mm: float, axis: int = 1, timeout: float = 2.0) -> None:
        if position_mm > 0.5:
            self.open()
        else:
            self.close()

    def home(self, axis: int = 1, timeout: float = 5.0) -> None:
        self.close()

    def open(self) -> None:
        """Open the shutter."""
        if not self._mock and self._ser:
            self._ser.write(b"ens\r")
        self._is_open = True

    def close(self) -> None:
        """Close the shutter."""
        if not self._mock and self._ser:
            self._ser.write(b"ens\r")
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    def toggle(self) -> None:
        if self._is_open:
            self.close()
        else:
            self.open()
