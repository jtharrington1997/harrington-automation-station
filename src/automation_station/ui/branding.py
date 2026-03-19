"""Branding constants and CSS for Harrington Automation Station.

Follows the same architecture as pax_americana.ui.branding but with a
lab-instrument / engineering aesthetic: dark background, red accent,
monospace headings.
"""
import base64
import uuid
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

BRAND = {
    "app_title": "Automation Station",
    "primary": "#E63946",
    "primary_hover": "#FF4D5A",
    "accent": "#58A6FF",
    "dark": "#0D1117",
    "dark_mid": "#161B22",
    "border": "#30363D",
    "text": "#C9D1D9",
    "text_muted": "#8B949E",
    "success": "#3FB950",
    "warning": "#D29922",
    "logo_path": "app/assets/automation-logo.svg",
    "font_heading": "JetBrains Mono",
    "font_body": "Inter",
}


def st_svg(path: str, height_px: int = 56):
    p = Path(path)
    if not p.exists():
        return
    svg_bytes = p.read_bytes()
    b64 = base64.b64encode(svg_bytes).decode("utf-8")
    html = (
        '<div style="display:flex; align-items:center; min-height:{h}px;">'
        '<img src="data:image/svg+xml;base64,{d}" '
        'style="height:{h}px; width:auto; max-width:100%; object-fit:contain; display:block;" />'
        "</div>"
    ).format(h=height_px, d=b64)
    st.markdown(html, unsafe_allow_html=True)


@contextmanager
def hw_panel():
    """Context manager for hardware/data panels — equivalent to aw_panel()."""
    panel_id = "hw-panel-" + uuid.uuid4().hex
    with st.container():
        st.markdown(
            '<div class="hw-panel-marker" data-hw-panel="' + panel_id + '"></div>',
            unsafe_allow_html=True,
        )
        yield


_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');
:root {{
  --hw-heading: "{fh}", "Courier New", monospace;
  --hw-body: "{fb}", "Helvetica Neue", sans-serif;
  --hw-red: {primary};
  --hw-red-hover: {hover};
  --hw-blue: {accent};
  --hw-dark: {dark};
  --hw-dark-mid: {dark_mid};
  --hw-border: {border};
  --hw-text: {text};
  --hw-muted: {muted};
  --hw-success: {success};
  --hw-warning: {warning};
  --hw-panel-bg: rgba(22,27,34,0.85);
  --hw-shadow: 0 1px 3px rgba(0,0,0,0.3);
}}

html, body, .stApp {{
  font-family: var(--hw-body) !important;
  color: var(--hw-text) !important;
}}

.stApp {{
  background: var(--hw-dark) !important;
  background-image:
    radial-gradient(ellipse at 20% 0%, rgba(230,57,70,0.04) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 100%, rgba(88,166,255,0.03) 0%, transparent 50%) !important;
}}

.stMarkdown, .stText, label, p, li {{
  color: var(--hw-text) !important;
  font-family: var(--hw-body) !important;
  line-height: 1.65;
}}

.stCaption, small {{
  color: var(--hw-muted) !important;
  font-weight: 400;
}}

h1 {{
  font-family: var(--hw-heading) !important;
  font-weight: 700 !important;
  color: #E6EDF3 !important;
  letter-spacing: -0.03em;
  font-size: 2rem !important;
  border-bottom: 2px solid var(--hw-red);
  padding-bottom: 8px;
}}

h2 {{
  font-family: var(--hw-heading) !important;
  font-weight: 600 !important;
  color: #E6EDF3 !important;
  letter-spacing: -0.02em;
}}

h3 {{
  font-family: var(--hw-heading) !important;
  font-weight: 600 !important;
  color: var(--hw-text) !important;
}}

h4,h5,h6 {{
  font-family: var(--hw-body) !important;
  font-weight: 600 !important;
  color: var(--hw-text) !important;
}}

.block-container {{
  padding-top: 1.2rem;
  padding-bottom: 2rem;
  max-width: 1200px;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
  background: var(--hw-dark-mid) !important;
  border-right: 2px solid var(--hw-border);
}}
section[data-testid="stSidebar"] .stMarkdown p {{
  color: var(--hw-text) !important;
}}

