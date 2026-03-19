"""Layout helpers for Automation Station — delegates to harrington_common."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from harrington_common.theme import apply_theme, st_svg

_TITLE = "Automation Station"
_SUBTITLE = "Beam Profiling \u2022 Lab Automation \u2022 Data Analysis"
_LOGO = "app/assets/automation-logo.svg"


def render_header() -> None:
    """Render the standard app header with logo and title."""
    apply_theme()
    if Path(_LOGO).exists():
        col1, col2 = st.columns([1, 4], vertical_alignment="center")
        with col1:
            st_svg(_LOGO, height_px=56)
        with col2:
            st.title(_TITLE)
            st.caption(_SUBTITLE)
    else:
        st.title(_TITLE)
        st.caption(_SUBTITLE)
