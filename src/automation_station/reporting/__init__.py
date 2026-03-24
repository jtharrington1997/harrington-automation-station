"""Measurement report PDF generator for automation-station.

Produces a structured lab measurement document including:
- Scan configuration (z-positions, knife-edge settings)
- Beam radius vs z (caustic) with M² fit
- Individual knife-edge profiles
- Comparison with digital twin predictions

No Streamlit imports.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

from harrington_common.reporting import (
    ReportSection, ReportConfig, build_report_pdf, latex_table,
    GnuplotSpec, GnuplotSeries,
)


def _config_section(
    wavelength_um: float = 2.94,
    z_positions: list[float] | None = None,
    x_range: tuple[float, float] = (2.0, 23.0),
    x_steps: int = 50,
    mode: str = "Full Auto",
) -> ReportSection:
    """Build scan configuration table."""
    rows = [
        ["Wavelength", f"{wavelength_um:.2f} \\textmu m"],
        ["Z positions", f"{len(z_positions) if z_positions else 'N/A'} points"],
        ["X sweep range", f"{x_range[0]:.1f} -- {x_range[1]:.1f} mm"],
        ["X steps", str(x_steps)],
        ["Acquisition mode", mode],
        ["Date", date.today().isoformat()],
    ]
    table = latex_table(["Parameter", "Value"], rows)
    return ReportSection(title="Scan Configuration", content=table, level=1)


def _caustic_section(
    z_mm: np.ndarray,
    w_mm: np.ndarray,
    w0_mm: float | None = None,
    z0_mm: float | None = None,
    m_squared: float | None = None,
    z_rayleigh_mm: float | None = None,
) -> tuple[ReportSection, GnuplotSpec | None]:
    """Build caustic fit results section with gnuplot figure."""
    rows = []
    if w0_mm is not None:
        rows.append(["Beam waist $w_0$", f"{w0_mm*1000:.1f} \\textmu m"])
    if z0_mm is not None:
        rows.append(["Focus position $z_0$", f"{z0_mm:.2f} mm"])
    if m_squared is not None:
        rows.append(["$M^2$", f"{m_squared:.2f}"])
    if z_rayleigh_mm is not None:
        rows.append(["Rayleigh range $z_R$", f"{z_rayleigh_mm:.2f} mm"])

    table = latex_table(["Parameter", "Value"], rows) if rows else ""
    content = f"Beam caustic measured at {len(z_mm)} z-positions.\n\n{table}"
    section = ReportSection(title="Caustic Fit Results", content=content, level=1)

    # Gnuplot figure
    spec = GnuplotSpec(
        title="Beam Caustic — $w(z)$",
        xlabel="z position (mm)",
        ylabel="Beam radius (mm)",
        series=[
            GnuplotSeries(name="Measured", x=z_mm.tolist(), y=w_mm.tolist(), style="points"),
        ],
    )
    # Add fit curve if we have the parameters
    if w0_mm is not None and z0_mm is not None and z_rayleigh_mm is not None:
        z_fine = np.linspace(z_mm.min(), z_mm.max(), 200)
        w_fit = w0_mm * np.sqrt(1 + ((z_fine - z0_mm) / z_rayleigh_mm)**2)
        spec.series.append(
            GnuplotSeries(name="Hyperbolic Fit", x=z_fine.tolist(), y=w_fit.tolist(), style="lines")
        )

    return section, spec


def _twin_comparison_section(
    z_mm: np.ndarray,
    w_measured_mm: np.ndarray,
    w_simulated_mm: np.ndarray,
) -> tuple[ReportSection, GnuplotSpec]:
    """Build measured vs simulated comparison."""
    residual = w_measured_mm - w_simulated_mm
    rmse = float(np.sqrt(np.mean(residual**2)))
    max_err = float(np.max(np.abs(residual)))
    mean_err_pct = float(np.mean(np.abs(residual) / w_measured_mm) * 100) if np.all(w_measured_mm > 0) else 0.0

    rows = [
        ["RMSE", f"{rmse*1000:.1f} \\textmu m"],
        ["Max absolute error", f"{max_err*1000:.1f} \\textmu m"],
        ["Mean relative error", f"{mean_err_pct:.1f}\\%"],
    ]
    table = latex_table(["Metric", "Value"], rows)
    content = f"Comparison of measured beam caustic against digital twin simulation.\n\n{table}"
    section = ReportSection(title="Digital Twin Comparison", content=content, level=1)

    spec = GnuplotSpec(
        title="Measured vs Simulated",
        xlabel="z position (mm)",
        ylabel="Beam radius (mm)",
        series=[
            GnuplotSeries(name="Measured", x=z_mm.tolist(), y=w_measured_mm.tolist(), style="points"),
            GnuplotSeries(name="Simulated", x=z_mm.tolist(), y=w_simulated_mm.tolist(), style="lines"),
        ],
    )

    return section, spec


def build_measurement_report(
    z_mm: np.ndarray,
    w_mm: np.ndarray,
    w0_mm: float | None = None,
    z0_mm: float | None = None,
    m_squared: float | None = None,
    z_rayleigh_mm: float | None = None,
    wavelength_um: float = 2.94,
    w_simulated_mm: np.ndarray | None = None,
    output_path: str = "measurement_report.pdf",
) -> str:
    """Generate a complete measurement report PDF.

    Returns the output file path.
    """
    config = ReportConfig(
        title="Beam Characterization Report",
        author="Joey Harrington",
        date=date.today().isoformat(),
        header_left="Automation Station",
        header_right=f"$\\lambda$ = {wavelength_um:.2f} \\textmu m",
    )

    sections = [_config_section(wavelength_um=wavelength_um)]
    gnuplot_specs = []

    caustic_sec, caustic_plot = _caustic_section(
        z_mm, w_mm, w0_mm, z0_mm, m_squared, z_rayleigh_mm,
    )
    sections.append(caustic_sec)
    if caustic_plot:
        gnuplot_specs.append(("caustic", caustic_plot))

    if w_simulated_mm is not None:
        twin_sec, twin_plot = _twin_comparison_section(z_mm, w_mm, w_simulated_mm)
        sections.append(twin_sec)
        gnuplot_specs.append(("twin_comparison", twin_plot))

    sections.append(ReportSection(
        title="Notes",
        content="Beam radii extracted from knife-edge scans via error-function fit. "
                "Caustic fit uses hyperbolic beam model with $M^2$ parameter. "
                "Report auto-generated by the Automation Station platform.",
        level=1,
    ))

    path = build_report_pdf(
        sections, output_path, config,
        gnuplot_specs=gnuplot_specs if gnuplot_specs else None,
    )
    return str(path)
