"""
pages/3_Minimal.py -- Minimal Automation Scan
Z stage automated only. User types knife-edge position and power readings.
"""
from __future__ import annotations

import numpy as np
import streamlit as st

from automation_station.ui.layout import render_header
from harrington_common.theme import aw_panel

st.set_page_config(page_title="Minimal", layout="wide")
render_header()

with aw_panel():
    st.subheader("Mode 3: Minimal")
    st.caption("Z stage automated. Manual knife-edge positioning. Manual power readings.")

smc = st.session_state.get("hw_smc")
if not smc or not smc.available:
    st.error("Newport SMC100 not connected. Go to Dashboard to connect.")
    st.stop()

# Settings
with st.sidebar:
    st.markdown("#### Scan Parameters")
    z_start = st.number_input("Z start (mm)", value=0.0, step=1.0)
    z_stop = st.number_input("Z stop (mm)", value=50.0, step=1.0)
    z_steps = st.number_input("Z steps", value=11, min_value=3, step=1)
    wavelength = st.number_input("Wavelength (um)", value=2.94, step=0.01, format="%.3f")

z_positions = np.linspace(z_start, z_stop, int(z_steps))

# Session state
if "m3_data" not in st.session_state:
    st.session_state.m3_data = []

with aw_panel():
    st.markdown("#### Data Entry")
    st.markdown("The Z stage moves automatically. Enter your measurements below for each position.")

    # Current Z control
    col1, col2 = st.columns([3, 1])
    with col1:
        z_select = st.selectbox("Move Z to position:", [f"{z:.3f} mm" for z in z_positions])
    with col2:
        if st.button("Move Z", use_container_width=True):
            z_val = float(z_select.replace(" mm", ""))
            smc.move_to(z_val)
            st.success(f"Moved to Z = {smc.get_position():.3f} mm")

# Entry form
with aw_panel():
    with st.form("entry_form"):
        st.markdown("##### Record a measurement")
        z_actual = smc.get_position()
        st.markdown(f"**Current Z: {z_actual:.3f} mm**")

        c1, c2, c3 = st.columns(3)
        with c1:
            P_full = st.number_input(
                "Full power reading:", value=0.0, format="%.6e",
                help="Remove knife edge, read the meter display.",
            )
        with c2:
            x_16 = st.number_input("X at 16% (mm):", value=0.0, format="%.4f")
            P_16 = st.number_input("Power at 16%:", value=0.0, format="%.6e")
        with c3:
            x_84 = st.number_input("X at 84% (mm):", value=0.0, format="%.4f")
            P_84 = st.number_input("Power at 84%:", value=0.0, format="%.6e")

        submitted = st.form_submit_button(
            "Add Measurement", type="primary", use_container_width=True
        )
        if submitted:
            if P_full < 1e-12:
                st.error("Full power must be > 0.")
            else:
                d_clip = abs(x_84 - x_16)
                w_um = d_clip / np.sqrt(2) * 1000.0
                st.session_state.m3_data.append({
                    "z_mm": z_actual, "P_full": P_full,
                    "x_16": x_16, "P_16": P_16,
                    "x_84": x_84, "P_84": P_84,
                    "w_um": w_um,
                })
                st.success(f"Recorded: Z = {z_actual:.3f} mm -> w = {w_um:.1f} um")

# Show collected data
if st.session_state.m3_data:
    with aw_panel():
        st.markdown("#### Collected Data")
        import pandas as pd

        df = pd.DataFrame(st.session_state.m3_data)
        st.dataframe(df, use_container_width=True)

        if len(st.session_state.m3_data) >= 3:
            if st.button("Fit Beam Caustic", type="primary", use_container_width=True):
                from utils.analysis import fit_caustic

                all_z = [r["z_mm"] * 1000.0 for r in st.session_state.m3_data]
                all_w = [r["w_um"] for r in st.session_state.m3_data]
                fit = fit_caustic(all_z, all_w, float(wavelength))
                if fit:
                    st.session_state.fit_result = fit
                    st.session_state.scan_data = {
                        "z_um": all_z, "w_um": all_w,
                        "raw": st.session_state.m3_data,
                    }
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("w0 (um)", f"{fit['w0']:.2f}")
                    c2.metric("M-squared", f"{fit['M2']:.2f}")
                    c3.metric("z_R (um)", f"{fit['z_R']:.0f}")
                    c4.metric("z0 (um)", f"{fit['z0']:.0f}")
                    st.markdown("Go to **Results & Analysis** for detailed plots.")
                else:
                    st.error("Caustic fit failed.")

        if st.button("Clear All Data", use_container_width=True):
            st.session_state.m3_data = []
            st.rerun()
