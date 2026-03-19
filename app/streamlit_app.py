"""
streamlit_app.py — Automation Station
Main dashboard with hardware status and mode selection.
"""
import streamlit as st
from automation_station.ui.layout import render_header
from automation_station.ui.branding import hw_panel, BRAND
from automation_station.ui.access import is_admin
from automation_station.io.config import load_config

st.set_page_config(
    page_title="Automation Station",
    page_icon="\U0001f52c",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header()

cfg = load_config()

# ── Hardware Status ──────────────────────────────────────────────
with hw_panel():
    st.subheader("Hardware Status")
    if cfg.hardware_profiles:
        cols = st.columns(min(len(cfg.hardware_profiles), 4))
        for i, hp in enumerate(cfg.hardware_profiles):
            with cols[i % 4]:
                status = "\u2705 Online" if hp.enabled else "\u26a0\ufe0f Disabled"
                st.metric(
                    label=hp.name,
                    value=hp.device_type.upper(),
                    delta=f"{hp.port} \u2022 {status}",
                )
    else:
        st.info(
            "No hardware configured. "
            + ("Go to **Admin \u2192 Hardware** to add devices."
               if is_admin()
               else "Ask an admin to configure hardware.")
        )

# ── Mode Selection ───────────────────────────────────────────────
with hw_panel():
    st.subheader("Scan Modes")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### \U0001f916 Full Auto")
        st.caption(
            "Automated knife-edge scan with stage control and power meter reading. "
            "Set parameters and let the system run."
        )
        st.page_link("pages/1_Full_Auto.py", label="Launch Full Auto", icon="\u25b6\ufe0f")
    with col2:
        st.markdown("### \U0001f579\ufe0f Semi Auto")
        st.caption(
            "Step-by-step guided scan. You control the stage manually; "
            "the app reads and records power at each position."
        )
        st.page_link("pages/2_Semi_Auto.py", label="Launch Semi Auto", icon="\u25b6\ufe0f")
    with col3:
        st.markdown("### \u270d\ufe0f Minimal")
        st.caption(
            "Manual data entry mode. Paste or type position/power data "
            "and run the beam profile analysis."
        )
        st.page_link("pages/3_Minimal.py", label="Launch Minimal", icon="\u25b6\ufe0f")

# ── Quick Links ──────────────────────────────────────────────────
with hw_panel():
    st.subheader("Quick Links")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.page_link("pages/4_Results.py", label="\U0001f4ca Results", icon="\U0001f4ca")
    with col2:
        st.page_link("pages/5_Settings.py", label="\u2699\ufe0f Settings", icon="\u2699\ufe0f")
    with col3:
        st.page_link("pages/6_Gnuplot.py", label="\U0001f4c8 Gnuplot", icon="\U0001f4c8")
    with col4:
        if is_admin():
            st.page_link("pages/7_Admin.py", label="\U0001f512 Admin", icon="\U0001f512")
        else:
            st.caption("\U0001f512 Admin (login required)")

# ── Footer ───────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Automation Station v1.0.0 \u2022 "
    "Harrington Lab \u2022 "
    "Built with Streamlit"
)
