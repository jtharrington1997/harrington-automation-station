"""
knife_edge_zscan.py
Z-scan knife-edge beam profiling with selectable automation level:

  Mode 1 — FULL AUTO
    SMC100 moves Z, KDC101 sweeps knife edge, Ophir reads power.
    Hands-free after pressing Enter.

  Mode 2 — SEMI AUTO
    SMC100 moves Z automatically, Ophir reads power automatically.
    User manually positions knife edge and presses Enter to record.
    (No KDC101 / Thorlabs stage needed.)

  Mode 3 — MINIMAL
    SMC100 moves Z automatically.
    User manually positions knife edge, reads power from the meter
    display, and types both values in.
    (No KDC101 or Ophir COM connection needed.)

Hardware:
  - Newport SMC100        (Z-axis, always used)
  - Thorlabs KDC101/Z825B (X-axis knife edge, Mode 1 only)
  - Ophir StarBright       (power meter, Modes 1 & 2 only)

Author : Joey Harrington
Date   : 2026-03-17
"""

import sys
import time
import csv
from datetime import datetime

import numpy as np
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

# ── pythonnet / Newport SMC100 (Windows-only, guarded) ───────────────────────
_HAS_SMC100 = False
SMC100 = None
if sys.platform == "win32":
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
        from CommandInterfaceSMC100 import SMC100 as _SMC100
        SMC100 = _SMC100
        _HAS_SMC100 = True
    except (ImportError, OSError):
        pass

if not _HAS_SMC100:
    import logging as _log
    _log.getLogger(__name__).debug("SMC100 .NET driver unavailable — CLI hardware commands disabled")

# ══════════════════════════════════════════════════════════════════════════════
# USER SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

# Newport SMC100 — Z axis (beam propagation)
SMC_PORT     = "COM3"
SMC_AXIS     = 1
SMC_VELOCITY = 2.5          # mm/s

# Z-scan positions (mm)
Z_POSITIONS = np.linspace(0.0, 50.0, 11)

# Thorlabs KDC101 — X axis (knife-edge sweep, Mode 1 only)
KDC_SERIAL  = "27266790"
X_CLEAR     = 0.0           # mm — knife edge fully retracted
X_START     = 2.0           # mm — sweep start (beam unclipped)
X_STOP      = 23.0          # mm — sweep end (beam fully clipped)
X_STEPS     = 50            # points per sweep
X_SETTLE_S  = 0.3           # settle time after each X move (seconds)

# Ophir StarBright (Modes 1 & 2)
OPHIR_NUM_READS  = 3
OPHIR_READ_DELAY = 0.2      # seconds

# Wavelength (µm) — for M² calculation
WAVELENGTH_UM = 2.94

# Output files
CSV_RAW     = "knife_edge_raw.csv"
CSV_RESULTS = "knife_edge_results.csv"
PLOT_FILE   = "beam_caustic.png"

# ══════════════════════════════════════════════════════════════════════════════


# ── OPHIR HELPER ──────────────────────────────────────────────────────────────
def ophir_read(com_obj, handle, channel=0, n_avg=3, delay=0.2):
    """Acquire n_avg readings from an already-streaming Ophir device."""
    readings = []
    attempts = 0
    while len(readings) < n_avg and attempts < n_avg * 20:
        time.sleep(delay)
        data = com_obj.GetData(handle, channel)
        if len(data[0]) > 0:
            for val in data[0]:
                readings.append(float(val))
        attempts += 1
    if not readings:
        print("  [WARN] No data from Ophir — returning NaN")
        return float("nan")
    return float(np.mean(readings[:n_avg]))


# ── SMC100 HELPERS ────────────────────────────────────────────────────────────
_smc = None

def smc_ts(axis):
    ret = _smc.TS(axis)
    vals = list(ret) if not isinstance(ret, int) else [ret]
    ok = (vals[0] == 0)
    state = ""
    for v in vals[1:]:
        if isinstance(v, str) and len(v) >= 2 and v[:2].isalnum():
            state = v
            break
    return ok, state

def smc_tp(axis):
    ret = _smc.TP(axis)
    vals = list(ret) if not isinstance(ret, int) else [ret]
    ok = (vals[0] == 0)
    pos = 0.0
    for v in vals[1:]:
        if isinstance(v, float):
            pos = v
            break
    return ok, pos

