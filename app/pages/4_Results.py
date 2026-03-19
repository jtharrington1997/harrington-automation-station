"""
pages/4_Results.py -- Results & Analysis
Beam caustic plot, parameter table, data export.
"""
from __future__ import annotations

import csv
import io

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from automation_station.ui.layout import render_header
from harrington_common.theme import aw_panel, BRAND

st.set_page_config(page_title="Results", layout="wide")
render_header()

with aw_panel():
    st.subheader("Results & Analysis")
    st.caption("Beam caustic fit. Parameter extraction. Data export.")

fit = st.session_state.get("fit_result")
scan = st.session_state.get("scan_data")

if not fit:
    st.info("No scan results yet. Run a scan from one of the mode pages.")
    st.stop()

# ── Parameter Table ───────────────────────────────────────────────────────────
with aw_panel():
    st.markdown("#### Beam Parameters")

    divergence = fit["M2"] * fit["wavelength"] / (np.pi * fit["w0"]) * 1000

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Beam waist w0", f"{fit['w0']:.2f} um", f"+/- {fit['w0_err']:.2f}")
    c2.metric("M-squared", f"{fit['M2']:.2f}", f"+/- {fit['M2_err']:.2f}")
    c3.metric("Rayleigh range z_R", f"{fit['z_R']:.0f} um")
    c4.metric("Divergence", f"{divergence:.2f} mrad")

    c5, c6, c7 = st.columns(3)
    c5.metric("Waist position z0", f"{fit['z0']:.0f} um", f"+/- {fit['z0_err']:.0f}")
    c6.metric("Beam diameter 2w0", f"{2 * fit['w0']:.2f} um")
    c7.metric("Wavelength", f"{fit['wavelength']} um")

# ── Beam Caustic Plot ─────────────────────────────────────────────────────────
with aw_panel():
    st.markdown("#### Beam Caustic")

    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(go.Scatter(
        x=fit["z_data"], y=fit["w_data"], mode="markers",
        name="Measured w(z)", marker=dict(color=BRAND["accent"], size=10, symbol="circle"),
    ))
    fig.add_trace(go.Scatter(
        x=fit["z_data"], y=[-w for w in fit["w_data"]], mode="markers",
        showlegend=False, marker=dict(color=BRAND["accent"], size=10, symbol="circle"),
    ))
    fig.add_trace(go.Scatter(
        x=fit["z_fit"], y=fit["w_fit"], mode="lines",
        name="Hyperbolic fit", line=dict(color=BRAND["primary"], width=2.5),
    ))
    fig.add_trace(go.Scatter(
        x=fit["z_fit"], y=[-w for w in fit["w_fit"]], mode="lines",
        showlegend=False, line=dict(color=BRAND["primary"], width=2.5),
    ))
    # Waist markers
    fig.add_hline(
        y=fit["w0"], line_dash="dash", line_color=BRAND["gold"],
        annotation_text=f"w0 = {fit['w0']:.1f} um",
    )
    fig.add_hline(y=-fit["w0"], line_dash="dash", line_color=BRAND["gold"])
    fig.add_vline(
        x=fit["z0"], line_dash="dot", line_color="#8B949E",
        annotation_text=f"z0 = {fit['z0']:.0f} um",
    )
    fig.update_layout(
        xaxis_title="Z position (um)",
        yaxis_title="Beam radius w (um)",
        title=f"Beam Caustic -- M-squared = {fit['M2']:.2f}, w0 = {fit['w0']:.1f} um",
        height=500,
        legend=dict(x=0.02, y=0.98),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Residuals ─────────────────────────────────────────────────────────────────
if len(fit["z_data"]) > 0:
    from utils.analysis import beam_caustic

    w_predicted = beam_caustic(
        fit["z_data"], fit["w0"], fit["z0"], fit["M2"], fit["wavelength"]
    )
    residuals = fit["w_data"] - w_predicted

    with aw_panel():
        st.markdown("#### Fit Residuals")
        fig_res = go.Figure()
        fig_res.add_trace(go.Bar(
            x=fit["z_data"],
            y=residuals,
            marker_color=[
                BRAND["gold"] if abs(r) < fit["w0"] * 0.05 else BRAND["accent"]
                for r in residuals
            ],
        ))
        fig_res.add_hline(y=0, line_color="#8B949E", line_width=1)
        fig_res.update_layout(
            xaxis_title="Z position (um)",
            yaxis_title="Residual (um)",
            height=250,
            showlegend=False,
        )
        st.plotly_chart(fig_res, use_container_width=True)

# ── Data Export ───────────────────────────────────────────────────────────────
with aw_panel():
    st.markdown("#### Export Data")

    col1, col2 = st.columns(2)

    with col1:
        buf = io.StringIO()
        wr = csv.writer(buf)
        wr.writerow(["parameter", "value", "uncertainty", "unit"])
        wr.writerow(["w0", f"{fit['w0']:.4f}", f"{fit['w0_err']:.4f}", "um"])
        wr.writerow(["z0", f"{fit['z0']:.2f}", f"{fit['z0_err']:.2f}", "um"])
        wr.writerow(["M_squared", f"{fit['M2']:.4f}", f"{fit['M2_err']:.4f}", ""])
        wr.writerow(["z_R", f"{fit['z_R']:.2f}", "", "um"])
        wr.writerow(["wavelength", f"{fit['wavelength']}", "", "um"])
        st.download_button(
            "Download Results CSV", buf.getvalue(),
            "beam_caustic_results.csv", "text/csv",
            use_container_width=True,
        )

    with col2:
        buf2 = io.StringIO()
        wr2 = csv.writer(buf2)
        wr2.writerow(["z_um", "w_um"])
        for z, w in zip(fit["z_data"], fit["w_data"]):
            wr2.writerow([f"{z:.2f}", f"{w:.2f}"])
        st.download_button(
            "Download Raw Data CSV", buf2.getvalue(),
            "beam_radii_raw.csv", "text/csv",
            use_container_width=True,
        )
