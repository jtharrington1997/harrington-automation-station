"""
pages/5_Settings.py -- Hardware & Scan Settings
"""
from __future__ import annotations

import streamlit as st

from automation_station.ui.layout import render_header
from harrington_common.theme import aw_panel

st.set_page_config(page_title="Settings", layout="wide")
render_header()

with aw_panel():
    st.subheader("Settings")
    st.caption("Hardware configuration. Scan defaults. Connection parameters.")

with aw_panel():
    st.markdown("#### Newport SMC100 (Z-Axis)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input(
            "COM Port", value="COM3", key="cfg_smc_port",
            help="Check Windows Device Manager for the correct port.",
        )
    with col2:
        st.number_input("Controller Axis", value=1, min_value=1, max_value=4, key="cfg_smc_axis")
    with col3:
        st.number_input("Velocity (mm/s)", value=2.5, step=0.5, format="%.1f", key="cfg_smc_vel")

with aw_panel():
    st.markdown("#### Thorlabs KDC101 (X-Axis Knife Edge)")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input(
            "Serial Number", value="27266790", key="cfg_kdc_serial",
            help="Found on the back of the KDC101 controller.",
        )
    with col2:
        st.selectbox(
            "Actuator", ["Z825B (25mm)", "Z812B (12mm)", "MTS25-Z8", "MTS50-Z8"],
            key="cfg_kdc_actuator",
            help="Must match what's set in the Kinesis GUI.",
        )

with aw_panel():
    st.markdown("#### Ophir StarBright (Power Meter)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input(
            "Readings per measurement", value=3, min_value=1, max_value=20, key="cfg_ophir_avg"
        )
    with col2:
        st.number_input(
            "Read delay (s)", value=0.2, step=0.05, format="%.2f", key="cfg_ophir_delay"
        )

with aw_panel():
    st.markdown("#### Beam / Laser")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input(
            "Wavelength (um)", value=2.94, step=0.01, format="%.3f",
            key="cfg_wavelength",
            help="Used for M-squared and Rayleigh range calculations.",
        )
    with col2:
        st.text_input("Laser ID / Notes", value="Er:YAG MIR", key="cfg_laser_notes")

with aw_panel():
    st.markdown("#### Hardware Status")

    ophir = st.session_state.get("hw_ophir")
    smc = st.session_state.get("hw_smc")
    kdc = st.session_state.get("hw_kdc")

    col1, col2, col3 = st.columns(3)
    with col1:
        if ophir and ophir.available:
            st.success("Ophir: Connected")
            if st.button("Disconnect Ophir"):
                ophir.disconnect()
                st.session_state.hw_ophir = None
                st.rerun()
        else:
            st.warning("Ophir: Disconnected")

    with col2:
        if smc and smc.available:
            st.success(f"SMC100: Connected ({smc.get_position():.3f} mm)")
            if st.button("Disconnect SMC100"):
                smc.disconnect()
                st.session_state.hw_smc = None
                st.rerun()
        else:
            st.warning("SMC100: Disconnected")

    with col3:
        if kdc and kdc.available:
            st.success(f"KDC101: Connected ({kdc.get_position():.3f} mm)")
            if st.button("Disconnect KDC101"):
                kdc.disconnect()
                st.session_state.hw_kdc = None
                st.rerun()
        else:
            st.warning("KDC101: Disconnected")

    st.info(
        "Settings on this page are for reference. To persist changes, "
        "update the configuration in the Admin page."
    )
