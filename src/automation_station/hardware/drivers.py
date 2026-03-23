"""
utils/hardware.py
Hardware abstraction layer for knife-edge beam profiler.
Wraps Newport SMC100, Thorlabs KDC101, and Ophir StarBright.
Each class has an `available` flag so the UI can adapt.
"""

import sys
import time
import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# OPHIR STARBRIGHT
# ══════════════════════════════════════════════════════════════════════════════
class OphirStarBright:
    def __init__(self):
        self.available = False
        self._com = None
        self._handle = None

    def connect(self):
        try:
            import win32com.client
            self._com = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")
            self._com.StopAllStreams()
            self._com.CloseAll()
            devices = self._com.ScanUSB()
            if not devices:
                raise RuntimeError("No Ophir USB devices found.")
            self._handle = self._com.OpenUSBDevice(devices[0])
            if not self._com.IsSensorExists(self._handle, 0):
                self._com.CloseAll()
                raise RuntimeError("No sensor attached.")
            self._com.SetRange(self._handle, 0, 0)
            self._com.StartStream(self._handle, 0)
            self.available = True
            return f"Connected (device: {devices[0]})"
        except Exception as e:
            self.available = False
            return f"Failed: {e}"

    def read(self, n_avg=3, delay=0.2):
        if not self.available:
            return float("nan")
        readings = []
        attempts = 0
        while len(readings) < n_avg and attempts < n_avg * 20:
            time.sleep(delay)
            data = self._com.GetData(self._handle, 0)
            if len(data[0]) > 0:
                for val in data[0]:
                    readings.append(float(val))
            attempts += 1
        if not readings:
            return float("nan")
        return float(np.mean(readings[:n_avg]))

    def disconnect(self):
        try:
            if self._com:
                self._com.StopAllStreams()
                self._com.CloseAll()
        except Exception:
            pass
        self._com = None
        self.available = False


# ══════════════════════════════════════════════════════════════════════════════
# NEWPORT SMC100
# ══════════════════════════════════════════════════════════════════════════════
class NewportSMC100:
    def __init__(self):
        self.available = False
        self._smc = None

    def connect(self, port="COM3", axis=1, velocity=2.5):
        self._axis = axis
        self._velocity = velocity
        try:
            import clr
            sys.path.append(
                r"C:\Windows\Microsoft.NET\assembly\GAC_64"
                r"\Newport.SMC100.CommandInterface"
                r"\v4.0_2.0.0.3__d9d722840772240b"
            )
            clr.AddReference(
                r"C:\Windows\Microsoft.NET\assembly\GAC_64"
                r"\Newport.SMC100.CommandInterface"
                r"\v4.0_2.0.0.3__d9d722840772240b"
                r"\Newport.SMC100.CommandInterface.dll"
            )
            from CommandInterfaceSMC100 import SMC100
            self._smc = SMC100()
            self._smc.OpenInstrument(port)

            # Wait for ready
            homed = False
            for attempt in range(60):
                ok, state = self._ts()
                if ok and len(state) >= 2:
                    code = state[:2]
                    if code in ("32", "33", "34"):
                        break
                    elif code in ("0A", "0B") and not homed:
                        self._smc.OR(self._axis)
                        homed = True
                time.sleep(0.5)

            self._smc.VA_Set(self._axis, self._velocity)
            self.available = True
            ok, pos = self._tp()
            return f"Connected (position: {pos:.3f} mm)"
        except Exception as e:
            self.available = False
            return f"Failed: {e}"

    def _ts(self):
        ret = self._smc.TS(self._axis)
        vals = list(ret) if not isinstance(ret, int) else [ret]
        ok = (vals[0] == 0)
        state = ""
        for v in vals[1:]:
            if isinstance(v, str) and len(v) >= 2 and v[:2].isalnum():
                state = v
                break
        return ok, state

    def _tp(self):
        ret = self._smc.TP(self._axis)
        vals = list(ret) if not isinstance(ret, int) else [ret]
        ok = (vals[0] == 0)
        pos = 0.0
        for v in vals[1:]:
            if isinstance(v, float):
                pos = v
                break
        return ok, pos

    def get_position(self):
        if not self.available:
            return 0.0
        ok, pos = self._tp()
        return pos if ok else 0.0

    def move_to(self, position_mm):
        if not self.available:
            return
        ok, current = self._tp()
        self._smc.PA_Set(self._axis, position_mm)
        travel = abs(position_mm - current) if ok else 10.0
        wait = (travel / self._velocity) + 0.5
        time.sleep(wait)

    def disconnect(self):
        try:
            if self._smc:
                self._smc.CloseInstrument()
        except Exception:
            pass
        self._smc = None
        self.available = False


