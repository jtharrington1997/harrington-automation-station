"""Device registry, auto-discovery, and COM port scanning.

Provides a central registry of all known instrument drivers and
methods to detect connected hardware automatically. Works on both
Windows (COM ports) and Linux (/dev/ttyUSB, /dev/ttyACM).

No Streamlit imports.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Type

from .base import Instrument, InstrumentInfo

logger = logging.getLogger(__name__)


@dataclass
class DeviceEntry:
    """A registered device type with its driver class and detection info."""
    driver_class: Type[Instrument]
    vendor: str
    model: str
    category: str  # "motion", "detector", "laser", "spectrometer", "camera", "dio"
    protocol: str  # "serial", "usb", "tcp", "dotnet", "sdk"
    default_baud: int = 9600
    usb_vid_pid: tuple[int, int] | None = None  # USB vendor/product ID for auto-detect
    id_query: str | None = None  # command to send for identification
    id_response_contains: str | None = None  # substring to match in response
    description: str = ""


# Global driver registry
_REGISTRY: dict[str, DeviceEntry] = {}


def register_driver(key: str, entry: DeviceEntry) -> None:
    """Register a device driver in the global registry."""
    _REGISTRY[key] = entry
    logger.debug("Registered driver: %s (%s %s)", key, entry.vendor, entry.model)


def get_registry() -> dict[str, DeviceEntry]:
    """Return the full driver registry."""
    return dict(_REGISTRY)


def get_drivers_by_category(category: str) -> dict[str, DeviceEntry]:
    """Return drivers filtered by category."""
    return {k: v for k, v in _REGISTRY.items() if v.category == category}


def get_drivers_by_vendor(vendor: str) -> dict[str, DeviceEntry]:
    """Return drivers filtered by vendor name (case-insensitive)."""
    vendor_lower = vendor.lower()
    return {k: v for k, v in _REGISTRY.items() if v.vendor.lower() == vendor_lower}


def list_serial_ports() -> list[dict[str, str]]:
    """Enumerate available serial ports with descriptions.

    Returns list of dicts with keys: port, description, hwid.
    Works on Windows, Linux, and macOS.
    """
    try:
        from serial.tools import list_ports
        return [
            {
                "port": p.device,
                "description": p.description or "",
                "hwid": p.hwid or "",
                "vid": f"0x{p.vid:04X}" if p.vid else "",
                "pid": f"0x{p.pid:04X}" if p.pid else "",
                "serial_number": p.serial_number or "",
                "manufacturer": p.manufacturer or "",
            }
            for p in list_ports.comports()
        ]
    except ImportError:
        logger.warning("pyserial not installed — cannot enumerate ports")
        return []


def auto_detect_devices(
    ports: list[str] | None = None,
    timeout: float = 2.0,
) -> list[dict]:
    """Attempt to identify instruments on serial ports.

    For each port, tries known ID queries from the registry.
    Returns list of dicts: {port, driver_key, vendor, model, response}.
    """
    if ports is None:
        port_info = list_serial_ports()
        ports = [p["port"] for p in port_info]

    detected = []
    serial_drivers = {
        k: v for k, v in _REGISTRY.items()
        if v.protocol == "serial" and v.id_query
    }

    try:
        import serial
    except ImportError:
        logger.warning("pyserial not installed — cannot auto-detect")
        return []

    for port in ports:
        for key, entry in serial_drivers.items():
            try:
                with serial.Serial(port, entry.default_baud, timeout=timeout) as ser:
                    ser.reset_input_buffer()
                    cmd = f"1{entry.id_query}\r\n" if entry.id_query else ""
                    ser.write(cmd.encode("ascii"))
                    ser.flush()
                    response = ser.readline().decode("ascii", errors="replace").strip()

                    if entry.id_response_contains and entry.id_response_contains in response:
                        detected.append({
                            "port": port,
                            "driver_key": key,
                            "vendor": entry.vendor,
                            "model": entry.model,
                            "response": response,
                        })
                        logger.info("Detected %s %s on %s", entry.vendor, entry.model, port)
                        break  # port claimed by this device
            except Exception:
                continue

    return detected


def scan_usb_devices() -> list[dict]:
    """Scan for USB devices matching known VID/PID pairs.

    Returns list of dicts: {driver_key, vendor, model, vid, pid, port}.
    """
    port_info = list_serial_ports()
    usb_drivers = {
        k: v for k, v in _REGISTRY.items()
        if v.usb_vid_pid is not None
    }

    found = []
    for p in port_info:
        vid_str = p.get("vid", "")
        pid_str = p.get("pid", "")
        if not vid_str or not pid_str:
            continue
        try:
            vid = int(vid_str, 16)
            pid = int(pid_str, 16)
        except ValueError:
            continue

        for key, entry in usb_drivers.items():
            if entry.usb_vid_pid == (vid, pid):
                found.append({
                    "driver_key": key,
                    "vendor": entry.vendor,
                    "model": entry.model,
                    "vid": vid_str,
                    "pid": pid_str,
                    "port": p["port"],
                })
    return found


# ── Auto-register all built-in drivers on import ──────────────────

def _register_builtin_drivers():
    """Register all known instrument drivers."""

    # Newport motion controllers
    register_driver("newport_smc100", DeviceEntry(
        driver_class=Instrument,  # placeholder — real class loaded lazily
        vendor="Newport", model="SMC100",
        category="motion", protocol="dotnet",
        default_baud=57600,
        id_query="VE", id_response_contains="SMC",
        description="Single-axis DC servo controller (.NET SDK)",
    ))
    register_driver("newport_nsc100", DeviceEntry(
        driver_class=Instrument,
        vendor="Newport", model="NSC100",
        category="motion", protocol="serial",
        default_baud=57600,
        id_query="VE", id_response_contains="NSC",
        description="Single-axis stepper controller (serial RS-232)",
    ))
    register_driver("newport_esp301", DeviceEntry(
        driver_class=Instrument,
        vendor="Newport", model="ESP301",
        category="motion", protocol="serial",
        default_baud=921600,
        id_query="VE", id_response_contains="ESP",
        description="Multi-axis motion controller (up to 3 axes, serial/GPIB)",
    ))
    register_driver("newport_conex_cc", DeviceEntry(
        driver_class=Instrument,
        vendor="Newport", model="CONEX-CC",
        category="motion", protocol="serial",
        default_baud=921600,
        id_query="VE", id_response_contains="CONEX",
        description="Compact piezo controller (serial USB)",
    ))
    register_driver("newport_conex_ag", DeviceEntry(
        driver_class=Instrument,
        vendor="Newport", model="CONEX-AG",
        category="motion", protocol="serial",
        default_baud=921600,
        id_query="VE", id_response_contains="AG",
        description="Agilis piezo positioner controller",
    ))

    # Thorlabs motion controllers
    register_driver("thorlabs_kdc101", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="KDC101",
        category="motion", protocol="dotnet",
        usb_vid_pid=(0x0403, 0xFAF0),
        description="K-Cube DC servo motor controller (Kinesis .NET SDK)",
    ))
    register_driver("thorlabs_bsc201", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="BSC201",
        category="motion", protocol="dotnet",
        description="2-channel benchtop stepper controller (Kinesis .NET SDK)",
    ))
    register_driver("thorlabs_bsc203", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="BSC203",
        category="motion", protocol="dotnet",
        description="3-channel benchtop stepper controller (Kinesis .NET SDK)",
    ))
    register_driver("thorlabs_bbd201", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="BBD201",
        category="motion", protocol="dotnet",
        description="Brushless DC controller (Kinesis .NET SDK)",
    ))
    register_driver("thorlabs_mff101", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="MFF101",
        category="motion", protocol="dotnet",
        description="Motorized flip mount (Kinesis .NET SDK)",
    ))
    register_driver("thorlabs_fw102c", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="FW102C",
        category="motion", protocol="serial",
        default_baud=115200,
        id_query="*idn?", id_response_contains="FW102",
        description="6-position motorized filter wheel (serial)",
    ))
    register_driver("thorlabs_sc10", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="SC10",
        category="motion", protocol="serial",
        default_baud=9600,
        description="Optical beam shutter controller (serial)",
    ))
    register_driver("thorlabs_ell14", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="ELL14",
        category="motion", protocol="serial",
        default_baud=9600,
        description="Elliptec rotation mount (serial)",
    ))

    # Thorlabs detectors
    register_driver("thorlabs_pm100d", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="PM100D",
        category="detector", protocol="usb",
        usb_vid_pid=(0x1313, 0x8078),
        description="Optical power and energy meter (USB, VISA/SCPI)",
    ))
    register_driver("thorlabs_pm400", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="PM400",
        category="detector", protocol="usb",
        description="Touch-screen optical power meter (USB, VISA/SCPI)",
    ))

    # Thorlabs cameras
    register_driver("thorlabs_zelux", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="Zelux",
        category="camera", protocol="sdk",
        description="Zelux 1.6MP CMOS camera (ThorCam SDK)",
    ))
    register_driver("thorlabs_kiralux", DeviceEntry(
        driver_class=Instrument,
        vendor="Thorlabs", model="Kiralux",
        category="camera", protocol="sdk",
        description="Kiralux CMOS camera (ThorCam SDK)",
    ))

    # Ophir detectors
    register_driver("ophir_starbright", DeviceEntry(
        driver_class=Instrument,
        vendor="Ophir", model="StarBright",
        category="detector", protocol="dotnet",
        description="Laser power/energy meter (COM/OLE automation)",
    ))
    register_driver("ophir_juno", DeviceEntry(
        driver_class=Instrument,
        vendor="Ophir", model="Juno",
        category="detector", protocol="usb",
        description="USB laser power meter interface",
    ))
    register_driver("ophir_beamgage", DeviceEntry(
        driver_class=Instrument,
        vendor="Ophir", model="BeamGage",
        category="camera", protocol="sdk",
        description="Camera-based beam profiler (BeamGage SDK)",
    ))

    # Andor spectrometers and cameras
    register_driver("andor_shamrock", DeviceEntry(
        driver_class=Instrument,
        vendor="Andor", model="Shamrock",
        category="spectrometer", protocol="sdk",
        description="Shamrock spectrograph (Andor SDK / Solis)",
    ))
    register_driver("andor_idus", DeviceEntry(
        driver_class=Instrument,
        vendor="Andor", model="iDus",
        category="camera", protocol="sdk",
        description="iDus InGaAs/CCD detector array (Andor SDK)",
    ))
    register_driver("andor_newton", DeviceEntry(
        driver_class=Instrument,
        vendor="Andor", model="Newton",
        category="camera", protocol="sdk",
        description="Newton EM-CCD spectroscopy camera (Andor SDK)",
    ))
    register_driver("andor_ixon", DeviceEntry(
        driver_class=Instrument,
        vendor="Andor", model="iXon",
        category="camera", protocol="sdk",
        description="iXon Ultra EM-CCD camera (Andor SDK)",
    ))
    register_driver("andor_zyla", DeviceEntry(
        driver_class=Instrument,
        vendor="Andor", model="Zyla",
        category="camera", protocol="sdk",
        description="Zyla sCMOS camera (Andor SDK3)",
    ))

    # Light Conversion lasers
    register_driver("lc_pharos", DeviceEntry(
        driver_class=Instrument,
        vendor="Light Conversion", model="Pharos",
        category="laser", protocol="tcp",
        description="Pharos femtosecond laser (TCP/IP control + serial status)",
    ))
    register_driver("lc_orpheus", DeviceEntry(
        driver_class=Instrument,
        vendor="Light Conversion", model="Orpheus",
        category="laser", protocol="tcp",
        description="Orpheus OPA (TCP/IP control, paired with Pharos pump)",
    ))
    register_driver("lc_carbide", DeviceEntry(
        driver_class=Instrument,
        vendor="Light Conversion", model="Carbide",
        category="laser", protocol="tcp",
        description="Carbide industrial femtosecond laser (TCP/IP)",
    ))

    # Coherent lasers
    register_driver("coherent_astrella", DeviceEntry(
        driver_class=Instrument,
        vendor="Coherent", model="Astrella",
        category="laser", protocol="serial",
        default_baud=19200,
        description="Astrella one-box Ti:Sapphire amplifier (serial RS-232)",
    ))
    register_driver("coherent_opera", DeviceEntry(
        driver_class=Instrument,
        vendor="Coherent", model="Opera-F/Solo",
        category="laser", protocol="serial",
        default_baud=19200,
        description="Opera OPA (pumped by Astrella Ti:Sapphire, 240 nm – 20 µm)",
    ))
    register_driver("coherent_chameleon", DeviceEntry(
        driver_class=Instrument,
        vendor="Coherent", model="Chameleon",
        category="laser", protocol="serial",
        default_baud=19200,
        description="Chameleon tunable Ti:Sapphire oscillator (serial)",
    ))
    register_driver("coherent_obis", DeviceEntry(
        driver_class=Instrument,
        vendor="Coherent", model="OBIS",
        category="laser", protocol="serial",
        default_baud=115200,
        id_query="?SYSTem:INFormation:MODel?",
        id_response_contains="OBIS",
        description="OBIS CW diode laser (serial SCPI)",
    ))
    register_driver("coherent_genesis", DeviceEntry(
        driver_class=Instrument,
        vendor="Coherent", model="Genesis",
        category="laser", protocol="serial",
        default_baud=19200,
        description="Genesis CW OPSL laser (serial)",
    ))

    # Spectra-Physics lasers
    register_driver("sp_mai_tai", DeviceEntry(
        driver_class=Instrument,
        vendor="Spectra-Physics", model="Mai Tai",
        category="laser", protocol="serial",
        default_baud=9600,
        description="Mai Tai tunable Ti:Sapphire oscillator (serial)",
    ))
    register_driver("sp_spirit", DeviceEntry(
        driver_class=Instrument,
        vendor="Spectra-Physics", model="Spirit",
        category="laser", protocol="tcp",
        description="Spirit industrial femtosecond laser (TCP/IP)",
    ))

    # NI DAQ
    register_driver("ni_daq", DeviceEntry(
        driver_class=Instrument,
        vendor="National Instruments", model="DAQ",
        category="dio", protocol="sdk",
        description="NI DAQ (nidaqmx Python API — USB-6001/6009/6361 etc.)",
    ))

    # Beam diagnostics
    register_driver("dataray_profiler", DeviceEntry(
        driver_class=Instrument,
        vendor="DataRay", model="Beam Profiler",
        category="camera", protocol="sdk",
        description="DataRay camera-based beam profiler (DataRay SDK)",
    ))

    # Galil motion
    register_driver("galil_dmc", DeviceEntry(
        driver_class=Instrument,
        vendor="Galil", model="DMC",
        category="motion", protocol="tcp",
        description="Galil DMC multi-axis motion controller (TCP/IP + serial)",
    ))

    # Lantronix serial bridges
    register_driver("lantronix_xport", DeviceEntry(
        driver_class=Instrument,
        vendor="Lantronix", model="XPort",
        category="dio", protocol="tcp",
        description="Serial-to-Ethernet bridge (TCP socket → RS-232)",
    ))

    # Ocean Insight (formerly Ocean Optics) spectrometers
    register_driver("ocean_usb", DeviceEntry(
        driver_class=Instrument,
        vendor="Ocean Insight", model="USB Spectrometer",
        category="spectrometer", protocol="usb",
        description="USB2000+/USB4000/Flame/HR series (OceanDirect/seabreeze)",
    ))

    # Hamamatsu detectors
    register_driver("hamamatsu_c_series", DeviceEntry(
        driver_class=Instrument,
        vendor="Hamamatsu", model="C-Series",
        category="camera", protocol="sdk",
        description="Hamamatsu ORCA/C-series scientific cameras (DCAM SDK)",
    ))

    # Gentec-EO energy meters
    register_driver("gentec_maestro", DeviceEntry(
        driver_class=Instrument,
        vendor="Gentec-EO", model="Maestro",
        category="detector", protocol="usb",
        description="Maestro touchscreen laser energy/power meter (USB)",
    ))

    # SRS lock-in amplifiers
    register_driver("srs_sr830", DeviceEntry(
        driver_class=Instrument,
        vendor="Stanford Research", model="SR830",
        category="detector", protocol="serial",
        default_baud=19200,
        id_query="*IDN?", id_response_contains="SR830",
        description="SR830 DSP lock-in amplifier (serial/GPIB SCPI)",
    ))

    # Keysight / Agilent oscilloscopes and function generators
    register_driver("keysight_scope", DeviceEntry(
        driver_class=Instrument,
        vendor="Keysight", model="Oscilloscope",
        category="dio", protocol="usb",
        description="InfiniiVision/Infiniium oscilloscope (VISA/SCPI)",
    ))
    register_driver("keysight_funcgen", DeviceEntry(
        driver_class=Instrument,
        vendor="Keysight", model="Function Generator",
        category="dio", protocol="usb",
        description="33500B/33600A waveform generator (VISA/SCPI)",
    ))

    logger.debug("Registered %d drivers total", len(_REGISTRY))


# Auto-register on import
_register_builtin_drivers()
