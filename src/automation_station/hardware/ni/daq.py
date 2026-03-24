"""National Instruments DAQ driver.

Wraps nidaqmx Python API for analog/digital I/O, counter/timer,
and triggered acquisition. Supports USB-6001, USB-6009, PCIe-6361,
and other NI-DAQmx compatible devices.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from ..base import DigitalIO, InstrumentInfo

logger = logging.getLogger(__name__)


class NIDAQ(DigitalIO):
    """NI DAQ device driver.

    Parameters
    ----------
    device_name : NI device identifier (e.g. 'Dev1').
    """

    def __init__(self, device_name: str = "Dev1", mock: bool = False):
        super().__init__(mock=mock)
        self._dev = device_name
        self._nidaqmx = None

    def connect(self, **kwargs) -> str:
        if self._mock:
            self._set_connected(InstrumentInfo("NI", "DAQ", description=f"Mock {self._dev}"))
            return f"Connected (mock {self._dev})"
        try:
            import nidaqmx
            import nidaqmx.system
            self._nidaqmx = nidaqmx
            system = nidaqmx.system.System.local()
            devices = [d.name for d in system.devices]
            if self._dev not in devices:
                raise ConnectionError(
                    f"Device {self._dev} not found. Available: {devices}"
                )
            dev = system.devices[self._dev]
            info = InstrumentInfo(
                vendor="National Instruments",
                model=dev.product_type,
                serial=str(dev.dev_serial_num),
            )
            self._set_connected(info)
            return f"Connected: {info.model} (S/N: {info.serial})"
        except ImportError:
            raise ImportError("nidaqmx required: pip install nidaqmx")

    def disconnect(self) -> None:
        self._nidaqmx = None
        self._set_disconnected()

    def identify(self) -> InstrumentInfo:
        return self._info or InstrumentInfo("NI", "DAQ")

    # ── Analog I/O ───────────────────────────────────────────────

    def read_analog(
        self,
        channel: int = 0,
        n_samples: int = 1,
        rate: float = 1000.0,
        voltage_range: tuple[float, float] = (-10.0, 10.0),
    ) -> Any:
        """Read analog input voltage(s).

        Returns numpy array of shape (n_samples,).
        """
        if self._mock:
            return np.random.normal(0, 0.01, n_samples)
        task = self._nidaqmx.Task()
        try:
            ch_name = f"{self._dev}/ai{channel}"
            task.ai_channels.add_ai_voltage_chan(
                ch_name,
                min_val=voltage_range[0],
                max_val=voltage_range[1],
            )
            if n_samples > 1:
                task.timing.cfg_samp_clk_timing(
                    rate, samps_per_chan=n_samples,
                )
            data = task.read(number_of_samples_per_channel=n_samples)
            return np.array(data)
        finally:
            task.close()

    def write_analog(self, channel: int, voltage: float) -> None:
        """Write analog output voltage."""
        if self._mock:
            return
        task = self._nidaqmx.Task()
        try:
            task.ao_channels.add_ao_voltage_chan(f"{self._dev}/ao{channel}")
            task.write(voltage)
        finally:
            task.close()

    # ── Digital I/O ──────────────────────────────────────────────

    def read_digital(self, channel: int = 0) -> bool:
        if self._mock:
            return False
        task = self._nidaqmx.Task()
        try:
            task.di_channels.add_di_chan(f"{self._dev}/port0/line{channel}")
            return bool(task.read())
        finally:
            task.close()

    def write_digital(self, channel: int, state: bool) -> None:
        if self._mock:
            return
        task = self._nidaqmx.Task()
        try:
            task.do_channels.add_do_chan(f"{self._dev}/port0/line{channel}")
            task.write(state)
        finally:
            task.close()

    # ── Triggered acquisition ────────────────────────────────────

    def read_triggered(
        self,
        channel: int = 0,
        n_samples: int = 1000,
        rate: float = 100000.0,
        trigger_source: str = "PFI0",
        trigger_edge: str = "rising",
        voltage_range: tuple[float, float] = (-10.0, 10.0),
    ) -> np.ndarray:
        """Read analog input with external trigger.

        Waits for trigger on trigger_source, then acquires n_samples
        at the specified rate.
        """
        if self._mock:
            t = np.linspace(0, n_samples / rate, n_samples)
            return np.sin(2 * np.pi * 1000 * t) + np.random.normal(0, 0.01, n_samples)

        edge = (self._nidaqmx.constants.Edge.RISING if trigger_edge == "rising"
                else self._nidaqmx.constants.Edge.FALLING)

        task = self._nidaqmx.Task()
        try:
            task.ai_channels.add_ai_voltage_chan(
                f"{self._dev}/ai{channel}",
                min_val=voltage_range[0],
                max_val=voltage_range[1],
            )
            task.timing.cfg_samp_clk_timing(rate, samps_per_chan=n_samples)
            task.triggers.start_trigger.cfg_dig_edge_start_trig(
                f"/{self._dev}/{trigger_source}", edge,
            )
            data = task.read(number_of_samples_per_channel=n_samples, timeout=30.0)
            return np.array(data)
        finally:
            task.close()

    def configure_trigger(self, source: str = "external", edge: str = "rising") -> None:
        """Configure default trigger settings."""
        logger.info("Trigger configured: source=%s, edge=%s", source, edge)

    # ── Counter/Timer ────────────────────────────────────────────

    def read_counter(self, channel: int = 0, integration_time_s: float = 1.0) -> int:
        """Read edge count over integration time."""
        if self._mock:
            return int(np.random.poisson(10000))
        task = self._nidaqmx.Task()
        try:
            task.ci_channels.add_ci_count_edges_chan(f"{self._dev}/ctr{channel}")
            task.start()
            import time
            time.sleep(integration_time_s)
            count = task.read()
            task.stop()
            return int(count)
        finally:
            task.close()

    def generate_pulse_train(
        self,
        channel: int = 0,
        frequency_hz: float = 1000.0,
        duty_cycle: float = 0.5,
        n_pulses: int = 0,
    ) -> None:
        """Generate a pulse train on counter output.

        n_pulses=0 means continuous until stop.
        """
        if self._mock:
            return
        task = self._nidaqmx.Task()
        try:
            task.co_channels.add_co_pulse_chan_freq(
                f"{self._dev}/ctr{channel}",
                freq=frequency_hz,
                duty_cycle=duty_cycle,
            )
            if n_pulses > 0:
                task.timing.cfg_implicit_timing(
                    sample_mode=self._nidaqmx.constants.AcquisitionType.FINITE,
                    samps_per_chan=n_pulses,
                )
            task.start()
        except Exception:
            task.close()
            raise
