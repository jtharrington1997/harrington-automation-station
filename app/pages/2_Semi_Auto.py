"""
pages/2_Semi_Auto.py -- Semi-Automated Knife-Edge Scan
Z stage automated, Ophir reads automatically, manual knife-edge positioning.
Features live power display to guide user to 16%/84% clip points.
"""
from __future__ import annotations

import time

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from automation_station.ui.layout import render_header
from harrington_common.theme import aw_panel, BRAND

st.set_page_config(page_title="Semi Auto", layout="wide")
render_header()


# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "m2_step": "idle",
    "m2_z_idx": 0,
    "m2_P_full": 0.0,
    "m2_results": [],
    "m2_all_z": [],
    "m2_all_w": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Header ────────────────────────────────────────────────────────────────────
with aw_panel():
    st.subheader("Mode 2: Semi Auto")
    st.caption("Z stage + power meter automated. Manual knife-edge positioning. Live power display.")


# ── Check hardware ────────────────────────────────────────────────────────────
ophir = st.session_state.get("hw_ophir")
smc = st.session_state.get("hw_smc")

if not ophir or not ophir.available:
    st.error("Ophir StarBright not connected. Go to Dashboard to connect.")
    st.stop()
if not smc or not smc.available:
    st.error("Newport SMC100 not connected. Go to Dashboard to connect.")
    st.stop()


