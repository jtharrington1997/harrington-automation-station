"""
pages/7_Admin.py — Admin Dashboard
Hardware config, API keys, and system settings behind admin auth.
"""
import json

import streamlit as st
from automation_station.ui.layout import render_header
from automation_station.ui.branding import hw_panel
from automation_station.ui.access import require_admin, set_admin_password, admin_logout
from automation_station.io.config import DEFAULT_CONFIG_PATH, load_config, save_config

st.set_page_config(page_title="Admin", layout="wide")
render_header()

if not require_admin():
    st.stop()

cfg = load_config()

# ── Logout button ──
with st.sidebar:
    if st.button("Logout admin"):
        admin_logout()
        st.rerun()

# ── Tabs ──
tab_hardware, tab_api, tab_analysis, tab_password = st.tabs(
    ["Hardware", "API Keys", "Analysis Defaults", "Change Password"]
)

# ═══════════════════════════════════════════════════════════════════
# TAB: HARDWARE
# ═══════════════════════════════════════════════════════════════════
with tab_hardware:
    with hw_panel():
        st.subheader("Hardware Detection")
        auto_detect = st.checkbox(
            "Auto-detect connected devices on startup",
            value=cfg.auto_detect_hardware,
        )
        scan_timeout = st.number_input(
            "Scan timeout (seconds)",
            min_value=5.0,
            max_value=120.0,
            value=cfg.scan_timeout_s,
            step=5.0,
        )

    with hw_panel():
        st.subheader("Saved Hardware Profiles")
        st.caption("Manually configure known devices. Auto-detect will populate this list.")

        profiles = []
        for i, hp in enumerate(cfg.hardware_profiles):
            st.markdown(f"**Device {i + 1}**")
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                name = st.text_input("Name", value=hp.name, key=f"hp_name_{i}")
            with col2:
                device_type = st.selectbox(
                    "Type",
                    ["smc100", "kdc101", "ophir", "newport_pm", "custom"],
                    index=["smc100", "kdc101", "ophir", "newport_pm", "custom"].index(
                        hp.device_type
                    )
                    if hp.device_type
                    in ["smc100", "kdc101", "ophir", "newport_pm", "custom"]
                    else 4,
                    key=f"hp_type_{i}",
                )
            with col3:
                port = st.text_input("Port", value=hp.port, key=f"hp_port_{i}")
            col4, col5 = st.columns(2)
            with col4:
                baud = st.number_input(
                    "Baud rate", value=hp.baud_rate, key=f"hp_baud_{i}"
                )
            with col5:
                enabled = st.checkbox("Enabled", value=hp.enabled, key=f"hp_en_{i}")
            profiles.append(
                {
                    "name": name.strip(),
                    "device_type": device_type,
                    "port": port.strip(),
                    "baud_rate": int(baud),
                    "enabled": enabled,
                }
            )
            st.markdown("---")

        st.caption("Add a new device:")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            new_name = st.text_input("Name", value="", key="new_hp_name")
        with col2:
            new_type = st.selectbox(
                "Type",
                ["smc100", "kdc101", "ophir", "newport_pm", "custom"],
                key="new_hp_type",
            )
        with col3:
            new_port = st.text_input("Port", value="", key="new_hp_port")

# ═══════════════════════════════════════════════════════════════════
# TAB: API KEYS
# ═══════════════════════════════════════════════════════════════════
with tab_api:
    with hw_panel():
        st.subheader("API Keys")
        st.caption("Used for AI-assisted analysis and reporting.")
        anthropic_key = st.text_input(
            "Anthropic API key",
            value=cfg.anthropic_api_key or "",
            type="password",
        )
        openai_key = st.text_input(
            "OpenAI API key",
            value=cfg.openai_api_key or "",
            type="password",
        )

# ═══════════════════════════════════════════════════════════════════
# TAB: ANALYSIS DEFAULTS
# ═══════════════════════════════════════════════════════════════════
with tab_analysis:
    with hw_panel():
        st.subheader("Default Parameters")
        wavelength = st.number_input(
            "Default wavelength (nm)",
            min_value=100.0,
            max_value=20000.0,
            value=cfg.default_wavelength_nm,
            step=1.0,
        )
        step_size = st.number_input(
            "Default step size (\u03bcm)",
            min_value=0.1,
            max_value=1000.0,
            value=cfg.default_step_size_um,
            step=0.5,
        )
        fit_method = st.selectbox(
            "Fit method",
            ["least_squares", "curve_fit"],
            index=["least_squares", "curve_fit"].index(cfg.fit_method),
        )

# ═══════════════════════════════════════════════════════════════════
# TAB: CHANGE PASSWORD
# ═══════════════════════════════════════════════════════════════════
with tab_password:
    with hw_panel():
        st.subheader("Change Admin Password")
        old_pw = st.text_input("Current password", type="password", key="old_pw")
        new_pw = st.text_input("New password", type="password", key="new_pw")
        confirm = st.text_input("Confirm new password", type="password", key="confirm_pw")
        if st.button("Update password", type="primary"):
            if not old_pw or not new_pw:
                st.error("Fill in all fields.")
            elif new_pw != confirm:
                st.error("New passwords don't match.")
            elif len(new_pw) < 8:
                st.error("Password must be at least 8 characters.")
            elif set_admin_password(old_pw, new_pw):
                st.success("Password updated.")
            else:
                st.error("Current password is incorrect.")

# ═══════════════════════════════════════════════════════════════════
# SAVE ALL
# ═══════════════════════════════════════════════════════════════════
st.markdown("---")
if st.button("Save all settings", type="primary"):
    from automation_station.io.config import AppConfig, HardwareProfile

    hw_list = [
        HardwareProfile(**p) for p in profiles if p["port"]
    ]
    if new_port.strip():
        hw_list.append(
            HardwareProfile(
                name=new_name.strip() or "Unnamed",
                device_type=new_type,
                port=new_port.strip(),
            )
        )

    new_cfg = AppConfig(
        hardware_profiles=hw_list,
        auto_detect_hardware=auto_detect,
        scan_timeout_s=scan_timeout,
        anthropic_api_key=anthropic_key.strip() or None,
        openai_api_key=openai_key.strip() or None,
        cache_dir=cfg.cache_dir,
        results_dir=cfg.results_dir,
        default_wavelength_nm=wavelength,
        default_step_size_um=step_size,
        fit_method=fit_method,
    )
    save_config(new_cfg)
    st.success("Configuration saved.")
    st.rerun()