def smc_init():
    """Connect and home the SMC100."""
    global _smc
    print(f"Connecting to SMC100 on {SMC_PORT}...")
    _smc = SMC100()
    _smc.OpenInstrument(SMC_PORT)

    print("  Waiting for SMC100 to initialize...")
    ready = False
    homed = False
    for attempt in range(60):
        ok, state = smc_ts(SMC_AXIS)
        if ok and len(state) >= 2:
            code = state[:2]
            if code in ("32", "33", "34"):
                ready = True
                print(f"  SMC100 ready (state: {code})")
                break
            elif code in ("0A", "0B") and not homed:
                print("  SMC100 not homed — sending OR...")
                _smc.OR(SMC_AXIS)
                homed = True
            if attempt % 5 == 0 and attempt > 0:
                print(f"  Still waiting... (state: {code}, {attempt * 0.5:.0f}s)")
        time.sleep(0.5)

    if not ready:
        print("  [WARN] SMC100 did not reach READY in 30s.")

    _smc.VA_Set(SMC_AXIS, SMC_VELOCITY)
    ok, pos = smc_tp(SMC_AXIS)
    if ok:
        print(f"  SMC100 position: {pos:.3f} mm")

def smc_move_z(z_target):
    """Move SMC100 to z_target (mm) and return actual position."""
    ok, current_pos = smc_tp(SMC_AXIS)
    _smc.PA_Set(SMC_AXIS, z_target)
    travel = abs(z_target - current_pos) if ok else 10.0
    wait = (travel / SMC_VELOCITY) + 0.5
    print(f"  Moving Z... (~{wait:.1f}s)")
    time.sleep(wait)
    ok, actual_z = smc_tp(SMC_AXIS)
    if not ok:
        actual_z = z_target
    print(f"  Z = {actual_z:.3f} mm")
    return actual_z


# ── KDC101 HELPERS ────────────────────────────────────────────────────────────
def kdc_init():
    """Connect, enable, home the KDC101. Returns the device object."""
    from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
    from Thorlabs.MotionControl.KCube.DCServoCLI import KCubeDCServo

    print(f"Connecting to KDC101 (S/N {KDC_SERIAL})...")
    DeviceManagerCLI.BuildDeviceList()
    kdc = KCubeDCServo.CreateKCubeDCServo(KDC_SERIAL)
    kdc.Connect(KDC_SERIAL)
    time.sleep(0.25)
    kdc.StartPolling(250)
    time.sleep(0.25)
    kdc.EnableDevice()
    time.sleep(0.25)
    kdc.LoadMotorConfiguration(KDC_SERIAL)
    time.sleep(0.25)

    if not kdc.IsActualPositionKnown:
        print("  Homing KDC101...")
        kdc.Home(60000)
    print(f"  KDC101 ready (position: {kdc.Position} mm)")
    return kdc

def kdc_move_to(device, position_mm, timeout_ms=20000):
    from System import Decimal
    device.MoveTo(Decimal(float(position_mm)), timeout_ms)


# ── OPHIR INIT ────────────────────────────────────────────────────────────────
def ophir_init():
    """Connect to Ophir StarBright. Returns (COM_obj, DeviceHandle) or raises."""
    import win32com.client
    print("Connecting to Ophir StarBright...")
    OphirCOM = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")
    OphirCOM.StopAllStreams()
    OphirCOM.CloseAll()
    DeviceList = OphirCOM.ScanUSB()
    if not DeviceList:
        raise RuntimeError("No Ophir USB devices found.")
    DeviceHandle = OphirCOM.OpenUSBDevice(DeviceList[0])
    if not OphirCOM.IsSensorExists(DeviceHandle, 0):
        OphirCOM.CloseAll()
        raise RuntimeError("No sensor attached to Ophir device.")
    OphirCOM.SetRange(DeviceHandle, 0, 0)
    OphirCOM.StartStream(DeviceHandle, 0)
    print(f"  Ophir ready (device: {DeviceList[0]})")
    return OphirCOM, DeviceHandle


# ── FITTING ───────────────────────────────────────────────────────────────────
def beam_caustic(z, w0, z0, M2):
    lam = WAVELENGTH_UM
    return np.sqrt(w0**2 * (1 + (z - z0)**2 * ((M2 * lam) / (np.pi * w0**2))**2))

