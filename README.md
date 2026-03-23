# harrington-automation-station

Lab automation platform for knife-edge beam profiling, hardware-coordinated measurements, and experimental data analysis. Controls Newport SMC100/NSC100 motion stages, Thorlabs KDC101 actuators, and Ophir StarBright power meters with full digital twin simulation capability.

**Port 8503** · Streamlit + harrington-common

## Modules

| Page | Function |
|------|----------|
| 1 — Full Auto | Fully automated beam profiling: configure scan parameters, run acquisition, analyze results |
| 2 — Semi Auto | Manual stage control with automated data collection at each position |
| 3 — Minimal | Bare-minimum interface for quick single-axis scans |
| 4 — Results | Browse, compare, and export completed measurement datasets |
| 5 — Settings | Hardware configuration, COM ports, scan defaults |
| 6 — Gnuplot | Export measurement data to gnuplot-ready format with auto-generated scripts |
| 7 — Digital Twin | Compare real measurements against simulated beam profiles |
| 9 — Admin | API keys, system settings |

## Hardware Drivers

```
src/automation_station/hardware/
├── drivers.py          Unified driver layer
│   ├── OphirStarBright   Ophir power meter (COM/USB, win32com)
│   ├── NewportSMC100     Newport SMC100 stage (.NET/pythonnet)
│   ├── ThorlabsKDC101    Thorlabs KDC101 actuator (.NET/pythonnet)
│   └── NewportNSC100     Newport NSC100 wrapper (delegates to nsc100/)
└── nsc100/             Newport NSC100 serial driver (folded from standalone repo)
    ├── __init__.py     Full RS-232 command set, state machine, property API
    ├── mock.py         MockNSC100 for development without hardware
    └── scan.py         Reusable linear scan orchestration
```

The NSC100 driver supports XON/XOFF flow control at 57600 baud, all documented controller states, blocking motion with timeout/error detection, and a context manager interface. MockNSC100 provides identical API for UI development.

## Package Structure

```
src/automation_station/
├── analysis/
│   └── beam_profile.py   Knife-edge fitting, beam width extraction, M² estimation
├── hardware/             All hardware drivers (see above)
├── io/
│   └── config.py         Scan configuration, COM port settings
├── ui/                   Layout, branding, access control
└── cli.py                Command-line profiler interface
```

## Installation

```bash
# Base install (includes numba + joblib)
uv sync

# With CUDA GPU (optional)
pip install "automation-station[cuda]"

# With hardware control (Windows/Linux with serial)
pip install "automation-station[hardware]"
```

Note: `cupy-cuda12x` is optional — base install works on all platforms.

## Running

```bash
source ~/harrington/.venv/bin/activate
cd ~/harrington/harrington-automation-station
streamlit run app/streamlit_app.py
```

## TODO

- [ ] Add 2D beam profiling (X + Y knife-edge scans)
- [ ] Build beam pointing stability monitor (continuous position tracking)
- [ ] Add M² measurement workflow (multi-position caustic scan)
- [ ] Integrate power meter reading directly into scan workflow
- [ ] Add real-time plotting during scan acquisition
- [ ] Build measurement report PDF via harrington-common reporting
- [ ] Add hardware auto-discovery for COM ports
- [ ] Add scan queue for batch measurements
- [ ] Improve digital twin with measured vs simulated overlay
- [ ] Add data export to HDF5 format for large datasets
