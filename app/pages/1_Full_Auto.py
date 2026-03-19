"""
pages/1_Full_Auto.py -- Fully Automated Knife-Edge Scan
All three devices automated. Press start and walk away.
"""
from __future__ import annotations

import time
from datetime import datetime

import numpy as np
import streamlit as st

from automation_station.ui.layout import render_header
from harrington_common.theme import aw_panel

st.set_page_config(page_title="Full Auto", layout="wide")
render_header()

with aw_panel():
    st.subheader("Mode 1: Full Auto")
    st.caption("Z stage + knife-edge stage + power meter all automated. Hands-free operation.")

# Check hardware
ophir = st.session_state.get("hw_ophir")
smc = st.session_state.get("hw_smc")
kdc = st.session_state.get("hw_kdc")

missing = []
if not ophir or not ophir.available:
    missing.append("Ophir StarBright")
if not smc or not smc.available:
    missing.append("Newport SMC100")
if not kdc or not kdc.available:
    missing.append("Thorlabs KDC101")

if missing:
    st.error(f"Missing hardware: **{', '.join(missing)}**. Go to Dashboard to connect.")
    st.stop()

# Settings
with st.sidebar:
    st.markdown("#### Scan Parameters")
    z_start = st.number_input("Z start (mm)", value=0.0, step=1.0)
    z_stop = st.number_input("Z stop (mm)", value=50.0, step=1.0)
    z_steps = st.number_input("Z steps", value=11, min_value=3, step=1)
    x_clear = st.number_input("X clear (mm)", value=0.0, step=0.5)
    x_start = st.number_input("X sweep start (mm)", value=2.0, step=0.5)
    x_stop = st.number_input("X sweep stop (mm)", value=23.0, step=0.5)
    x_steps = st.number_input("X sweep points", value=50, min_value=10, step=5)
    x_settle = st.number_input("X settle time (s)", value=0.3, step=0.1, format="%.1f")
    wavelength = st.number_input("Wavelength (um)", value=2.94, step=0.01, format="%.3f")
    n_avg = st.number_input("Ophir averages", value=3, min_value=1, step=1)

z_positions = np.linspace(z_start, z_stop, int(z_steps))
x_positions = np.linspace(x_start, x_stop, int(x_steps))

with aw_panel():
    st.info(
        f"Will scan **{int(z_steps)}** Z positions x **{int(x_steps)}** X points = "
        f"**{int(z_steps * x_steps)}** total measurements."
    )

    if st.button("Start Full Auto Scan", type="primary", use_container_width=True):
        from utils.analysis import find_clip_positions, fit_caustic

        all_z, all_w = [], []
        progress = st.progress(0, text="Initializing...")
        status = st.empty()
        log_area = st.empty()

        total = len(z_positions)
        for z_idx, z_target in enumerate(z_positions):
            progress.progress(z_idx / total, text=f"Z {z_idx + 1}/{total}: {z_target:.3f} mm")

            # Move Z
            status.markdown(f"**Moving Z -> {z_target:.3f} mm...**")
            smc.move_to(z_target)
            z_actual = smc.get_position()

            # Full power reference
            status.markdown(f"**Z = {z_actual:.3f} mm -- Reading full power (knife retracted)...**")
            kdc.move_to(x_clear)
            time.sleep(float(x_settle))
            P_full = ophir.read(n_avg=int(n_avg))
            if P_full < 1e-12:
                status.warning(f"Z = {z_actual:.3f} mm -- Power too low, skipping.")
                continue

            # Sweep
            powers = []
            for x_idx, x_pos in enumerate(x_positions):
                kdc.move_to(x_pos)
                time.sleep(float(x_settle))
                p = ophir.read(n_avg=int(n_avg))
                powers.append(p)
                if x_idx % 10 == 0:
                    status.markdown(
                        f"**Z = {z_actual:.3f} mm -- Sweeping X: "
                        f"{x_idx + 1}/{int(x_steps)} (P = {p:.4e})**"
                    )

            # Analyze
            p_arr = np.array(powers)
            x_16, x_84 = find_clip_positions(x_positions, p_arr, P_full)
            if x_16 is not None and x_84 is not None:
                w_um = abs(x_84 - x_16) / np.sqrt(2) * 1000.0
                all_z.append(z_actual * 1000.0)
                all_w.append(w_um)
                log_area.markdown(
                    f"Z = {z_actual:.3f} mm -> **w = {w_um:.1f} um** "
                    f"(x16 = {x_16:.3f}, x84 = {x_84:.3f})"
                )

            kdc.move_to(x_clear)

        progress.progress(1.0, text="Scan complete!")

        # Fit
        if len(all_z) >= 3:
            fit = fit_caustic(all_z, all_w, float(wavelength))
            if fit:
                st.session_state.fit_result = fit
                st.session_state.scan_data = {"z_um": all_z, "w_um": all_w, "raw": []}
                st.success(
                    f"w0 = {fit['w0']:.2f} um  |  M-squared = {fit['M2']:.2f}  |  "
                    f"z_R = {fit['z_R']:.0f} um"
                )
                st.markdown("Go to **Results & Analysis** for detailed plots.")
            else:
                st.error("Caustic fit failed.")
        else:
            st.warning(f"Only {len(all_z)} valid Z slices -- need at least 3.")