def find_clip_positions(x_arr, p_arr, P_full):
    """Interpolate sweep to find X at 16% and 84% of P_full."""
    p_norm = p_arr / P_full
    order = np.argsort(x_arr)
    x_s, p_s = x_arr[order], p_norm[order]
    try:
        f = interp1d(p_s, x_s, kind="linear", bounds_error=False,
                     fill_value="extrapolate")
        return float(f(0.16)), float(f(0.84))
    except Exception as e:
        print(f"  [WARN] Clip interpolation failed: {e}")
        return None, None

def fit_and_report(all_z, all_w):
    """Fit beam caustic, print results, save CSV and plot."""
    print("\n" + "=" * 60)
    if len(all_z) < 3:
        print(f"  Need >=3 fitted Z slices for caustic (got {len(all_z)})")
        print("=" * 60)
        return

    z_data = np.array(all_z)
    w_data = np.array(all_w)

    try:
        p0_c = [w_data.min(), z_data[np.argmin(w_data)], 1.2]
        popt_c, pcov_c = curve_fit(beam_caustic, z_data, w_data, p0=p0_c)
        w0, z0, M2 = abs(popt_c[0]), popt_c[1], abs(popt_c[2])
        perr_c = np.sqrt(np.diag(pcov_c))
        z_R = (np.pi * w0**2) / (M2 * WAVELENGTH_UM)

        print("  BEAM CAUSTIC FIT RESULTS")
        print("=" * 60)
        print(f"  Beam waist  w₀  = {w0:.2f} ± {perr_c[0]:.2f} µm")
        print(f"  Focus loc.  z₀  = {z0:.0f} ± {perr_c[1]:.0f} µm")
        print(f"  M²              = {M2:.2f} ± {perr_c[2]:.2f}")
        print(f"  Rayleigh    z_R = {z_R:.0f} µm")
        print(f"  λ               = {WAVELENGTH_UM} µm")
        print("=" * 60)

        with open(CSV_RESULTS, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["parameter", "value", "uncertainty", "unit"])
            wr.writerow(["w0", f"{w0:.4f}", f"{perr_c[0]:.4f}", "um"])
            wr.writerow(["z0", f"{z0:.2f}", f"{perr_c[1]:.2f}", "um"])
            wr.writerow(["M_squared", f"{M2:.4f}", f"{perr_c[2]:.4f}", ""])
            wr.writerow(["z_R", f"{z_R:.2f}", "", "um"])
            wr.writerow(["wavelength", f"{WAVELENGTH_UM}", "", "um"])
        print(f"  Results → {CSV_RESULTS}")

        z_fine = np.linspace(z_data.min(), z_data.max(), 300)
        w_fine = beam_caustic(z_fine, w0, z0, M2)
        fig, ax = plt.subplots(1, 1, dpi=200)
        ax.plot(z_data, w_data, "o", color="red", label="data")
        ax.plot(z_data, -w_data, "o", color="red")
        ax.plot(z_fine, w_fine, "-", color="blue", label="fit")
        ax.plot(z_fine, -w_fine, "-", color="blue")
        ax.grid(visible=True, which="major", axis="both",
                linestyle="dotted", color="0.1")
        ax.set_xlabel(r"Z position ($\mu$m)")
        ax.set_ylabel(r"Beam radius ($\mu$m)")
        ax.legend()
        plt.tight_layout()
        plt.savefig(PLOT_FILE, dpi=200)
        plt.close()
        print(f"  Plot   → {PLOT_FILE}")

        print(f"\n  Beam waist at focus: {w0:.2f} ± {perr_c[0]:.2f} µm")
        print(f"  Focus position: {z0:.2f} ± {perr_c[1]:.2f} µm")
        print(f"  M² factor: {M2:.2f} ± {perr_c[2]:.2f}")

    except RuntimeError as e:
        print(f"  [ERROR] Caustic fit failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — FULL AUTO
# ══════════════════════════════════════════════════════════════════════════════
def run_full_auto():
    """Both stages automated + Ophir auto-read. Hands-free after Enter."""
    OphirCOM, DeviceHandle = ophir_init()
    kdc = kdc_init()
    smc_init()

    with open(CSV_RAW, "w", newline="") as f:
        csv.writer(f).writerow(["timestamp", "z_mm", "x_mm", "power"])

    x_positions = np.linspace(X_START, X_STOP, X_STEPS)
    all_z, all_w = [], []

    try:
        print("\n" + "=" * 60)
        print("  MODE 1: FULL AUTO")
        print(f"  Z: {len(Z_POSITIONS)} pos, "
              f"{Z_POSITIONS[0]:.1f} → {Z_POSITIONS[-1]:.1f} mm (SMC100)")
        print(f"  X: {X_STEPS} pts, "
              f"{X_START:.1f} → {X_STOP:.1f} mm (KDC101/Z825B)")
        print("  Ctrl+C to abort.")
        print("=" * 60)
        input("\n  Press Enter to begin scan...")

        for z_idx, z_target in enumerate(Z_POSITIONS):
            print(f"\n── Z {z_idx+1}/{len(Z_POSITIONS)}: {z_target:.3f} mm ──")
            actual_z = smc_move_z(z_target)

            # Full-power reference
            print(f"  Retracting knife edge to X = {X_CLEAR:.1f} mm...")
            kdc_move_to(kdc, X_CLEAR)
            time.sleep(X_SETTLE_S)
            P_full = ophir_read(OphirCOM, DeviceHandle,
                                n_avg=OPHIR_NUM_READS, delay=OPHIR_READ_DELAY)
            if P_full < 1e-12:
                print(f"  [WARN] Full power too low ({P_full:.2e}), skipping.")
                continue
            print(f"  P₀ = {P_full:.4e}  |  16% = {0.16*P_full:.4e}  "
                  f"|  84% = {0.84*P_full:.4e}")

            # Sweep
            powers = []
            for x_idx, x_pos in enumerate(x_positions):
                kdc_move_to(kdc, x_pos)
                time.sleep(X_SETTLE_S)
                p = ophir_read(OphirCOM, DeviceHandle,
                               n_avg=OPHIR_NUM_READS, delay=OPHIR_READ_DELAY)
                powers.append(p)
                with open(CSV_RAW, "a", newline="") as f:
                    csv.writer(f).writerow([
                        datetime.now().isoformat(),
                        f"{actual_z:.3f}", f"{x_pos:.4f}", f"{p:.6e}",
                    ])
                if x_idx % 10 == 0 or x_idx == X_STEPS - 1:
                    print(f"    X={x_pos:7.3f}  P={p:.4e}  ({x_idx+1}/{X_STEPS})")

            # Clip positions
            p_arr = np.array(powers)
            x_16, x_84 = find_clip_positions(x_positions, p_arr, P_full)
            if x_16 is not None and x_84 is not None:
                w_um = abs(x_84 - x_16) / np.sqrt(2) * 1000.0
                all_z.append(actual_z * 1000.0)
                all_w.append(w_um)
                print(f"  ✓ x_16={x_16:.3f}  x_84={x_84:.3f}  → w = {w_um:.1f} µm")
            else:
                print("  [SKIP] Could not determine clip positions.")
            kdc_move_to(kdc, X_CLEAR)

        fit_and_report(all_z, all_w)

    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    finally:
        try: OphirCOM.StopAllStreams(); OphirCOM.CloseAll()
        except: pass
        try: kdc.StopPolling(); kdc.Disconnect(False)
        except: pass
        try: _smc.CloseInstrument()
        except: pass
        print(f"\nDone. Raw data → {CSV_RAW}")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — SEMI AUTO
# ══════════════════════════════════════════════════════════════════════════════
def run_semi_auto():
    """Z automated + Ophir auto-read. User positions knife edge manually."""
    OphirCOM, DeviceHandle = ophir_init()
    smc_init()

    with open(CSV_RAW, "w", newline="") as f:
        csv.writer(f).writerow([
            "timestamp", "z_mm", "P_full",
            "x_16pct_mm", "P_16pct_actual",
            "x_84pct_mm", "P_84pct_actual",
            "beam_radius_um",
        ])

    all_z, all_w = [], []

    try:
        print("\n" + "=" * 60)
        print("  MODE 2: SEMI AUTO")
        print("  Z moves automatically (SMC100).")
        print("  Ophir reads automatically.")
        print("  You manually position the knife edge.")
        print("  At each Z:")
        print("    1. Remove knife edge → Enter for full-power ref")
        print("    2. Move to 16% clip → type X pos → Enter")
        print("    3. Move to 84% clip → type X pos → Enter")
        print("  'skip' / 'quit' available at any prompt.")
        print("=" * 60)

        for z_idx, z_target in enumerate(Z_POSITIONS):
            print(f"\n── Z {z_idx+1}/{len(Z_POSITIONS)}: {z_target:.3f} mm ──")
            actual_z = smc_move_z(z_target)

            # Full-power reference
            user = input("\n  Remove knife edge, press Enter "
                         "('skip'/'quit'): ").strip().lower()
            if user == "quit": break
            if user == "skip": continue

            P_full = ophir_read(OphirCOM, DeviceHandle,
                                n_avg=OPHIR_NUM_READS, delay=OPHIR_READ_DELAY)
            if P_full < 1e-12:
                print(f"  [WARN] Full power too low ({P_full:.2e}), skipping.")
                continue
            P_16, P_84 = 0.16 * P_full, 0.84 * P_full
            print(f"  P₀ = {P_full:.4e}")
            print(f"  ── Target 16% = {P_16:.4e}")
            print(f"  ── Target 84% = {P_84:.4e}")

            # 16% clip
            x_16 = _prompt_float(
                f"\n  Move knife edge to ~{P_16:.3e} (16%)."
                f"\n  Enter X position (mm): ")
            if x_16 is None: break
            if x_16 == "skip": continue
            P_16_actual = ophir_read(OphirCOM, DeviceHandle,
                                     n_avg=OPHIR_NUM_READS, delay=OPHIR_READ_DELAY)
            print(f"       → P = {P_16_actual:.4e}  "
                  f"({(P_16_actual/P_full)*100:.1f}%)")

            # 84% clip
            x_84 = _prompt_float(
                f"\n  Move knife edge to ~{P_84:.3e} (84%)."
                f"\n  Enter X position (mm): ")
            if x_84 is None: break
            if x_84 == "skip": continue
            P_84_actual = ophir_read(OphirCOM, DeviceHandle,
                                     n_avg=OPHIR_NUM_READS, delay=OPHIR_READ_DELAY)
            print(f"       → P = {P_84_actual:.4e}  "
                  f"({(P_84_actual/P_full)*100:.1f}%)")

            # Compute
            d_clip = abs(x_84 - x_16)
            w_um = d_clip / np.sqrt(2) * 1000.0
            all_z.append(actual_z * 1000.0)
            all_w.append(w_um)
            print(f"\n  ✓ w = {w_um:.1f} µm  |  d(16–84) = {d_clip*1000:.1f} µm")

            # Symmetry check
            r16, r84 = P_16_actual / P_full, P_84_actual / P_full
            if abs(r16 - 0.16) + abs(r84 - 0.84) > 0.10:
                print(f"  ⚠ Symmetry: actual {r16*100:.1f}% / {r84*100:.1f}%")

            with open(CSV_RAW, "a", newline="") as f:
                csv.writer(f).writerow([
                    datetime.now().isoformat(), f"{actual_z:.3f}",
                    f"{P_full:.6e}",
                    f"{x_16:.4f}", f"{P_16_actual:.6e}",
                    f"{x_84:.4f}", f"{P_84_actual:.6e}",
                    f"{w_um:.2f}",
                ])

        fit_and_report(all_z, all_w)

    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    finally:
        try: OphirCOM.StopAllStreams(); OphirCOM.CloseAll()
        except: pass
        try: _smc.CloseInstrument()
        except: pass
        print(f"\nDone. Raw data → {CSV_RAW}")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 3 — MINIMAL
# ══════════════════════════════════════════════════════════════════════════════
def run_minimal():
    """Z automated only. User types knife-edge position AND power reading."""
    smc_init()

    with open(CSV_RAW, "w", newline="") as f:
        csv.writer(f).writerow([
            "timestamp", "z_mm", "P_full",
            "x_16pct_mm", "P_16pct_manual",
            "x_84pct_mm", "P_84pct_manual",
            "beam_radius_um",
        ])

    all_z, all_w = [], []

    try:
        print("\n" + "=" * 60)
        print("  MODE 3: MINIMAL AUTOMATION")
        print("  Z moves automatically (SMC100).")
        print("  You manually position the knife edge AND read the power.")
        print("  At each Z:")
        print("    1. Read full power from meter display → type it in")
        print("    2. Move to 16% clip → type X pos and power")
        print("    3. Move to 84% clip → type X pos and power")
        print("  'skip' / 'quit' available at any prompt.")
        print("=" * 60)

        for z_idx, z_target in enumerate(Z_POSITIONS):
            print(f"\n── Z {z_idx+1}/{len(Z_POSITIONS)}: {z_target:.3f} mm ──")
            actual_z = smc_move_z(z_target)

            # Full-power reference
            P_full = _prompt_float(
                "\n  Remove knife edge. Enter full power reading: ")
            if P_full is None: break
            if P_full == "skip": continue
            if P_full < 1e-12:
                print(f"  [WARN] Power too low ({P_full:.2e}), skipping.")
                continue
            P_16, P_84 = 0.16 * P_full, 0.84 * P_full
            print(f"  ── Target 16% = {P_16:.4e}")
            print(f"  ── Target 84% = {P_84:.4e}")

            # 16% clip
            print(f"\n  Move knife edge until meter reads ~{P_16:.3e} (16%).")
            x_16 = _prompt_float("  Enter X position (mm): ")
            if x_16 is None: break
            if x_16 == "skip": continue
            P_16_actual = _prompt_float("  Enter power reading: ")
            if P_16_actual is None: break
            if P_16_actual == "skip": continue
            print(f"       → {(P_16_actual/P_full)*100:.1f}% of full power")

            # 84% clip
            print(f"\n  Move knife edge until meter reads ~{P_84:.3e} (84%).")
            x_84 = _prompt_float("  Enter X position (mm): ")
            if x_84 is None: break
            if x_84 == "skip": continue
            P_84_actual = _prompt_float("  Enter power reading: ")
            if P_84_actual is None: break
            if P_84_actual == "skip": continue
            print(f"       → {(P_84_actual/P_full)*100:.1f}% of full power")

            # Compute
            d_clip = abs(x_84 - x_16)
            w_um = d_clip / np.sqrt(2) * 1000.0
            all_z.append(actual_z * 1000.0)
            all_w.append(w_um)
            print(f"\n  ✓ w = {w_um:.1f} µm  |  d(16–84) = {d_clip*1000:.1f} µm")

            r16, r84 = P_16_actual / P_full, P_84_actual / P_full
            if abs(r16 - 0.16) + abs(r84 - 0.84) > 0.10:
                print(f"  ⚠ Symmetry: actual {r16*100:.1f}% / {r84*100:.1f}%")

            with open(CSV_RAW, "a", newline="") as f:
                csv.writer(f).writerow([
                    datetime.now().isoformat(), f"{actual_z:.3f}",
                    f"{P_full:.6e}",
                    f"{x_16:.4f}", f"{P_16_actual:.6e}",
                    f"{x_84:.4f}", f"{P_84_actual:.6e}",
                    f"{w_um:.2f}",
                ])

        fit_and_report(all_z, all_w)

    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    finally:
        try: _smc.CloseInstrument()
        except: pass
        print(f"\nDone. Raw data → {CSV_RAW}")


# ── INPUT HELPER ──────────────────────────────────────────────────────────────
def _prompt_float(prompt):
    """
    Prompt user for a float. Returns:
      float value  — on valid number
      "skip"       — if user types 'skip'
      None         — if user types 'quit'
    """
    while True:
        user = input(prompt).strip().lower()
        if user == "quit":
            print("\nScan terminated by user.")
            return None
        if user == "skip":
            print("  Skipping this Z position.")
            return "skip"
        try:
            return float(user)
        except ValueError:
            print("  Enter a number, 'skip', or 'quit'.")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  KNIFE-EDGE Z-SCAN BEAM PROFILER")
    print("=" * 60)
    print()
    print("  Select automation mode:")
    print()
    print("  [1] FULL AUTO")
    print("      Z stage + knife-edge stage + power meter all automated.")
    print("      Requires: SMC100, KDC101/Z825B, Ophir StarBright.")
    print()
    print("  [2] SEMI AUTO")
    print("      Z stage + power meter automated.")
    print("      You manually position the knife edge.")
    print("      Requires: SMC100, Ophir StarBright.")
    print()
    print("  [3] MINIMAL")
    print("      Z stage automated only.")
    print("      You position knife edge and read power from display.")
    print("      Requires: SMC100 only.")
    print()

    while True:
        choice = input("  Enter mode (1/2/3): ").strip()
        if choice in ("1", "2", "3"):
            break
        print("  Please enter 1, 2, or 3.")

    print()
    if choice == "1":
        run_full_auto()
    elif choice == "2":
        run_semi_auto()
    else:
        run_minimal()


if __name__ == "__main__":
    main()
