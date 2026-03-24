"""Base classes for all hardware instruments.

Every driver inherits from one of these ABCs, ensuring a uniform
interface across vendors. The connect/disconnect lifecycle, error
handling, and mock support patterns are standardized here.

No Streamlit imports.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class InstrumentInfo:
    """Metadata returned by identify()."""
    vendor: str
    model: str
    serial: str = ""
    firmware: str = ""
    description: str = ""


class Instrument(ABC):
    """Base class for all hardware instruments.

    Subclasses must implement connect(), disconnect(), and identify().
    The `available` flag tracks connection state. All drivers support
    a `mock` mode for testing without hardware.
    """

    def __init__(self, mock: bool = False):
        self._mock = mock
        self._state = ConnectionState.DISCONNECTED
        self._info: InstrumentInfo | None = None
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def available(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def info(self) -> InstrumentInfo | None:
        return self._info

    @property
    def mock(self) -> bool:
        return self._mock

    @abstractmethod
    def connect(self, **kwargs) -> str:
        """Connect to the instrument. Returns status message."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the instrument."""
        ...

    @abstractmethod
    def identify(self) -> InstrumentInfo:
        """Query instrument identification."""
        ...

    def _set_connected(self, info: InstrumentInfo | None = None) -> None:
        self._state = ConnectionState.CONNECTED
        self._info = info

    def _set_disconnected(self) -> None:
        self._state = ConnectionState.DISCONNECTED
        self._info = None

    def _set_error(self, msg: str) -> None:
        self._state = ConnectionState.ERROR
        self._logger.error(msg)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"{cls}(state={self._state.value}, mock={self._mock})"


class MotionController(Instrument):
    """Base class for single- or multi-axis motion controllers.

    Subclasses must implement position, move_absolute, and home.
    Multi-axis controllers override with axis parameters.
    """

    @property
    @abstractmethod
    def position(self) -> float:
        """Current position in mm."""
        ...

    @abstractmethod
    def move_absolute(self, position_mm: float, axis: int = 1, timeout: float = 30.0) -> None:
        """Move to absolute position and block until complete."""
        ...

    def move_relative(self, displacement_mm: float, axis: int = 1, timeout: float = 30.0) -> None:
        """Move by relative displacement. Default: compute from position."""
        current = self.position
        self.move_absolute(current + displacement_mm, axis=axis, timeout=timeout)

    @abstractmethod
    def home(self, axis: int = 1, timeout: float = 60.0) -> None:
        """Execute home/reference search."""
        ...

    def stop(self, axis: int = 1) -> None:
        """Emergency stop. Override for hardware-specific implementation."""
        self._logger.warning("stop() not implemented for %s", self.__class__.__name__)

    @property
    def velocity(self) -> float:
        """Current velocity in mm/s. Override in subclass."""
        return 0.0

    @velocity.setter
    def velocity(self, value: float) -> None:
        """Set velocity in mm/s. Override in subclass."""
        pass


class Detector(Instrument):
    """Base class for power meters, energy meters, and photodetectors."""

    @abstractmethod
    def read(self, n_avg: int = 1, delay: float = 0.1) -> float:
        """Read a measurement value (W, J, or V depending on detector type)."""
        ...

    @property
    def units(self) -> str:
        """Measurement units string. Override in subclass."""
        return "a.u."

    def read_burst(self, n_samples: int, rate_hz: float = 10.0) -> list[float]:
        """Read a burst of samples at the given rate. Default: loop read()."""
        results = []
        dt = 1.0 / rate_hz if rate_hz > 0 else 0.1
        for _ in range(n_samples):
            results.append(self.read())
            time.sleep(dt)
        return results


class LaserController(Instrument):
    """Base class for laser source control (emission, power, rep rate, etc.)."""

    @abstractmethod
    def set_emission(self, on: bool) -> None:
        """Enable or disable laser emission."""
        ...

    @property
    @abstractmethod
    def is_emitting(self) -> bool:
        """Whether the laser is currently emitting."""
        ...

    @property
    def power_w(self) -> float:
        """Current output power in watts. Override in subclass."""
        return 0.0

    @power_w.setter
    def power_w(self, value: float) -> None:
        """Set output power. Override in subclass."""
        pass

    @property
    def wavelength_nm(self) -> float:
        """Current wavelength in nm. Override for tunable sources."""
        return 0.0

    @property
    def rep_rate_hz(self) -> float:
        """Repetition rate in Hz. Override for pulsed lasers."""
        return 0.0

    @rep_rate_hz.setter
    def rep_rate_hz(self, value: float) -> None:
        pass

    @property
    def pulse_energy_j(self) -> float:
        """Pulse energy in joules. Override for pulsed lasers."""
        return 0.0

    def get_status(self) -> dict[str, Any]:
        """Return a dict of current laser status parameters."""
        return {
            "emitting": self.is_emitting,
            "power_w": self.power_w,
            "wavelength_nm": self.wavelength_nm,
            "rep_rate_hz": self.rep_rate_hz,
        }


class Spectrometer(Instrument):
    """Base class for spectrometers and spectrographs."""

    @abstractmethod
    def acquire(self, integration_time_s: float = 1.0) -> dict:
        """Acquire a spectrum. Returns dict with 'wavelength_nm' and 'intensity' arrays."""
        ...

    @property
    def wavelength_range_nm(self) -> tuple[float, float]:
        """Current wavelength range. Override in subclass."""
        return (0.0, 0.0)

    def set_grating(self, grating_id: int) -> None:
        """Select grating. Override for multi-grating instruments."""
        pass

    def set_center_wavelength(self, wavelength_nm: float) -> None:
        """Set center wavelength. Override for scanning spectrographs."""
        pass


class Camera(Instrument):
    """Base class for scientific cameras and beam profilers."""

    @abstractmethod
    def acquire_frame(self, exposure_s: float = 0.01) -> Any:
        """Acquire a single frame. Returns 2D numpy array."""
        ...

    @property
    def resolution(self) -> tuple[int, int]:
        """(width, height) in pixels. Override in subclass."""
        return (0, 0)

    @property
    def pixel_size_um(self) -> float:
        """Pixel pitch in micrometers. Override in subclass."""
        return 0.0

    def set_roi(self, x: int, y: int, width: int, height: int) -> None:
        """Set region of interest. Override in subclass."""
        pass

    def set_exposure(self, exposure_s: float) -> None:
        """Set exposure time. Override in subclass."""
        pass

    def set_gain(self, gain: float) -> None:
        """Set camera gain. Override in subclass."""
        pass


class DigitalIO(Instrument):
    """Base class for digital I/O, DAQ, and trigger devices."""

    @abstractmethod
    def read_analog(self, channel: int = 0, n_samples: int = 1, rate: float = 1000.0) -> Any:
        """Read analog input. Returns numpy array of voltage values."""
        ...

    @abstractmethod
    def write_analog(self, channel: int, voltage: float) -> None:
        """Write analog output voltage."""
        ...

    def read_digital(self, channel: int = 0) -> bool:
        """Read digital input state. Override in subclass."""
        return False

    def write_digital(self, channel: int, state: bool) -> None:
        """Write digital output state. Override in subclass."""
        pass

    def configure_trigger(self, source: str = "external", edge: str = "rising") -> None:
        """Configure trigger. Override in subclass."""
        pass
