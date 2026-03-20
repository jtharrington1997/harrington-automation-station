"""
pages/8_Digital_Twin_Compare.py -- Experimental vs Model Comparison

Upload or connect experimental data (beam profiles, damage measurements,
transmission scans) and overlay against LMI model predictions.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from automation_station.ui.layout import render_header
from harrington_common.theme import aw_panel

st.set_page_config(page_title="Digital Twin Compare", layout="wide")
render_header()

RESULTS_DIR = Path("data/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

PLOT_TEMPLATE = "plotly_dark"
PLOT_BG = "#0D1117"
PLOT_PAPER = "#161B22"


def plot_defaults() -> dict:
    return dict(
        template=PLOT_TEMPLATE,
        paper_bgcolor=PLOT_PAPER,
        plot_bgcolor=PLOT_BG,
    )


# ── Sidebar ───────────────────────────────────────────────────────

st.sidebar.header("Data Source")
data_mode = st.sidebar.radio(
    "Input mode",
    ["Upload CSV", "Manual Entry", "Load Previous"],
)

st.sidebar.subheader("Model Parameters")
st.sidebar.caption(
    "Enter the same parameters used in LMI Digital Twin "
    "for apples-to-apples comparison."
)
wavelength_nm = st.sidebar.number_input("Wavelength (nm)", value=8500.0, format="%.0f")
pulse_energy_uj = st.sidebar.number_input("Pulse energy (uJ)", value=20.0)
pulse_width_fs = st.sidebar.number_input("Pulse width (fs)", value=170.0)
spot_diameter_um = st.sidebar.number_input("Spot diameter (um)", value=200.0)
material_name = st.sidebar.text_input("Material", value="Silicon (Si)")
thickness_mm = st.sidebar.number_input("Thickness (mm)", value=0.1)

# Derived
import math

pulse_energy_j = pulse_energy_uj * 1e-6
pulse_width_s = pulse_width_fs * 1e-15
spot_radius_m = (spot_diameter_um * 1e-6) / 2
area_cm2 = math.pi * (spot_radius_m * 100) ** 2
peak_power = pulse_energy_j / pulse_width_s if pulse_width_s > 0 else 0
irradiance = peak_power / area_cm2 if area_cm2 > 0 else 0
fluence = pulse_energy_j / area_cm2 if area_cm2 > 0 else 0

# ── Header ────────────────────────────────────────────────────────

st.subheader("Experimental vs Model Comparison")

with aw_panel():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Material", material_name)
    c2.metric("Irradiance", f"{irradiance:.2e} W/cm2")
    c3.metric("Fluence", f"{fluence * 1000:.1f} mJ/cm2")
    c4.metric("Peak Power", f"{peak_power:.2e} W")

# ── Data Input ────────────────────────────────────────────────────

experimental_data: dict[str, pd.DataFrame] = {}

if data_mode == "Upload CSV":
    with aw_panel():
        st.subheader("Upload Experimental Data")
        st.caption(
            "Upload CSV files with columns appropriate to the measurement type. "
            "Supported: beam_profile (x_um, intensity), transmission (wavelength_nm, T), "
            "damage (fluence_mj_cm2, damage_diameter_um), temperature (time_us, T_K)."
        )

        uploaded = st.file_uploader(
            "Upload CSV(s)",
            type=["csv", "tsv"],
            accept_multiple_files=True,
        )

        for f in (uploaded or []):
            try:
                df = pd.read_csv(f)
                name = f.name.rsplit(".", 1)[0]
                experimental_data[name] = df
                st.success(f"Loaded {name}: {len(df)} rows, columns: {list(df.columns)}")
            except Exception as e:
                st.error(f"Failed to load {f.name}: {e}")

elif data_mode == "Manual Entry":
    with aw_panel():
        st.subheader("Manual Data Entry")

        mtype = st.selectbox(
            "Measurement type",
            ["Beam Profile", "Transmission", "Damage Threshold", "Temperature"],
        )

        if mtype == "Beam Profile":
            st.caption("Enter beam profile as x (um) vs intensity pairs.")
            n_pts = st.number_input("Number of points", 5, 200, 20)
            x_vals = st.text_area(
                "x positions (um, comma-separated)",
                value=", ".join(str(i * 20 - 200) for i in range(21)),
            )
            i_vals = st.text_area(
                "Intensity (a.u., comma-separated)",
                placeholder="0.01, 0.05, 0.15, ...",
            )
            if x_vals and i_vals:
                try:
                    x = [float(v.strip()) for v in x_vals.split(",")]
                    intensity = [float(v.strip()) for v in i_vals.split(",")]
                    experimental_data["beam_profile"] = pd.DataFrame({
                        "x_um": x[:len(intensity)],
                        "intensity": intensity[:len(x)],
                    })
                except ValueError:
                    st.error("Could not parse values. Use comma-separated numbers.")

        elif mtype == "Transmission":
            col1, col2 = st.columns(2)
            with col1:
                t_incident = st.number_input("Incident power (mW)", 0.0, 1e4, 200.0)
            with col2:
                t_transmitted = st.number_input("Transmitted power (mW)", 0.0, 1e4, 0.0)
            if t_incident > 0:
                t_frac = t_transmitted / t_incident
                experimental_data["transmission_point"] = pd.DataFrame({
                    "wavelength_nm": [wavelength_nm],
                    "T": [t_frac],
                    "T_percent": [t_frac * 100],
                })

        elif mtype == "Damage Threshold":
            st.caption("Enter fluence vs observed damage.")
            fluences_text = st.text_area(
                "Fluences tested (mJ/cm2, comma-separated)",
            )
            damaged_text = st.text_area(
                "Damage observed? (1=yes, 0=no, comma-separated)",
            )
            if fluences_text and damaged_text:
                try:
                    fl = [float(v.strip()) for v in fluences_text.split(",")]
                    dm = [int(v.strip()) for v in damaged_text.split(",")]
                    experimental_data["damage"] = pd.DataFrame({
                        "fluence_mj_cm2": fl[:len(dm)],
                        "damaged": dm[:len(fl)],
                    })
                except ValueError:
                    st.error("Could not parse values.")

elif data_mode == "Load Previous":
    with aw_panel():
        st.subheader("Previous Results")
        result_files = sorted(RESULTS_DIR.glob("*.json"))
        if result_files:
            sel = st.selectbox("Select result set", [f.stem for f in result_files])
            if sel:
                data = json.loads((RESULTS_DIR / f"{sel}.json").read_text())
                for key, records in data.items():
                    experimental_data[key] = pd.DataFrame(records)
                st.success(f"Loaded {len(experimental_data)} datasets from {sel}")
        else:
            st.info("No previous results found in data/results/.")

# ── Comparison Plots ──────────────────────────────────────────────

if experimental_data:
    with aw_panel():
        st.subheader("Comparison Plots")

        for name, df in experimental_data.items():
            st.markdown(f"**{name}**")

            if "x_um" in df.columns and "intensity" in df.columns:
                # Beam profile comparison
                fig = go.Figure()

                # Experimental
                fig.add_trace(go.Scatter(
                    x=df["x_um"], y=df["intensity"] / df["intensity"].max(),
                    mode="markers+lines", line=dict(color="#E63946", width=2),
                    marker=dict(size=6), name="Measured",
                ))

                # Model Gaussian
                x_model = np.linspace(
                    df["x_um"].min(), df["x_um"].max(), 200,
                )
                w0 = spot_diameter_um / 2
                gaussian = np.exp(-2 * (x_model / w0) ** 2)
                fig.add_trace(go.Scatter(
                    x=x_model, y=gaussian,
                    mode="lines", line=dict(color="#58A6FF", width=2, dash="dash"),
                    name=f"Model (w0={w0:.0f} um)",
                ))

                fig.update_layout(
                    xaxis_title="Position (um)",
                    yaxis_title="Normalized Intensity",
                    height=400, **plot_defaults(),
                )
                st.plotly_chart(fig, use_container_width=True)

            elif "wavelength_nm" in df.columns and "T" in df.columns:
                # Transmission point
                st.metric(
                    f"Measured Transmission at {wavelength_nm:.0f} nm",
                    f"{df['T'].iloc[0] * 100:.1f}%",
                )
                # Model: Beer-Lambert (linear only as baseline)
                alpha_est = 0.001 * 100  # 0.001 /cm -> /m for Si default
                t_model = math.exp(-alpha_est * thickness_mm * 1e-3)
                st.metric(
                    "Model (linear Beer-Lambert)",
                    f"{t_model * 100:.1f}%",
                    delta=f"{(df['T'].iloc[0] - t_model) * 100:.2f}% difference",
                )

            elif "fluence_mj_cm2" in df.columns and "damaged" in df.columns:
                fig = go.Figure()
                colors = ["#3FB950" if d == 0 else "#E63946" for d in df["damaged"]]
                fig.add_trace(go.Scatter(
                    x=df["fluence_mj_cm2"], y=df["damaged"],
                    mode="markers", marker=dict(size=12, color=colors),
                    name="Observed",
                ))
                fig.update_layout(
                    xaxis_title="Fluence (mJ/cm2)",
                    yaxis_title="Damaged (0/1)",
                    yaxis=dict(tickvals=[0, 1], ticktext=["No", "Yes"]),
                    height=300, **plot_defaults(),
                )
                st.plotly_chart(fig, use_container_width=True)

            else:
                st.dataframe(df, use_container_width=True)

    # Save results
    with aw_panel():
        save_name = st.text_input("Save this dataset as", placeholder="run_001")
        if st.button("Save Results") and save_name:
            out = {
                name: df.to_dict(orient="records")
                for name, df in experimental_data.items()
            }
            out_path = RESULTS_DIR / f"{save_name}.json"
            out_path.write_text(json.dumps(out, indent=2))
            st.success(f"Saved to {out_path}")

else:
    with aw_panel():
        st.info(
            "Upload or enter experimental data to compare against model predictions. "
            "Run the LMI Digital Twin page with the same parameters for model output."
        )
