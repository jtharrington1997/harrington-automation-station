"""Light Conversion laser control drivers.

Pharos femtosecond laser and Orpheus OPA control via TCP/IP.
The Pharos uses a custom TCP protocol on port 12345 (configurable).
The Orpheus pairs with the Pharos as its pump source.

These drivers implement the base LaserController interface.
"""
from __future__ import annotations

import json
import logging
import socket
import time
from typing import Any, Optional

from ..base import LaserController, InstrumentInfo

logger = logging.getLogger(__name__)


class LCPharos(LaserController):
    """Light Conversion Pharos femtosecond laser controller.

    Parameters
    ----------
    host : IP address of the Pharos controller.
    port : TCP port (default 12345).
    """

    def __init__(self, host: str = "192.168.1.100", port: int = 12345,
                 mock: bool = False):
        super().__init__(mock=mock)
        self._host = host
        self._port = port
        self._sock: Optional[socket.socket] = None
        self._emitting = False
        self._power = 0.0
        self._rep_rate = 10000.0
        self._pulse_energy = 2e-3
        self._wavelength = 1030.0
        self._burst_mode = False
        self._burst_count = 1
        self._bi_burst = False

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo(
                "Light Conversion", "Pharos", description="Mock — 2 mJ, 1030 nm"
            ))
            return "Connected (mock)"
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((self._host, self._port))
            info = self.identify()
            self._set_connected(info)
            # Read initial state
            self._update_status()
            return f"Connected: {info.model} (S/N: {info.serial})"
        except Exception as e:
            self._set_error(str(e))
            return f"Failed: {e}"

    def disconnect(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        if self._mock:
            return InstrumentInfo("Light Conversion", "Pharos", "MOCK-PH2000",
                                  firmware="1.0", description="Yb:KGW, 1030 nm, 2 mJ")
        resp = self._send_cmd("GET_INFO")
        return InstrumentInfo(
            vendor="Light Conversion",
            model=resp.get("model", "Pharos"),
            serial=resp.get("serial", ""),
            firmware=resp.get("firmware", ""),
        )

    def _send_cmd(self, cmd: str, params: dict | None = None) -> dict:
        """Send TCP command and parse JSON response."""
        if self._mock:
            return {}
        msg = json.dumps({"command": cmd, **(params or {})}) + "\n"
        self._sock.sendall(msg.encode("utf-8"))
        data = self._sock.recv(4096).decode("utf-8")
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {"raw": data}

    def _update_status(self) -> None:
        """Refresh cached status from laser."""
        if self._mock:
            return
        status = self._send_cmd("GET_STATUS")
        self._emitting = status.get("emission", False)
        self._power = status.get("power_w", 0.0)
        self._rep_rate = status.get("rep_rate_hz", 10000.0)
        self._pulse_energy = status.get("pulse_energy_j", 2e-3)

    # ── Emission control ─────────────────────────────────────────

    def set_emission(self, on: bool) -> None:
        if self._mock:
            self._emitting = on
            return
        self._send_cmd("SET_EMISSION", {"state": on})
        time.sleep(0.5)
        self._emitting = on

    @property
    def is_emitting(self) -> bool:
        return self._emitting

    # ── Power and energy ─────────────────────────────────────────

    @property
    def power_w(self) -> float:
        return self._power

    @power_w.setter
    def power_w(self, value: float) -> None:
        if self._mock:
            self._power = value
            self._pulse_energy = value / self._rep_rate if self._rep_rate > 0 else 0
            return
        self._send_cmd("SET_POWER", {"power_w": value})
        self._power = value

    @property
    def wavelength_nm(self) -> float:
        return self._wavelength

    @property
    def rep_rate_hz(self) -> float:
        return self._rep_rate

    @rep_rate_hz.setter
    def rep_rate_hz(self, value: float) -> None:
        if self._mock:
            self._rep_rate = value
            return
        self._send_cmd("SET_REP_RATE", {"rep_rate_hz": value})
        self._rep_rate = value

    @property
    def pulse_energy_j(self) -> float:
        return self._pulse_energy

    @pulse_energy_j.setter
    def pulse_energy_j(self, value: float) -> None:
        if self._mock:
            self._pulse_energy = value
            self._power = value * self._rep_rate
            return
        self._send_cmd("SET_PULSE_ENERGY", {"energy_j": value})
        self._pulse_energy = value

    # ── Burst mode ───────────────────────────────────────────────

    @property
    def burst_mode(self) -> bool:
        return self._burst_mode

    def set_burst_mode(self, enabled: bool, n_pulses: int = 5) -> None:
        """Enable/disable burst mode with N pulses per burst."""
        self._burst_mode = enabled
        self._burst_count = n_pulses
        if not self._mock:
            self._send_cmd("SET_BURST", {"enabled": enabled, "n_pulses": n_pulses})

    @property
    def bi_burst_mode(self) -> bool:
        return self._bi_burst

    def set_bi_burst_mode(self, enabled: bool, outer: int = 3, inner: int = 5) -> None:
        """Enable bi-burst (burst of bursts) mode."""
        self._bi_burst = enabled
        if not self._mock:
            self._send_cmd("SET_BI_BURST", {
                "enabled": enabled, "outer": outer, "inner": inner
            })

    # ── Harmonics ────────────────────────────────────────────────

    def set_harmonic(self, harmonic: int) -> None:
        """Select harmonic output (1=fundamental, 2=SHG, 3=THG, 4=FHG, 5=5HG).

        Available harmonics depend on installed modules.
        """
        wl_map = {1: 1030.0, 2: 515.0, 3: 343.0, 4: 257.5, 5: 206.0}
        if harmonic in wl_map:
            self._wavelength = wl_map[harmonic]
        if not self._mock:
            self._send_cmd("SET_HARMONIC", {"harmonic": harmonic})

    def get_status(self) -> dict[str, Any]:
        self._update_status()
        return {
            "emitting": self._emitting,
            "power_w": self._power,
            "wavelength_nm": self._wavelength,
            "rep_rate_hz": self._rep_rate,
            "pulse_energy_j": self._pulse_energy,
            "burst_mode": self._burst_mode,
            "burst_count": self._burst_count,
            "bi_burst": self._bi_burst,
        }


class LCOrpheus(LaserController):
    """Light Conversion Orpheus OPA controller.

    Paired with Pharos as pump source. Controls wavelength tuning
    across the OPA signal and idler range (630 nm – 16 µm).

    Parameters
    ----------
    host : IP address of the Orpheus controller.
    port : TCP port (default 12346).
    pump : Associated LCPharos instance.
    """

    def __init__(self, host: str = "192.168.1.101", port: int = 12346,
                 pump: LCPharos | None = None, mock: bool = False):
        super().__init__(mock=mock)
        self._host = host
        self._port = port
        self._pump = pump
        self._sock: Optional[socket.socket] = None
        self._emitting = False
        self._wavelength = 8500.0  # default mid-IR
        self._output = "idler"

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo(
                "Light Conversion", "Orpheus",
                description="Mock — tunable 630 nm – 16 µm"
            ))
            return "Connected (mock)"
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((self._host, self._port))
            info = self.identify()
            self._set_connected(info)
            return f"Connected: {info.model}"
        except Exception as e:
            self._set_error(str(e))
            return f"Failed: {e}"

    def disconnect(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        return InstrumentInfo("Light Conversion", "Orpheus",
                              description="Tunable OPA, 630 nm – 16 µm")

    def _send_cmd(self, cmd: str, params: dict | None = None) -> dict:
        if self._mock:
            return {}
        msg = json.dumps({"command": cmd, **(params or {})}) + "\n"
        self._sock.sendall(msg.encode("utf-8"))
        data = self._sock.recv(4096).decode("utf-8")
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {"raw": data}

    def set_emission(self, on: bool) -> None:
        self._emitting = on
        if not self._mock:
            self._send_cmd("SET_EMISSION", {"state": on})

    @property
    def is_emitting(self) -> bool:
        return self._emitting

    @property
    def wavelength_nm(self) -> float:
        return self._wavelength

    @wavelength_nm.setter
    def wavelength_nm(self, value: float) -> None:
        """Tune OPA to target wavelength (nm)."""
        if value < 630 or value > 16000:
            raise ValueError(f"Wavelength {value} nm outside Orpheus range (630–16000 nm)")
        self._wavelength = value
        # Determine signal vs idler
        self._output = "signal" if value < 2600 else "idler"
        if not self._mock:
            self._send_cmd("SET_WAVELENGTH", {"wavelength_nm": value})
            time.sleep(2.0)  # OPA tuning time

    @property
    def output_type(self) -> str:
        """Current output: 'signal', 'idler', or 'sum_frequency'."""
        return self._output

    @property
    def tuning_range_nm(self) -> tuple[float, float]:
        return (630.0, 16000.0)

    @property
    def pump_status(self) -> dict | None:
        """Query paired Pharos pump status."""
        if self._pump:
            return self._pump.get_status()
        return None

    def get_status(self) -> dict[str, Any]:
        return {
            "emitting": self._emitting,
            "wavelength_nm": self._wavelength,
            "output": self._output,
            "tuning_range_nm": self.tuning_range_nm,
            "pump_connected": self._pump.available if self._pump else False,
        }


class CoherentOpera(LaserController):
    """Coherent Opera OPA controller.

    Paired with a Coherent Astrella Ti:Sapphire amplifier as pump.
    Tunable across UV–MIR via signal, idler, and nonlinear mixing
    stages (DFG, SFG, SHG of signal/idler).

    Typical tuning range: 240 nm – 20 µm depending on installed
    mixing modules. Uses serial RS-232 communication.

    Parameters
    ----------
    port : Serial port for Opera control.
    pump : Associated Coherent Astrella instance (optional).
    """

    def __init__(self, port: str = "COM10", pump: "CoherentAstrella | None" = None,
                 baudrate: int = 19200, mock: bool = False):
        super().__init__(mock=mock)
        self._port = port
        self._pump = pump
        self._baudrate = baudrate
        self._sock = None
        self._ser = None
        self._emitting = False
        self._wavelength = 800.0
        self._output = "signal"
        self._modules = ["signal", "idler", "SHG-S", "SHG-I", "SFG", "DFG"]

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo(
                "Coherent", "Opera-F/Solo",
                description="Mock — tunable OPA, Astrella-pumped"
            ))
            return "Connected (mock)"
        try:
            import serial as _serial
            self._ser = _serial.Serial(self._port, self._baudrate, timeout=2.0)
            self._ser.reset_input_buffer()
            info = self.identify()
            self._set_connected(info)
            return f"Connected: {info.model}"
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
            return InstrumentInfo("Coherent", "Opera-F/Solo", "MOCK-OPERA",
                                  description="OPA pumped by Astrella, 240 nm – 20 µm")
        resp = self._query("*IDN?")
        return InstrumentInfo(vendor="Coherent", model="Opera", firmware=resp)

    def _send(self, cmd: str) -> None:
        if self._mock or self._ser is None:
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
            self._send(f"SHUTTER {'OPEN' if on else 'CLOSE'}")

    @property
    def is_emitting(self) -> bool:
        return self._emitting

    @property
    def wavelength_nm(self) -> float:
        return self._wavelength

    @wavelength_nm.setter
    def wavelength_nm(self, value: float) -> None:
        """Tune OPA to target wavelength.

        The Opera automatically selects the appropriate output stage
        (signal, idler, SHG, SFG, DFG) based on the requested wavelength.
        """
        self._wavelength = value
        # Determine output stage
        if 1140 <= value <= 1600:
            self._output = "signal"
        elif 1600 < value <= 2600:
            self._output = "idler"
        elif 570 <= value < 800:
            self._output = "SHG-S"
        elif 800 <= value < 1140:
            self._output = "SHG-I"
        elif 240 <= value < 570:
            self._output = "SFG"
        elif value > 2600:
            self._output = "DFG"
        else:
            self._output = "signal"

        if not self._mock:
            self._send(f"WAVELENGTH {value:.1f}")
            import time
            time.sleep(3.0)  # OPA tuning + crystal rotation

    @property
    def output_type(self) -> str:
        """Current output stage."""
        return self._output

    @property
    def available_modules(self) -> list[str]:
        """Installed mixing modules."""
        return list(self._modules)

    @property
    def tuning_range_nm(self) -> tuple[float, float]:
        """Full tuning range across all modules."""
        return (240.0, 20000.0)

    @property
    def signal_range_nm(self) -> tuple[float, float]:
        return (1140.0, 1600.0)

    @property
    def idler_range_nm(self) -> tuple[float, float]:
        return (1600.0, 2600.0)

    @property
    def pump_wavelength_nm(self) -> float:
        """Astrella pump wavelength (fixed at 800 nm)."""
        return 800.0

    @property
    def pump_status(self) -> dict | None:
        if self._pump:
            return self._pump.get_status()
        return None

    def get_status(self) -> dict:
        return {
            "emitting": self._emitting,
            "wavelength_nm": self._wavelength,
            "output": self._output,
            "tuning_range_nm": self.tuning_range_nm,
            "modules": self._modules,
            "pump_connected": self._pump.available if self._pump else False,
            "pump_wavelength_nm": self.pump_wavelength_nm,
        }
