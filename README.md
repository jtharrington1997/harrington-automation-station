# Knife-Edge Z-Scan Beam Profiler

Automated beam characterization tool using the knife-edge / clip-level method.
Measures the 1/e² beam radius at multiple positions along the propagation axis,
then fits a beam caustic to extract waist size (w₀), waist location (z₀),
Rayleigh range (z_R), and M² beam quality factor.

Two interfaces are provided: a **Streamlit web app** with live power display
and interactive controls, and a **standalone CLI script** for headless operation.

---

## Quick Start

```powershell
# 1. Install uv (if not already installed)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Clone or copy the project
cd C:\Users\joeyh\Projects
# Copy the knife-edge-profiler folder here

# 3. Sync dependencies (creates .venv automatically)
cd knife-edge-profiler
uv sync

# 4. Launch the web app
uv run streamlit run Home.py

# 5. Or run the CLI version directly
uv run python knife_edge_zscan.py
```

---

## Project Structure

```
knife-edge-profiler/
├── Home.py                    # Streamlit dashboard (main entry point)
├── pyproject.toml             # Project config & dependencies (uv)
├── .streamlit/
│   └── config.toml            # Dark theme configuration
├── pages/
│   ├── 1_Full_Auto.py         # Mode 1: fully automated scan
│   ├── 2_Semi_Auto.py         # Mode 2: semi-auto with live power display
│   ├── 3_Minimal.py           # Mode 3: manual entry with Z automation
│   ├── 4_Results.py           # Results, plots, and data export
│   └── 5_Settings.py          # Hardware configuration
├── utils/
│   ├── __init__.py
│   ├── hardware.py            # Hardware abstraction (SMC100, KDC101, Ophir)
│   └── analysis.py            # Fitting functions and data processing
│
knife_edge_zscan.py            # Standalone CLI script (no Streamlit needed)
README.md                      # This file
```

---

## Automation Modes

### Mode 1 — Full Auto
Everything runs unattended. SMC100 moves Z, KDC101 sweeps the knife edge,
Ophir reads power. Press start and walk away.

**Requires:** SMC100 + KDC101/Z825B + Ophir StarBright

### Mode 2 — Semi Auto
Z stage and power meter are automated. You manually position the knife edge.
The app shows a **live power reading** with color-coded feedback (green = on target,
yellow = close, red = far) to guide you to the 16% and 84% clip points.

**Requires:** SMC100 + Ophir StarBright

### Mode 3 — Minimal
Only the Z stage is automated. You position the knife edge and read the power
from the meter display, typing both values into the app.

**Requires:** SMC100 only

---

## Hardware

| Device | Role | Connection | Modes |
|--------|------|------------|-------|
| Newport SMC100 | Z-axis translation | USB → COM3 | All |
| Thorlabs KDC101 | Knife-edge sweep controller | USB | 1 only |
| Thorlabs Z825B | 25 mm DC servo stage | 6-pin → KDC101 | 1 only |
| Ophir StarBright | Laser power meter | USB | 1, 2 |

---

## Software Prerequisites

### uv (Package Manager)

