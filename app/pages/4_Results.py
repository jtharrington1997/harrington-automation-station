"""
pages/4_Results.py — Results & Analysis
Beam caustic plot, parameter table, data export.
"""

import streamlit as st
import numpy as np
import csv
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Results & Analysis", page_icon="📊", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
    .param-table {
        font-family: 'JetBrains Mono', monospace;
        width: 100%;
        border-collapse: collapse;
    }
    .param-table th {
        background: #161B22;
        color: #8B949E;
        text-align: left;
        padding: 8px 12px;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-bottom: 1px solid #30363D;
    }
    .param-table td {
        padding: 10px 12px;
        border-bottom: 1px solid #21262D;
        color: #C9D1D9;
        font-size: 0.9rem;
    }
    .param-table td:nth-child(2) {
        color: #E63946;
        font-weight: 600;
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background: linear-gradient(135deg, #0D1117, #161B22);
            border: 1px solid #30363D; border-left: 4px solid #3FB950;
            border-radius: 8px; padding: 1.5rem 2rem; margin-bottom: 1.5rem;">
    <h2 style="font-family: 'JetBrains Mono', monospace; color: #E6EDF3; margin: 0 0 0.3rem 0;">
        RESULTS &amp; ANALYSIS
    </h2>
    <p style="color: #8B949E; font-size: 0.9rem; margin: 0;">
        Beam caustic fit · Parameter extraction · Data export
    </p>
</div>
""", unsafe_allow_html=True)

fit = st.session_state.get("fit_result")
scan = st.session_state.get("scan_data")

if not fit:
    st.info("No scan results yet. Run a scan from one of the mode pages.")
    st.stop()

# ── Parameter Table ───────────────────────────────────────────────────────────
st.markdown("### Beam Parameters")
st.markdown(f"""
<table class="param-table">
    <tr><th>Parameter</th><th>Value</th><th>Uncertainty</th><th>Unit</th></tr>
    <tr><td>Beam waist w₀</td><td>{fit['w0']:.2f}</td><td>± {fit['w0_err']:.2f}</td><td>µm</td></tr>
    <tr><td>Waist position z₀</td><td>{fit['z0']:.0f}</td><td>± {fit['z0_err']:.0f}</td><td>µm</td></tr>
    <tr><td>M² factor</td><td>{fit['M2']:.2f}</td><td>± {fit['M2_err']:.2f}</td><td>—</td></tr>
    <tr><td>Rayleigh range z_R</td><td>{fit['z_R']:.0f}</td><td>—</td><td>µm</td></tr>
    <tr><td>Wavelength λ</td><td>{fit['wavelength']}</td><td>—</td><td>µm</td></tr>
    <tr><td>Beam diameter 2w₀</td><td>{2*fit['w0']:.2f}</td><td>± {2*fit['w0_err']:.2f}</td><td>µm</td></tr>
    <tr><td>Divergence θ</td><td>{fit['M2']*fit['wavelength']/(np.pi*fit['w0'])*1000:.2f}</td>
        <td>—</td><td>mrad</td></tr>
</table>
""", unsafe_allow_html=True)

# ── Beam Caustic Plot ─────────────────────────────────────────────────────────
st.markdown("### Beam Caustic")

fig = make_subplots(rows=1, cols=1)
fig.add_trace(go.Scatter(
    x=fit["z_data"], y=fit["w_data"], mode="markers",
    name="Measured w(z)", marker=dict(color="#E63946", size=10, symbol="circle")))
fig.add_trace(go.Scatter(
    x=fit["z_data"], y=-fit["w_data"], mode="markers",
    showlegend=False, marker=dict(color="#E63946", size=10, symbol="circle")))
fig.add_trace(go.Scatter(
    x=fit["z_fit"], y=fit["w_fit"], mode="lines",
    name="Hyperbolic fit", line=dict(color="#388BFD", width=2.5)))
fig.add_trace(go.Scatter(
    x=fit["z_fit"], y=-fit["w_fit"], mode="lines",
    showlegend=False, line=dict(color="#388BFD", width=2.5)))
# Waist marker
fig.add_hline(y=fit["w0"], line_dash="dash", line_color="#3FB950",
              annotation_text=f"w₀ = {fit['w0']:.1f} µm",
              annotation_font_color="#3FB950")
fig.add_hline(y=-fit["w0"], line_dash="dash", line_color="#3FB950")
fig.add_vline(x=fit["z0"], line_dash="dot", line_color="#8B949E",
              annotation_text=f"z₀ = {fit['z0']:.0f} µm",
              annotation_font_color="#8B949E")
fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0D1117", plot_bgcolor="#0D1117",
    xaxis_title="Z position (µm)",
    yaxis_title="Beam radius w (µm)",
    title=dict(text=f"Beam Caustic — M² = {fit['M2']:.2f}, w₀ = {fit['w0']:.1f} µm",
               font=dict(family="JetBrains Mono", size=16)),
    font=dict(family="JetBrains Mono, monospace", size=12),
    height=500,
    legend=dict(x=0.02, y=0.98),
)
st.plotly_chart(fig, use_container_width=True)

# ── Residuals ─────────────────────────────────────────────────────────────────
if len(fit["z_data"]) > 0:
    from utils.analysis import beam_caustic
    w_predicted = beam_caustic(fit["z_data"], fit["w0"], fit["z0"], fit["M2"],
                                fit["wavelength"])
    residuals = fit["w_data"] - w_predicted

    st.markdown("### Fit Residuals")
    fig_res = go.Figure()
    fig_res.add_trace(go.Bar(
        x=fit["z_data"], y=residuals,
        marker_color=["#3FB950" if abs(r) < fit["w0"]*0.05 else "#E63946"
                       for r in residuals],
    ))
    fig_res.add_hline(y=0, line_color="#8B949E", line_width=1)
    fig_res.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0D1117", plot_bgcolor="#0D1117",
        xaxis_title="Z position (µm)",
        yaxis_title="Residual (µm)",
        height=250,
        font=dict(family="JetBrains Mono, monospace"),
        showlegend=False,
    )
    st.plotly_chart(fig_res, use_container_width=True)

# ── Data Export ───────────────────────────────────────────────────────────────
st.markdown("### Export Data")

col1, col2 = st.columns(2)

with col1:
    # Results CSV
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["parameter", "value", "uncertainty", "unit"])
    wr.writerow(["w0", f"{fit['w0']:.4f}", f"{fit['w0_err']:.4f}", "um"])
    wr.writerow(["z0", f"{fit['z0']:.2f}", f"{fit['z0_err']:.2f}", "um"])
    wr.writerow(["M_squared", f"{fit['M2']:.4f}", f"{fit['M2_err']:.4f}", ""])
    wr.writerow(["z_R", f"{fit['z_R']:.2f}", "", "um"])
    wr.writerow(["wavelength", f"{fit['wavelength']}", "", "um"])
    st.download_button("Download Results CSV", buf.getvalue(),
                       "beam_caustic_results.csv", "text/csv",
                       use_container_width=True)

with col2:
    # Raw data CSV
    buf2 = io.StringIO()
    wr2 = csv.writer(buf2)
    wr2.writerow(["z_um", "w_um"])
    for z, w in zip(fit["z_data"], fit["w_data"]):
        wr2.writerow([f"{z:.2f}", f"{w:.2f}"])
    st.download_button("Download Raw Data CSV", buf2.getvalue(),
                       "beam_radii_raw.csv", "text/csv",
                       use_container_width=True)
