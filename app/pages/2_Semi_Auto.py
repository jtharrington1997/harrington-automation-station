"""
pages/2_Semi_Auto.py — Semi-Automated Knife-Edge Scan
Z stage automated, Ophir reads automatically, manual knife-edge positioning.
Features live power display to guide user to 16%/84% clip points.
"""

import streamlit as st
import numpy as np
import time
import csv
from datetime import datetime
import plotly.graph_objects as go


# ── Shared CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

    .power-display {
        background: #0D1117;
        border: 2px solid #30363D;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        margin: 1rem 0;
    }
    .power-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 3.5rem;
        font-weight: 700;
        color: #3FB950;
        line-height: 1.1;
    }
    .power-unit {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1rem;
        color: #8B949E;
    }
    .power-label {
        font-size: 0.8rem;
        color: #8B949E;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.3rem;
    }

    .target-display {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .target-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.5rem;
        font-weight: 600;
    }
    .target-label {
        font-size: 0.75rem;
        color: #8B949E;
        text-transform: uppercase;
    }
    .target-16 { color: #D29922; }
    .target-84 { color: #388BFD; }

    .step-indicator {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #8B949E;
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        margin-bottom: 1rem;
    }
    .step-active {
        color: #E63946;
        font-weight: 600;
    }

    .z-badge {
        font-family: 'JetBrains Mono', monospace;
        background: #E63946;
        color: #fff;
        font-size: 0.8rem;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 0.5rem;
    }

    .result-row {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #C9D1D9;
    }

    .progress-bar-bg {
        background: #21262D;
        border-radius: 4px;
        height: 6px;
        width: 100%;
        margin: 0.5rem 0;
    }
    .progress-bar-fill {
        background: #E63946;
        border-radius: 4px;
        height: 6px;
        transition: width 0.3s;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "m2_step": "idle",       # idle, ref, clip16, clip84, done
    "m2_z_idx": 0,
    "m2_P_full": 0.0,
    "m2_results": [],        # list of dicts per Z slice
    "m2_all_z": [],
    "m2_all_w": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background: linear-gradient(135deg, #0D1117, #161B22, #1a0a0a);
            border: 1px solid #30363D; border-left: 4px solid #D29922;
            border-radius: 8px; padding: 1.5rem 2rem; margin-bottom: 1.5rem;">
    <h2 style="font-family: 'JetBrains Mono', monospace; color: #E6EDF3; margin: 0 0 0.3rem 0;">
        MODE 2: SEMI AUTO
    </h2>
    <p style="color: #8B949E; font-size: 0.9rem; margin: 0;">
        Z stage + power meter automated · Manual knife-edge positioning · Live power display
    </p>
</div>
""", unsafe_allow_html=True)


# ── Check hardware ────────────────────────────────────────────────────────────
ophir = st.session_state.get("hw_ophir")
smc = st.session_state.get("hw_smc")

if not ophir or not ophir.available:
    st.error("Ophir StarBright not connected. Go to Dashboard → Connect Ophir.")
    st.stop()
if not smc or not smc.available:
    st.error("Newport SMC100 not connected. Go to Dashboard → Connect SMC100.")
    st.stop()


# ── Settings sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("#### Scan Parameters")
    z_start = st.number_input("Z start (mm)", value=0.0, step=1.0)
    z_stop = st.number_input("Z stop (mm)", value=50.0, step=1.0)
    z_steps = st.number_input("Z steps", value=11, min_value=3, max_value=50, step=1)
    wavelength = st.number_input("Wavelength (µm)", value=2.94, step=0.01, format="%.3f")
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
    """Read Ophir and display the live value."""
    p = ophir.read(n_avg=int(n_avg))
    # Format with appropriate unit
    if abs(p) < 1e-6:
        val_str = f"{p*1e9:.1f}"
        unit = "nW"
    elif abs(p) < 1e-3:
        val_str = f"{p*1e6:.2f}"
        unit = "µW"
    elif abs(p) < 1.0:
        val_str = f"{p*1e3:.3f}"
        unit = "mW"
    else:
        val_str = f"{p:.4f}"
        unit = "W"
    return p, val_str, unit


# ── Progress ──────────────────────────────────────────────────────────────────
progress_pct = (z_idx / total_z * 100) if total_z > 0 else 0
st.markdown(f"""
<div class="step-indicator">
    Z Position: <span class="step-active">{z_idx}/{total_z}</span> &nbsp;·&nbsp;
    Step: <span class="step-active">{st.session_state.m2_step.upper()}</span>
</div>
<div class="progress-bar-bg">
    <div class="progress-bar-fill" style="width: {progress_pct}%"></div>
</div>
""", unsafe_allow_html=True)


# ── Main scan workflow ────────────────────────────────────────────────────────
if z_idx >= total_z:
    st.session_state.m2_step = "done"

step = st.session_state.m2_step

# ── IDLE: Start scan ─────────────────────────────────────────────────────
if step == "idle":
    st.info(f"Ready to scan {total_z} Z positions from {z_start:.1f} to {z_stop:.1f} mm.")

    # Live power preview
    st.markdown("#### Live Power Reading")
    col_power, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("Read Power", use_container_width=True):
            pass  # triggers rerun
    with col_power:
        p, val_str, unit = read_and_display_power()
        st.markdown(f"""
        <div class="power-display">
            <div class="power-value">{val_str}</div>
            <div class="power-unit">{unit}</div>
            <div class="power-label">Current Reading</div>
        </div>""", unsafe_allow_html=True)

    if st.button("Start Scan", type="primary", use_container_width=True):
        st.session_state.m2_step = "ref"
        st.session_state.m2_z_idx = 0
        st.session_state.m2_results = []
        st.session_state.m2_all_z = []
        st.session_state.m2_all_w = []
        # Move to first Z
        smc.move_to(z_positions[0])
        st.rerun()

# ── REF: Full-power reference ────────────────────────────────────────────
elif step == "ref":
    z_target = z_positions[z_idx]
    z_actual = smc.get_position()

    st.markdown(f'<div class="z-badge">Z = {z_actual:.3f} mm ({z_idx+1}/{total_z})</div>',
                unsafe_allow_html=True)
    st.markdown("#### Step 1: Full-Power Reference")
    st.markdown("Remove the knife edge from the beam path, then click **Read Full Power**.")

    col_power, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("Refresh", key="ref_refresh", use_container_width=True):
            pass
    with col_power:
        p, val_str, unit = read_and_display_power()
        st.markdown(f"""
        <div class="power-display">
            <div class="power-value">{val_str}</div>
            <div class="power-unit">{unit}</div>
            <div class="power-label">Live Power</div>
        </div>""", unsafe_allow_html=True)

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
    P_84_target = 0.84 * P_full

    st.markdown(f'<div class="z-badge">Z = {z_actual:.3f} mm ({z_idx+1}/{total_z})</div>',
                unsafe_allow_html=True)
    st.markdown("#### Step 2: Find 16% Clip Position")

    # Target display
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown(f"""
        <div class="target-display">
            <div class="target-label">Target 16%</div>
            <div class="target-val target-16">{P_16_target:.4e}</div>
        </div>""", unsafe_allow_html=True)
    with col_t2:
        st.markdown(f"""
        <div class="target-display">
            <div class="target-label">Full Power P₀</div>
            <div class="target-val" style="color: #3FB950;">{P_full:.4e}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("Move the knife edge until the power reads approximately the **16% target** value.")

    # Live power with color feedback
    col_power, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("Refresh", key="c16_refresh", use_container_width=True):
            pass
    with col_power:
        p, val_str, unit = read_and_display_power()
        ratio = p / P_full if P_full > 0 else 0
        if abs(ratio - 0.16) < 0.03:
            color = "#3FB950"  # green = on target
        elif abs(ratio - 0.16) < 0.08:
            color = "#D29922"  # yellow = close
        else:
            color = "#E63946"  # red = far
        st.markdown(f"""
        <div class="power-display" style="border-color: {color};">
            <div class="power-value" style="color: {color};">{val_str}</div>
            <div class="power-unit">{unit} ({ratio*100:.1f}%)</div>
            <div class="power-label">Move knife edge → target 16%</div>
        </div>""", unsafe_allow_html=True)

    x_16_input = st.number_input("Knife-edge X position (mm):", value=0.0,
                                  format="%.4f", key="x16_input")
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

    st.markdown(f'<div class="z-badge">Z = {z_actual:.3f} mm ({z_idx+1}/{total_z})</div>',
                unsafe_allow_html=True)
    st.markdown("#### Step 3: Find 84% Clip Position")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown(f"""
        <div class="target-display">
            <div class="target-label">Target 84%</div>
            <div class="target-val target-84">{P_84_target:.4e}</div>
        </div>""", unsafe_allow_html=True)
    with col_t2:
        st.markdown(f"""
        <div class="target-display">
            <div class="target-label">16% Recorded</div>
            <div class="target-val target-16">x = {st.session_state.m2_x16:.4f} mm</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("Move the knife edge until the power reads approximately the **84% target** value.")

    col_power, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("Refresh", key="c84_refresh", use_container_width=True):
            pass
    with col_power:
        p, val_str, unit = read_and_display_power()
        ratio = p / P_full if P_full > 0 else 0
        if abs(ratio - 0.84) < 0.03:
            color = "#3FB950"
        elif abs(ratio - 0.84) < 0.08:
            color = "#D29922"
        else:
            color = "#E63946"
        st.markdown(f"""
        <div class="power-display" style="border-color: {color};">
            <div class="power-value" style="color: {color};">{val_str}</div>
            <div class="power-unit">{unit} ({ratio*100:.1f}%)</div>
            <div class="power-label">Move knife edge → target 84%</div>
        </div>""", unsafe_allow_html=True)

    x_84_input = st.number_input("Knife-edge X position (mm):", value=0.0,
                                  format="%.4f", key="x84_input")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Record 84% Position", type="primary", use_container_width=True):
            P_84_actual = ophir.read(n_avg=int(n_avg))
            x_16 = st.session_state.m2_x16
            x_84 = x_84_input
            P_16 = st.session_state.m2_P16

            # Compute beam radius
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

            # Advance to next Z
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
    st.markdown("#### Scan Complete")

    results = st.session_state.m2_results
    if results:
        # Show collected data
        st.markdown("##### Measured Beam Radii")
        for r in results:
            st.markdown(f"""
            <div class="result-row">
                Z = {r['z_mm']:.3f} mm &nbsp;→&nbsp; w = {r['w_um']:.1f} µm
                &nbsp;·&nbsp; x₁₆ = {r['x_16']:.3f} &nbsp;·&nbsp; x₈₄ = {r['x_84']:.3f}
            </div>""", unsafe_allow_html=True)

    all_z = st.session_state.m2_all_z
    all_w = st.session_state.m2_all_w

    if len(all_z) >= 3:
        from utils.analysis import fit_caustic
        fit = fit_caustic(all_z, all_w, wavelength)
        if fit:
            st.session_state.fit_result = fit
            st.session_state.scan_data = {"z_um": all_z, "w_um": all_w, "raw": results}

            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("w₀ (µm)", f"{fit['w0']:.2f}", f"± {fit['w0_err']:.2f}")
            with c2:
                st.metric("M²", f"{fit['M2']:.2f}", f"± {fit['M2_err']:.2f}")
            with c3:
                st.metric("z_R (µm)", f"{fit['z_R']:.0f}")
            with c4:
                st.metric("z₀ (µm)", f"{fit['z0']:.0f}", f"± {fit['z0_err']:.0f}")

            # Caustic plot
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=fit["z_data"], y=fit["w_data"], mode="markers",
                name="Data", marker=dict(color="#E63946", size=8)))
            fig.add_trace(go.Scatter(
                x=fit["z_data"], y=-fit["w_data"], mode="markers",
                showlegend=False, marker=dict(color="#E63946", size=8)))
            fig.add_trace(go.Scatter(
                x=fit["z_fit"], y=fit["w_fit"], mode="lines",
                name="Fit", line=dict(color="#388BFD", width=2)))
            fig.add_trace(go.Scatter(
                x=fit["z_fit"], y=-fit["w_fit"], mode="lines",
                showlegend=False, line=dict(color="#388BFD", width=2)))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0D1117", plot_bgcolor="#0D1117",
                xaxis_title="Z position (µm)",
                yaxis_title="Beam radius (µm)",
                title=f"Beam Caustic — M² = {fit['M2']:.2f}",
                font=dict(family="JetBrains Mono, monospace"),
                height=450,
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("View detailed analysis on the **Results & Analysis** page.")
        else:
            st.error("Caustic fit failed. Check data quality.")
    else:
        st.warning(f"Need at least 3 Z slices for caustic fit (got {len(all_z)}).")

    if st.button("New Scan", type="primary", use_container_width=True):
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()