All Python dependencies are managed with [uv](https://docs.astral.sh/uv/).
Install it once:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip if you prefer
pip install uv
```

Verify:

```powershell
uv --version
```

### Python 3.10+ (3.12 confirmed)

uv will manage the Python version for you. If you want to specify one:

```powershell
uv python install 3.12
```

### Project Dependencies

From the project root:

```powershell
uv sync
```

This reads `pyproject.toml`, creates a `.venv`, and installs everything:
`streamlit`, `numpy`, `scipy`, `matplotlib`, `plotly`, `pandas`,
`pythonnet`, `pywin32`.

To add a new dependency later:

```powershell
uv add <package-name>
```

### Newport SMC100 DLL

Installed by Newport's motion controller software. Expected path:

```
C:\Windows\Microsoft.NET\assembly\GAC_64\
  Newport.SMC100.CommandInterface\
    v4.0_2.0.0.3__d9d722840772240b\
      Newport.SMC100.CommandInterface.dll
```

If your version differs, update the paths in `utils/hardware.py` (line ~74)
and `knife_edge_zscan.py` (line ~39).

To register manually (admin cmd):

```powershell
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\regasm.exe ^
  "path\to\Newport.SMC100.CommandInterface.dll" /codebase
```

### Thorlabs Kinesis (Mode 1 only)

Download from [thorlabs.com](https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=Motion_Control).
Install to the default path (`C:\Program Files\Thorlabs\Kinesis`).

**First-time setup:**
1. Open Kinesis GUI
2. Find KDC101 (S/N 27266790)
3. Settings → select **Z825B** as actuator → Apply
4. Click Home, verify the stage moves
5. **Close Kinesis before running the Python app**

### Ophir StarLab (Modes 1 & 2)

Download from [ophiropt.com](https://www.ophiropt.com/laser-measurement/software/starlab).
The installer registers the `OphirLMMeasurement` COM object.

**First-time setup:**
1. Open StarLab
2. Confirm the StarBright detects its sensor and shows readings
3. **Close StarLab before running the Python app**

---

## Deployment on Your Laptop

### Step-by-step

```powershell
# 1. Open PowerShell / VS Code terminal

# 2. Install uv (one time)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 3. Navigate to your projects folder
cd C:\Users\joeyh\Projects

# 4. Copy files (or clone from your repo)
#    Place the knife-edge-profiler/ folder here

# 5. Install all dependencies
cd knife-edge-profiler
uv sync

# 6. Verify hardware software is installed:
#    - Newport Motion Controller Applet (for SMC100 DLL)
#    - Thorlabs Kinesis (for KDC101 DLLs)
#    - Ophir StarLab (for COM object)

# 7. Connect hardware via USB:
#    - SMC100 → COM3 (check Device Manager if different)
#    - KDC101 → USB
#    - Ophir StarBright → USB

# 8. CLOSE any Newport, Kinesis, or StarLab GUIs
#    (only one app can talk to each device at a time)

# 9. Launch the web app
uv run streamlit run Home.py
```

The app opens in your default browser at `http://localhost:8501`.

### Running the CLI version instead

```powershell
uv run python knife_edge_zscan.py
```

Select mode 1, 2, or 3 at the prompt. No browser needed.

### Running from VS Code

1. Open the `knife-edge-profiler` folder in VS Code
2. Open a terminal (Ctrl+`)
3. Run `uv run streamlit run Home.py`
4. VS Code may auto-detect the port and offer to open the browser

### Accessing from iPad via Tailscale

If you're running on IronMan and want to access from your iPad:

```powershell
# On IronMan, launch with network access
uv run streamlit run Home.py --server.address 0.0.0.0
```

Then on your iPad browser, navigate to `http://<ironman-tailscale-ip>:8501`.

---

## Common uv Commands

```powershell
uv sync                    # Install/update all dependencies from pyproject.toml
uv add <package>           # Add a new dependency
uv remove <package>        # Remove a dependency
uv run <command>           # Run a command in the project's venv
uv run python              # Open a Python REPL in the venv
uv lock                    # Regenerate the lockfile
uv tree                    # Show dependency tree
```

---

## Using the Web App

### Dashboard (Home)

The landing page shows:
- **Hardware status** — green/grey indicators for each device
- **Connect buttons** — click to initialize each device
- **Mode selection cards** — choose your scan mode
- **Latest results** — if a scan has been completed

Connect your devices first (SMC100 is always needed), then launch a mode.

### Mode 2: Semi Auto (Live Power Display)

This is the primary interactive mode. The workflow at each Z position:

1. **Full Power Reference** — remove the knife edge, click "Read Full Power"
2. **16% Clip** — the app shows a large live power reading with color feedback:
   - **Green** = within 3% of target (record now)
   - **Yellow** = within 8% (getting close)
   - **Red** = too far (keep adjusting)
   - Click "Refresh" to update the reading as you move the blade
   - Type the X position and click "Record 16% Position"
3. **84% Clip** — same process for the 84% target
4. **Auto-advance** — the Z stage moves to the next position automatically

### Results & Analysis

After the scan completes:
- **Parameter table** — w₀, M², z_R, z₀, divergence with uncertainties
- **Interactive caustic plot** — hover for values, zoom, pan
- **Fit residuals** — color-coded bar chart (green = good, red = outlier)
- **CSV export** — download results and raw data

---

## Theory

### Knife-Edge Clip Method

A knife edge translating across a Gaussian beam produces transmitted power:

```
P(x) = (P₀/2) · [1 + erf(√2 · (x - x₀) / w)]
```

The 16% and 84% power points correspond to the ±w beam edges:

```
w = |x₈₄ - x₁₆| / √2
```

### Beam Caustic

```
w(z) = w₀ · √(1 + ((z - z₀) · M² · λ / (π · w₀²))²)
```

Fitted parameters:
- **w₀** — beam waist (minimum radius)
- **z₀** — waist position along propagation axis
- **M²** — beam quality factor (1.0 for ideal Gaussian)
- **z_R** = π·w₀² / (M²·λ) — Rayleigh range

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid class string" on Ophir connect | Install StarLab. Open it once to verify, then close. |
| SMC100 TypeError on connect | DLL version mismatch. Check the folder name in GAC_64. |
| SMC100 doesn't move | It's homing. Wait up to 30s. Check stage cable. |
| KDC101 doesn't move | Open Kinesis, set actuator to Z825B, Apply. Close Kinesis. |
| Power reads NaN | Check sensor head. Increase Ophir averages. Close StarLab. |
| Caustic fit fails | Need ≥3 Z slices. Widen Z range. Check X sweep clips fully. |
| `uv` not found | Re-run the install script or `pip install uv`. |
| `uv sync` fails | Run `uv python install 3.12` first. |
| App won't open in browser | Try `http://localhost:8501` manually. |
| Can't access from iPad | Use `--server.address 0.0.0.0` flag. Check Tailscale. |