# ── Settings sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("#### Scan Parameters")
    z_start = st.number_input("Z start (mm)", value=0.0, step=1.0)
    z_stop = st.number_input("Z stop (mm)", value=50.0, step=1.0)
    z_steps = st.number_input("Z steps", value=11, min_value=3, max_value=50, step=1)
    wavelength = st.number_input("Wavelength (um)", value=2.94, step=0.01, format="%.3f")
    n_avg = st.number_input("Ophir averages", value=3, min_value=1, max_value=20, step=1)
    st.markdown("---")
    if st.button("Reset Scan", type="secondary", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()

z_positions = np.linspace(z_start, z_stop, int(z_steps))
z_idx = st.session_state.m2_z_idx
total_z = len(z_positions)


# ── Live power meter ──────────────────────────────────────────────────────────
def read_and_display_power():
    """Read Ophir and return formatted value."""
    p = ophir.read(n_avg=int(n_avg))
    if abs(p) < 1e-6:
        val_str = f"{p * 1e9:.1f}"
        unit = "nW"
    elif abs(p) < 1e-3:
        val_str = f"{p * 1e6:.2f}"
        unit = "uW"
    elif abs(p) < 1.0:
        val_str = f"{p * 1e3:.3f}"
        unit = "mW"
    else:
        val_str = f"{p:.4f}"
        unit = "W"
    return p, val_str, unit


def power_metric(label: str, val_str: str, unit: str):
    """Display power as a Streamlit metric."""
    st.metric(label, f"{val_str} {unit}")


# ── Progress ──────────────────────────────────────────────────────────────────
with aw_panel():
    progress_pct = z_idx / total_z if total_z > 0 else 0
    c1, c2 = st.columns(2)
    c1.metric("Z Position", f"{z_idx}/{total_z}")
    c2.metric("Step", st.session_state.m2_step.upper())
    st.progress(progress_pct)


# ── Main scan workflow ────────────────────────────────────────────────────────
if z_idx >= total_z:
    st.session_state.m2_step = "done"

step = st.session_state.m2_step

# ── IDLE: Start scan ─────────────────────────────────────────────────────
if step == "idle":
    with aw_panel():
        st.info(f"Ready to scan {total_z} Z positions from {z_start:.1f} to {z_stop:.1f} mm.")

        st.markdown("#### Live Power Reading")
        col_power, col_btn = st.columns([3, 1])
        with col_btn:
            if st.button("Read Power", use_container_width=True):
                pass
        with col_power:
            p, val_str, unit = read_and_display_power()
            power_metric("Current Reading", val_str, unit)

        if st.button("Start Scan", type="primary", use_container_width=True):
            st.session_state.m2_step = "ref"
            st.session_state.m2_z_idx = 0
            st.session_state.m2_results = []
            st.session_state.m2_all_z = []
            st.session_state.m2_all_w = []
            smc.move_to(z_positions[0])
            st.rerun()

# ── REF: Full-power reference ────────────────────────────────────────────
elif step == "ref":
    z_target = z_positions[z_idx]
    z_actual = smc.get_position()

    with aw_panel():
        st.metric("Current Z", f"{z_actual:.3f} mm ({z_idx + 1}/{total_z})")
        st.markdown("#### Step 1: Full-Power Reference")
        st.markdown("Remove the knife edge from the beam path, then click **Read Full Power**.")

        col_power, col_btn = st.columns([3, 1])
        with col_btn:
            if st.button("Refresh", key="ref_refresh", use_container_width=True):
                pass
        with col_power:
            p, val_str, unit = read_and_display_power()
            power_metric("Live Power", val_str, unit)

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            if st.button("Read Full Power", type="primary", use_container_width=True):
                P_full = ophir.read(n_avg=int(n_avg))
                if P_full < 1e-12:
                    st.error(f"Power too low ({P_full:.2e}). Check beam alignment.")
                else:
                    st.session_state.m2_P_full = P_full
                    st.session_state.m2_step = "clip16"
                    st.rerun()
        with col3:
            if st.button("Skip Z", use_container_width=True):
                st.session_state.m2_z_idx += 1
                if st.session_state.m2_z_idx < total_z:
                    smc.move_to(z_positions[st.session_state.m2_z_idx])
                st.rerun()

# ── CLIP16: Move knife edge to 16% ──────────────────────────────────────
elif step == "clip16":
    z_actual = smc.get_position()
    P_full = st.session_state.m2_P_full
    P_16_target = 0.16 * P_full

    with aw_panel():
        st.metric("Current Z", f"{z_actual:.3f} mm ({z_idx + 1}/{total_z})")
        st.markdown("#### Step 2: Find 16% Clip Position")

        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Target 16%", f"{P_16_target:.4e}")
        col_t2.metric("Full Power P0", f"{P_full:.4e}")

        st.markdown("Move the knife edge until the power reads approximately the **16% target** value.")

        col_power, col_btn = st.columns([3, 1])
        with col_btn:
            if st.button("Refresh", key="c16_refresh", use_container_width=True):
                pass
        with col_power:
            p, val_str, unit = read_and_display_power()
            ratio = p / P_full if P_full > 0 else 0
            power_metric(f"Live Power ({ratio * 100:.1f}%)", val_str, unit)

        x_16_input = st.number_input(
            "Knife-edge X position (mm):", value=0.0, format="%.4f", key="x16_input"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Record 16% Position", type="primary", use_container_width=True):
                P_16_actual = ophir.read(n_avg=int(n_avg))
                st.session_state.m2_x16 = x_16_input
                st.session_state.m2_P16 = P_16_actual
                st.session_state.m2_step = "clip84"
                st.rerun()
        with col2:
            if st.button("Skip Z", key="skip16", use_container_width=True):
                st.session_state.m2_z_idx += 1
                st.session_state.m2_step = "ref"
                if st.session_state.m2_z_idx < total_z:
                    smc.move_to(z_positions[st.session_state.m2_z_idx])
                st.rerun()

# ── CLIP84: Move knife edge to 84% ──────────────────────────────────────
elif step == "clip84":
    z_actual = smc.get_position()
    P_full = st.session_state.m2_P_full
    P_84_target = 0.84 * P_full

    with aw_panel():
        st.metric("Current Z", f"{z_actual:.3f} mm ({z_idx + 1}/{total_z})")
        st.markdown("#### Step 3: Find 84% Clip Position")

        col_t1, col_t2 = st.columns(2)
        col_t1.metric("Target 84%", f"{P_84_target:.4e}")
        col_t2.metric("16% Recorded", f"x = {st.session_state.m2_x16:.4f} mm")

        st.markdown("Move the knife edge until the power reads approximately the **84% target** value.")

        col_power, col_btn = st.columns([3, 1])
        with col_btn:
            if st.button("Refresh", key="c84_refresh", use_container_width=True):
                pass
        with col_power:
            p, val_str, unit = read_and_display_power()
            ratio = p / P_full if P_full > 0 else 0
            power_metric(f"Live Power ({ratio * 100:.1f}%)", val_str, unit)

        x_84_input = st.number_input(
            "Knife-edge X position (mm):", value=0.0, format="%.4f", key="x84_input"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Record 84% Position", type="primary", use_container_width=True):
                P_84_actual = ophir.read(n_avg=int(n_avg))
                x_16 = st.session_state.m2_x16
                x_84 = x_84_input
                P_16 = st.session_state.m2_P16

                d_clip = abs(x_84 - x_16)
                w_um = d_clip / np.sqrt(2) * 1000.0

                st.session_state.m2_all_z.append(z_actual * 1000.0)
                st.session_state.m2_all_w.append(w_um)
                st.session_state.m2_results.append({
                    "z_mm": z_actual, "P_full": P_full,
                    "x_16": x_16, "P_16": P_16,
                    "x_84": x_84, "P_84": P_84_actual,
                    "w_um": w_um,
                })

                st.session_state.m2_z_idx += 1
                if st.session_state.m2_z_idx < total_z:
                    smc.move_to(z_positions[st.session_state.m2_z_idx])
                    st.session_state.m2_step = "ref"
                else:
                    st.session_state.m2_step = "done"
                st.rerun()
        with col2:
            if st.button("Skip Z", key="skip84", use_container_width=True):
                st.session_state.m2_z_idx += 1
                st.session_state.m2_step = "ref"
                if st.session_state.m2_z_idx < total_z:
                    smc.move_to(z_positions[st.session_state.m2_z_idx])
                st.rerun()

# ── DONE: Fit and display results ────────────────────────────────────────
elif step == "done":
    with aw_panel():
        st.markdown("#### Scan Complete")

        results = st.session_state.m2_results
        if results:
            st.markdown("##### Measured Beam Radii")
            import pandas as pd

            df = pd.DataFrame(results)
            st.dataframe(
                df[["z_mm", "w_um", "x_16", "x_84"]],
                use_container_width=True,
            )

    all_z = st.session_state.m2_all_z
    all_w = st.session_state.m2_all_w

    if len(all_z) >= 3:
        from utils.analysis import fit_caustic

        fit = fit_caustic(all_z, all_w, wavelength)
        if fit:
            st.session_state.fit_result = fit
            st.session_state.scan_data = {"z_um": all_z, "w_um": all_w, "raw": results}

            with aw_panel():
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("w0 (um)", f"{fit['w0']:.2f}", f"+/- {fit['w0_err']:.2f}")
                c2.metric("M-squared", f"{fit['M2']:.2f}", f"+/- {fit['M2_err']:.2f}")
                c3.metric("z_R (um)", f"{fit['z_R']:.0f}")
                c4.metric("z0 (um)", f"{fit['z0']:.0f}", f"+/- {fit['z0_err']:.0f}")

            with aw_panel():
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=fit["z_data"], y=fit["w_data"], mode="markers",
                    name="Data", marker=dict(color=BRAND["accent"], size=8),
                ))
                fig.add_trace(go.Scatter(
                    x=fit["z_data"], y=[-w for w in fit["w_data"]], mode="markers",
                    showlegend=False, marker=dict(color=BRAND["accent"], size=8),
                ))
                fig.add_trace(go.Scatter(
                    x=fit["z_fit"], y=fit["w_fit"], mode="lines",
                    name="Fit", line=dict(color=BRAND["primary"], width=2),
                ))
                fig.add_trace(go.Scatter(
                    x=fit["z_fit"], y=[-w for w in fit["w_fit"]], mode="lines",
                    showlegend=False, line=dict(color=BRAND["primary"], width=2),
                ))
                fig.update_layout(
                    xaxis_title="Z position (um)",
                    yaxis_title="Beam radius (um)",
                    title=f"Beam Caustic -- M-squared = {fit['M2']:.2f}",
                    height=450,
                )
                st.plotly_chart(fig, width="stretch")

            st.markdown("View detailed analysis on the **Results & Analysis** page.")
        else:
            st.error("Caustic fit failed. Check data quality.")
    else:
        st.warning(f"Need at least 3 Z slices for caustic fit (got {len(all_z)}).")

    if st.button("New Scan", type="primary", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()