/* Panels */
div[data-testid="stVerticalBlock"]:has(.hw-panel-marker) {{
  background: var(--hw-panel-bg);
  border: 1px solid var(--hw-border);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 8px 0 16px 0;
  box-shadow: var(--hw-shadow);
  backdrop-filter: blur(8px);
}}
.hw-panel-marker {{ height:0; margin:0; padding:0; }}

/* Metrics */
div[data-testid="stMetric"] {{
  border-radius: 10px;
  border: 1px solid var(--hw-border);
  background: rgba(22,27,34,0.6);
  padding: 14px 18px;
  box-shadow: var(--hw-shadow);
}}
div[data-testid="stMetric"] label {{
  font-family: var(--hw-body) !important;
  font-weight: 500;
  text-transform: uppercase;
  font-size: 0.7rem !important;
  letter-spacing: 0.08em;
  color: var(--hw-muted) !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
  font-family: var(--hw-heading) !important;
  font-weight: 700;
  color: #E6EDF3 !important;
}}

/* Buttons */
button[kind="primary"], .stFormSubmitButton button {{
  background-color: var(--hw-red) !important;
  border: 0 !important;
  border-radius: 8px !important;
  font-family: var(--hw-body) !important;
  font-weight: 600 !important;
  letter-spacing: 0.03em;
  color: #ffffff !important;
  transition: background-color 0.2s ease;
}}
button[kind="primary"]:hover, .stFormSubmitButton button:hover {{
  background-color: var(--hw-red-hover) !important;
  color: #ffffff !important;
}}
button[kind="primary"] *, .stFormSubmitButton button * {{
  color: #ffffff !important;
}}
/* Secondary buttons */
button[kind="secondary"] {{
  color: var(--hw-text) !important;
  border-color: var(--hw-border) !important;
  border-radius: 8px !important;
  font-family: var(--hw-body) !important;
}}
button[kind="secondary"]:hover {{
  background-color: var(--hw-red) !important;
  color: #ffffff !important;
  border-color: var(--hw-red) !important;
}}
button[kind="secondary"]:hover p, button[kind="secondary"]:hover span {{
  color: #ffffff !important;
}}

/* Links */
a {{ color: var(--hw-blue) !important; text-decoration: none; }}
a:hover {{ color: var(--hw-red) !important; }}

/* Expanders */
div[data-testid="stExpander"] {{
  border: 1px solid var(--hw-border) !important;
  border-radius: 10px !important;
  margin-bottom: 8px;
  background: rgba(22,27,34,0.4);
}}
div[data-testid="stExpander"] summary {{
  font-family: var(--hw-body) !important;
  font-weight: 500;
}}

/* Text inputs */
input[type="text"], textarea {{
  border: 1px solid var(--hw-border) !important;
  border-radius: 8px !important;
  background: rgba(13,17,23,0.6) !important;
  color: var(--hw-text) !important;
}}
input[type="text"]:focus, textarea:focus {{
  border-color: var(--hw-red) !important;
  box-shadow: 0 0 0 1px var(--hw-red) !important;
}}

/* Selectbox */
div[data-testid="stSelectbox"] > div {{
  border-radius: 8px !important;
}}

/* Top accent line */
.stApp > header {{
  background: linear-gradient(90deg, var(--hw-red) 0%, var(--hw-red) 33%, var(--hw-dark) 33%, var(--hw-dark) 67%, var(--hw-blue) 67%, var(--hw-blue) 100%) !important;
  height: 4px !important;
}}

/* Status indicators */
.hw-status-online {{ color: var(--hw-success); font-weight: 600; }}
.hw-status-offline {{ color: var(--hw-red); font-weight: 600; }}
.hw-status-warning {{ color: var(--hw-warning); font-weight: 600; }}

</style>"""


def apply_brand_css():
    st.markdown(
        _CSS.format(
            fh=BRAND["font_heading"],
            fb=BRAND["font_body"],
            primary=BRAND["primary"],
            hover=BRAND["primary_hover"],
            accent=BRAND["accent"],
            dark=BRAND["dark"],
            dark_mid=BRAND["dark_mid"],
            border=BRAND["border"],
            text=BRAND["text"],
            muted=BRAND["text_muted"],
            success=BRAND["success"],
            warning=BRAND["warning"],
        ),
        unsafe_allow_html=True,
    )
