# Automation Station

Lab automation platform for beam profiling, hardware control, and data analysis.
Supports automated, semi-automated, and manual knife-edge beam characterization
with live power display, caustic fitting, gnuplot visualization, and a digital
twin comparison mode for overlaying experimental data against LMI model predictions.

Built with Streamlit. Part of the Harrington app ecosystem.

## Pages

| Page | Description |
|------|-------------|
| Full Auto | Z stage + knife-edge + power meter all automated. Press start and walk away |
| Semi Auto | Z stage + power meter automated. Manual knife-edge with live power guidance |
| Minimal | Z stage automated. Manual data entry for positions and power readings |
| Results | Beam caustic plot, parameter extraction (w0, M-squared, z_R), data export |
| Settings | Hardware configuration, scan defaults, connection parameters |
| Gnuplot | Publication-quality plots from scan data. Live script editor with render |
| Admin | Hardware profiles, API keys, analysis defaults, password management |
| Digital Twin Compare | Overlay experimental beam profiles, transmission, damage data against LMI models |

## Supported Hardware

- **Ophir StarBright** -- Power meter (COM/USB via pythonnet)
- **Newport SMC100** -- Z-axis linear stage (serial)
- **Thorlabs KDC101** -- X-axis knife-edge actuator (Kinesis .NET)

## Setup

```bash
uv sync
uv run streamlit run app/streamlit_app.py
```

Runs on port 8503 by default. For hardware support on Windows:

```bash
uv sync --extra hardware
```

## Architecture

```
automation-station/
  app/
    streamlit_app.py
    pages/
      1_Full_Auto.py
      2_Semi_Auto.py
      3_Minimal.py
      4_Results.py
      5_Settings.py
      6_Gnuplot.py
      7_Admin.py
      8_Digital_Twin_Compare.py
  src/automation_station/
    analysis/
      beam_profile.py
    hardware/
      drivers.py
    io/
      config.py
    ui/
      branding.py      # Delegates to harrington-common
      layout.py        # render_header()
      access.py        # Admin auth
    cli.py
  data/
    cache/
    results/
```

## Dependencies

Uses `harrington-common` for the shared Americana theme. GPU acceleration
via numba/cupy (CUDA toolkit required).
