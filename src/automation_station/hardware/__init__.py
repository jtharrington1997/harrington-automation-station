"""Harrington Automation Station — hardware abstraction layer.

Provides unified drivers for all common laser laboratory instruments:

Vendors: Newport, Thorlabs, Ophir, Andor, Light Conversion, Coherent,
         Spectra-Physics, National Instruments, DataRay, Galil, Lantronix,
         Ocean Insight, Hamamatsu, Gentec-EO, Stanford Research, Keysight

Categories: Motion controllers, detectors (power/energy), lasers,
            spectrometers, cameras, DAQ/digital I/O

Usage:
    from automation_station.hardware.base import MotionController, Detector
    from automation_station.hardware.registry import get_registry, auto_detect_devices
    from automation_station.hardware.newport.esp301 import NewportESP301
    from automation_station.hardware.thorlabs.pm100 import ThorlabsPM100
    from automation_station.hardware.andor.instruments import AndorShamrock
    from automation_station.hardware.light_conversion.lasers import LCPharos
    from automation_station.hardware.ni.daq import NIDAQ
"""
from __future__ import annotations

from .base import (
    Instrument, MotionController, Detector, LaserController,
    Spectrometer, Camera, DigitalIO,
    ConnectionState, InstrumentInfo,
)
from .registry import (
    get_registry, get_drivers_by_category, get_drivers_by_vendor,
    list_serial_ports, auto_detect_devices, scan_usb_devices,
)