# ══════════════════════════════════════════════════════════════════════════════
# THORLABS KDC101
# ══════════════════════════════════════════════════════════════════════════════
class ThorlabsKDC101:
    def __init__(self):
        self.available = False
        self._device = None

    def connect(self, serial_no="27266790"):
        try:
            import clr
            sys.path.append(r"C:\Program Files\Thorlabs\Kinesis")
            clr.AddReference(r"C:\Program Files\Thorlabs\Kinesis\Thorlabs.MotionControl.DeviceManagerCLI.dll")
            clr.AddReference(r"C:\Program Files\Thorlabs\Kinesis\Thorlabs.MotionControl.GenericMotorCLI.dll")
            clr.AddReference(r"C:\Program Files\Thorlabs\Kinesis\Thorlabs.MotionControl.KCube.DCServoCLI.dll")
            from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
            from Thorlabs.MotionControl.KCube.DCServoCLI import KCubeDCServo

            DeviceManagerCLI.BuildDeviceList()
            self._device = KCubeDCServo.CreateKCubeDCServo(serial_no)
            self._device.Connect(serial_no)
            time.sleep(0.25)
            self._device.StartPolling(250)
            time.sleep(0.25)
            self._device.EnableDevice()
            time.sleep(0.25)
            self._device.LoadMotorConfiguration(serial_no)
            time.sleep(0.25)

            if not self._device.IsActualPositionKnown:
                self._device.Home(60000)

            self.available = True
            return f"Connected (S/N {serial_no}, pos: {self._device.Position} mm)"
        except Exception as e:
            self.available = False
            return f"Failed: {e}"

    def get_position(self):
        if not self.available:
            return 0.0
        return float(str(self._device.Position))

    def move_to(self, position_mm, timeout_ms=20000):
        if not self.available:
            return
        from System import Decimal
        self._device.MoveTo(Decimal(float(position_mm)), timeout_ms)

    def disconnect(self):
        try:
            if self._device:
                self._device.StopPolling()
                self._device.Disconnect(False)
        except Exception:
            pass
        self._device = None
        self.available = False


# ══════════════════════════════════════════════════════════════════════════════
# NEWPORT NSC100  (delegates to newport-nsc100 package)
# ══════════════════════════════════════════════════════════════════════════════
class NewportNSC100:
    """Newport NSC100 motion controller via the newport-nsc100 serial driver.

    This is a thin wrapper that presents the same interface as the other
    hardware classes (available flag, connect/disconnect/move_to/get_position)
    while delegating actual serial communication to the standalone
    newport_nsc100 package.
    """

    def __init__(self):
        self.available = False
        self._ctrl = None

    def connect(self, port="COM4", axis=1, velocity=5.0, use_mock=False):
        try:
            if use_mock:
                from newport_nsc100.mock import MockNSC100
                self._ctrl = MockNSC100(port=port, axis=axis)
            else:
                from newport_nsc100 import NSC100
                self._ctrl = NSC100(port=port, axis=axis)

            result = self._ctrl.connect()
            self._ctrl.velocity = velocity
            self.available = True
            return result
        except Exception as e:
            self.available = False
            return f"Failed: {e}"

    def get_position(self):
        if not self.available or self._ctrl is None:
            return 0.0
        return self._ctrl.position

    def move_to(self, position_mm, timeout=30.0):
        if not self.available or self._ctrl is None:
            return
        self._ctrl.move_absolute(position_mm, timeout=timeout)

    def move_relative(self, displacement_mm, timeout=30.0):
        if not self.available or self._ctrl is None:
            return
        self._ctrl.move_relative(displacement_mm, timeout=timeout)

    def home(self, timeout=60.0):
        if not self.available or self._ctrl is None:
            return
        self._ctrl.home(timeout=timeout)

    @property
    def velocity(self):
        if self._ctrl is None:
            return 0.0
        return self._ctrl.velocity

    @velocity.setter
    def velocity(self, value):
        if self._ctrl is not None:
            self._ctrl.velocity = value

    def disconnect(self):
        try:
            if self._ctrl:
                self._ctrl.disconnect()
        except Exception:
            pass
        self._ctrl = None
        self.available = False
