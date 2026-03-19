"""Layout helpers for Automation Station.

Mirrors pax_americana.ui.layout — provides render_header() and
common page scaffolding.
"""
import streamlit as st
from .branding import BRAND, apply_brand_css, st_svg


def render_header():
    """Render the standard app header with logo and title."""
    apply_brand_css()
    col1, col2 = st.columns([1, 4], vertical_alignment="center")
    with col1:
        st_svg(BRAND["logo_path"], height_px=56)
    with col2:
        st.title(BRAND["app_title"])
        st.caption(
            "Beam Profiling \u2022 Lab Automation \u2022 Data Analysis"
        )
