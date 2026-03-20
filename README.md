# Automation Station

Lab automation and beam-characterization platform built with Streamlit.

Automation Station provides a structured interface for beam profiling, hardware control, data analysis, and comparison of experimental measurements against simulation outputs. It is intended for technical lab workflows ranging from guided acquisition to more automated measurement runs.

## Core capabilities

- Automated and semi-automated beam characterization workflows
- Hardware-assisted scan orchestration
- Beam caustic analysis and parameter extraction
- Result review and export
- Gnuplot-oriented plotting workflow
- Digital Twin comparison against model outputs
- Shared Americana design system via `harrington-common`

## Supported workflow tiers

- Full automation
- Semi-automated acquisition
- Minimal/manual acquisition
- Results and analysis review
- Hardware and scan settings
- Admin-only controls

## Hardware integration

Typical supported hardware includes:

- Ophir StarBright
- Newport SMC100
- Thorlabs KDC101

The exact hardware stack can be extended as the platform grows.

## Repository layout

Typical areas include:

- `app/` for the Streamlit entrypoint and pages
- `src/automation_station/` for analysis logic, hardware integration, I/O, and UI helpers
- `data/cache/` for runtime artifacts
- `data/results/` for measurement outputs

## Installation

This project uses `uv`.

### Prerequisites

- Python 3.10+
- `uv`
- local sibling checkout of `harrington-common`

Expected layout:

```text
Projects/
  harrington-common/
  automation-station/
```

### Install dependencies

```bash
uv sync
```

### Run the app

```bash
uv run streamlit run app/streamlit_app.py
```

## Development notes

- Keep hardware-facing logic isolated from Streamlit page code
- Preserve admin gating for protected controls
- Prefer reproducible `uv` workflows over ad hoc environment setup
- Use the shared theme layer rather than repo-local visual drift

## Related repos

- `harrington-common`
- `harrington-lmi`
