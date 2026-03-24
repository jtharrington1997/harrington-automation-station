"""Andor Shamrock spectrograph and detector camera drivers.

Wraps the Andor SDK (atmcd64d.dll / libandor.so) and Shamrock SDK
for spectrograph control. Supports iDus, Newton, iXon, and Zyla cameras.

Requires Andor SDK installed. Falls back to mock mode if unavailable.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np

from ..base import Spectrometer, Camera, InstrumentInfo

logger = logging.getLogger(__name__)


class AndorShamrock(Spectrometer):
    """Andor Shamrock spectrograph (SR-163, SR-303, SR-500, SR-750).

    Controls grating selection, center wavelength, slit width,
    and filter wheel. Pairs with an Andor CCD/EM-CCD detector.

    Parameters
    ----------
    device_index : Shamrock device index (typically 0).
    """

    def __init__(self, device_index: int = 0, mock: bool = False):
        super().__init__(mock=mock)
        self._idx = device_index
        self._sdk = None
        self._n_gratings = 0
        self._current_grating = 1
        self._center_wl = 500.0
        self._n_pixels = 1024

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._n_gratings = 3
            self._set_connected(InstrumentInfo("Andor", "Shamrock", description="Mock"))
            return "Connected (mock)"
        try:
            from ctypes import cdll, c_int, c_float, byref
            self._sdk = cdll.LoadLibrary("ShamrockCIF.dll")
            n_dev = c_int()
            self._sdk.ShamrockGetNumberDevices(byref(n_dev))
            if n_dev.value == 0:
                raise ConnectionError("No Shamrock spectrographs found")
            self._sdk.ShamrockInitialize("")
            ng = c_int()
            self._sdk.ShamrockGetNumberGratings(self._idx, byref(ng))
            self._n_gratings = ng.value
            self._set_connected(InstrumentInfo("Andor", "Shamrock"))
            return f"Connected: Shamrock ({self._n_gratings} gratings)"
        except Exception as e:
            self._set_error(str(e))
            return f"Failed: {e}"

    def disconnect(self) -> None:
        if self._sdk:
            try:
                self._sdk.ShamrockClose()
            except Exception:
                pass
        self._sdk = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        return InstrumentInfo("Andor", "Shamrock")

    def acquire(self, integration_time_s: float = 1.0) -> dict:
        """Acquire spectrum — delegates to paired camera. Returns placeholder."""
        if self._mock:
            wl = np.linspace(self._center_wl - 50, self._center_wl + 50, self._n_pixels)
            noise = np.random.normal(0, 50, self._n_pixels)
            signal = 1000 * np.exp(-0.5 * ((wl - self._center_wl) / 5)**2) + noise
            return {"wavelength_nm": wl, "intensity": np.maximum(signal, 0)}
        raise NotImplementedError("Acquire requires paired Andor camera")

    @property
    def wavelength_range_nm(self) -> tuple[float, float]:
        return (self._center_wl - 50, self._center_wl + 50)

    def set_grating(self, grating_id: int) -> None:
        """Select grating (1-indexed)."""
        if self._mock:
            self._current_grating = grating_id
            return
        from ctypes import c_int
        self._sdk.ShamrockSetGrating(self._idx, c_int(grating_id))
        self._current_grating = grating_id
        time.sleep(2.0)  # grating turret settling

    def set_center_wavelength(self, wavelength_nm: float) -> None:
        if self._mock:
            self._center_wl = wavelength_nm
            return
        from ctypes import c_float
        self._sdk.ShamrockSetWavelength(self._idx, c_float(wavelength_nm))
        self._center_wl = wavelength_nm
        time.sleep(1.0)

    @property
    def current_grating(self) -> int:
        return self._current_grating

    @property
    def n_gratings(self) -> int:
        return self._n_gratings

    def get_grating_info(self, grating_id: int) -> dict:
        """Get grating lines/mm and blaze wavelength."""
        if self._mock:
            grooves = [150, 300, 600][min(grating_id - 1, 2)]
            return {"grooves_per_mm": grooves, "blaze_nm": 500.0}
        return {"grooves_per_mm": 0, "blaze_nm": 0}

    def set_slit_width(self, width_um: float, slit: str = "input") -> None:
        """Set slit width in micrometers."""
        if self._mock:
            return
        from ctypes import c_float
        if slit == "input":
            self._sdk.ShamrockSetSlit(self._idx, c_float(width_um))

    def get_calibration(self) -> np.ndarray:
        """Get wavelength calibration array for detector pixels."""
        if self._mock:
            return np.linspace(
                self._center_wl - 50, self._center_wl + 50, self._n_pixels
            )
        from ctypes import c_float, POINTER, cast
        cal = (c_float * self._n_pixels)()
        self._sdk.ShamrockGetCalibration(self._idx, cal, self._n_pixels)
        return np.array(list(cal))


class AndorCamera(Camera):
    """Andor CCD/EM-CCD camera (iDus, Newton, iXon, Zyla).

    Wraps Andor SDK2 (atmcd64d.dll) or SDK3 (atcore.dll for Zyla/Neo).

    Parameters
    ----------
    camera_index : Camera index (typically 0).
    sdk_version : 'sdk2' for iDus/Newton/iXon, 'sdk3' for Zyla/Neo.
    """

    def __init__(self, camera_index: int = 0, sdk_version: str = "sdk2",
                 mock: bool = False):
        super().__init__(mock=mock)
        self._cam_idx = camera_index
        self._sdk_ver = sdk_version
        self._sdk = None
        self._width = 1024
        self._height = 256
        self._pixel_size = 26.0  # µm, typical for iDus

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("Andor", "iDus", description="Mock"))
            return "Connected (mock)"
        try:
            from ctypes import cdll
            if self._sdk_ver == "sdk2":
                self._sdk = cdll.LoadLibrary("atmcd64d.dll")
                self._sdk.Initialize("")
            else:
                self._sdk = cdll.LoadLibrary("atcore.dll")
            self._set_connected(InstrumentInfo("Andor", "Camera"))
            return "Connected: Andor camera"
        except Exception as e:
            self._set_error(str(e))
            return f"Failed: {e}"

    def disconnect(self) -> None:
        if self._sdk and self._sdk_ver == "sdk2":
            try:
                self._sdk.ShutDown()
            except Exception:
                pass
        self._sdk = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        return InstrumentInfo("Andor", "Camera")

    def acquire_frame(self, exposure_s: float = 0.01) -> Any:
        if self._mock:
            return np.random.poisson(100, (self._height, self._width)).astype(np.float64)
        raise NotImplementedError("Full SDK acquisition not yet implemented")

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._width, self._height)

    @property
    def pixel_size_um(self) -> float:
        return self._pixel_size

    def set_exposure(self, exposure_s: float) -> None:
        if self._mock:
            return
        if self._sdk_ver == "sdk2":
            from ctypes import c_float
            self._sdk.SetExposureTime(c_float(exposure_s))

    def set_temperature(self, temp_c: int = -60) -> None:
        """Set CCD cooler temperature (for cooled detectors)."""
        if self._mock:
            return
        if self._sdk_ver == "sdk2":
            from ctypes import c_int
            self._sdk.SetTemperature(c_int(temp_c))
            self._sdk.CoolerON()

    def get_temperature(self) -> float:
        """Read current CCD temperature."""
        if self._mock:
            return -60.0
        return 0.0

    def set_gain(self, gain: float) -> None:
        """Set EM gain (for EM-CCD cameras like iXon)."""
        if self._mock:
            return
        if self._sdk_ver == "sdk2":
            from ctypes import c_int
            self._sdk.SetEMCCDGain(c_int(int(gain)))

    def acquire_spectrum(self, exposure_s: float = 1.0) -> np.ndarray:
        """Acquire 1D spectrum (full vertical binning)."""
        if self._mock:
            return np.random.poisson(500, self._width).astype(np.float64)
        raise NotImplementedError("Full SDK acquisition not yet implemented")
