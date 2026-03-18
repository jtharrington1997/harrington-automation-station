"""
Home.py — Knife-Edge Z-Scan Beam Profiler
Main dashboard with hardware status and mode selection.
"""

import streamlit as st

st.set_page_config(
    page_title="Knife-Edge Beam Profiler",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS (pax-americana inspired) ───────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

    .stApp { font-family: 'Inter', sans-serif; }
    code, .stCode { font-family: 'JetBrains Mono', monospace; }

    /* Header banner */
    .hero-banner {
        background: linear-gradient(135deg, #0D1117 0%, #161B22 50%, #1a0a0a 100%);
        border: 1px solid #30363D;
        border-left: 4px solid #E63946;
        border-radius: 8px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
    }
    .hero-banner h1 {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem;
        font-weight: 700;
        color: #E6EDF3;
        margin: 0 0 0.3rem 0;
    }
    .hero-banner .subtitle {
        color: #8B949E;
        font-size: 0.95rem;
        margin: 0;
    }
    .hero-banner .accent {
        color: #E63946;
        font-weight: 600;
    }

    /* Status cards */
    .hw-card {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.8rem;
    }
    .hw-card .hw-name {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
        font-size: 0.9rem;
        color: #E6EDF3;
    }
    .hw-card .hw-role {
        color: #8B949E;
        font-size: 0.8rem;
    }
    .hw-status-ok {
        color: #3FB950;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .hw-status-off {
        color: #6E7681;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .hw-status-err {
        color: #E63946;
        font-weight: 600;
        font-size: 0.85rem;
    }

    /* Mode cards */
    .mode-card {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 1.5rem;
        transition: border-color 0.2s;
    }
    .mode-card:hover {
        border-color: #E63946;
    }
    .mode-card h3 {
        font-family: 'JetBrains Mono', monospace;
        color: #E6EDF3;
        font-size: 1.1rem;
        margin: 0 0 0.5rem 0;
    }
    .mode-card p {
        color: #8B949E;
        font-size: 0.85rem;
        margin: 0;
        line-height: 1.5;
    }
    .mode-tag {
        display: inline-block;
        background: #E63946;
        color: #fff;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 4px;
        margin-bottom: 0.5rem;
    }
    .mode-tag-semi {
        background: #D29922;
    }
    .mode-tag-min {
        background: #388BFD;
    }

    /* Metric display */
    .metric-box {
        background: #0D1117;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 1rem;
        text-align: center;
    }
    .metric-box .metric-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem;
        font-weight: 700;
        color: #E63946;
    }
    .metric-box .metric-label {
        color: #8B949E;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #0D1117;
        border-right: 1px solid #30363D;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
if "hw_ophir" not in st.session_state:
    st.session_state.hw_ophir = None
if "hw_smc" not in st.session_state:
    st.session_state.hw_smc = None
if "hw_kdc" not in st.session_state:
    st.session_state.hw_kdc = None
if "scan_data" not in st.session_state:
    st.session_state.scan_data = {"z_um": [], "w_um": [], "raw": []}
if "fit_result" not in st.session_state:
    st.session_state.fit_result = None


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
    <h1>KNIFE-EDGE BEAM PROFILER</h1>
    <p class="subtitle">
        Z-scan beam characterization &nbsp;·&nbsp;
        <span class="accent">16% / 84%</span> clip method &nbsp;·&nbsp;
        w₀, M², z_R extraction
    </p>
</div>
""", unsafe_allow_html=True)


# ── Hardware Status ───────────────────────────────────────────────────────────
st.markdown("### Hardware Status")

col1, col2, col3 = st.columns(3)

with col1:
    ophir_status = "DISCONNECTED"
    ophir_class = "hw-status-off"
    if st.session_state.hw_ophir and st.session_state.hw_ophir.available:
        ophir_status = "CONNECTED"
        ophir_class = "hw-status-ok"
    st.markdown(f"""
    <div class="hw-card">
        <div class="hw-name">Ophir StarBright</div>
        <div class="hw-role">Power Meter · Modes 1 & 2</div>
        <div class="{ophir_class}">{ophir_status}</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Connect Ophir", key="btn_ophir", use_container_width=True):
        from utils.hardware import OphirStarBright
        ophir = OphirStarBright()
        msg = ophir.connect()
        st.session_state.hw_ophir = ophir
        if ophir.available:
            st.success(msg)
        else:
            st.error(msg)

with col2:
    smc_status = "DISCONNECTED"
    smc_class = "hw-status-off"
    if st.session_state.hw_smc and st.session_state.hw_smc.available:
        smc_status = "CONNECTED"
        smc_class = "hw-status-ok"
    st.markdown(f"""
    <div class="hw-card">
        <div class="hw-name">Newport SMC100</div>
        <div class="hw-role">Z-Axis Stage · All Modes</div>
        <div class="{smc_class}">{smc_status}</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Connect SMC100", key="btn_smc", use_container_width=True):
        from utils.hardware import NewportSMC100
        smc = NewportSMC100()
        msg = smc.connect()
        st.session_state.hw_smc = smc
        if smc.available:
            st.success(msg)
        else:
            st.error(msg)

with col3:
    kdc_status = "DISCONNECTED"
    kdc_class = "hw-status-off"
    if st.session_state.hw_kdc and st.session_state.hw_kdc.available:
        kdc_status = "CONNECTED"
        kdc_class = "hw-status-ok"
    st.markdown(f"""
    <div class="hw-card">
        <div class="hw-name">Thorlabs KDC101</div>
        <div class="hw-role">X-Axis Knife Edge · Mode 1 Only</div>
        <div class="{kdc_class}">{kdc_status}</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Connect KDC101", key="btn_kdc", use_container_width=True):
        from utils.hardware import ThorlabsKDC101
        kdc = ThorlabsKDC101()
        msg = kdc.connect()
        st.session_state.hw_kdc = kdc
        if kdc.available:
            st.success(msg)
        else:
            st.error(msg)


# ── Mode Selection ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Select Scan Mode")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="mode-card">
        <div class="mode-tag">MODE 1</div>
        <h3>Full Auto</h3>
        <p>
            Z stage + knife-edge stage + power meter all automated.
            Press start and walk away.<br><br>
            <strong>Requires:</strong> SMC100, KDC101, Ophir
        </p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Launch Full Auto →", key="launch_m1", use_container_width=True):
        st.switch_page("pages/1_Full_Auto.py")

with col2:
    st.markdown("""
    <div class="mode-card">
        <div class="mode-tag mode-tag-semi">MODE 2</div>
        <h3>Semi Auto</h3>
        <p>
            Z stage + power meter automated.
            You position the knife edge manually.
            Live power display guides you to clip points.<br><br>
            <strong>Requires:</strong> SMC100, Ophir
        </p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Launch Semi Auto →", key="launch_m2", use_container_width=True):
        st.switch_page("pages/2_Semi_Auto.py")

with col3:
    st.markdown("""
    <div class="mode-card">
        <div class="mode-tag mode-tag-min">MODE 3</div>
        <h3>Minimal</h3>
        <p>
            Z stage automated only.
            You position knife edge and read the power meter display.
            Type both values manually.<br><br>
            <strong>Requires:</strong> SMC100 only
        </p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Launch Minimal →", key="launch_m3", use_container_width=True):
        st.switch_page("pages/3_Minimal.py")


# ── Quick Results (if any) ────────────────────────────────────────────────────
if st.session_state.fit_result:
    st.markdown("---")
    st.markdown("### Latest Results")
    r = st.session_state.fit_result
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-val">{r['w0']:.1f}</div>
            <div class="metric-label">w₀ (µm)</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-val">{r['M2']:.2f}</div>
            <div class="metric-label">M²</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-val">{r['z_R']:.0f}</div>
            <div class="metric-label">z_R (µm)</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-val">{r['z0']:.0f}</div>
            <div class="metric-label">z₀ (µm)</div>
        </div>""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("#### ⚙️ Configuration")
    st.markdown("Edit `Home.py` USER SETTINGS or use the **Settings** page.")
    st.markdown("---")
    st.markdown("#### 📖 Pages")
    st.page_link("Home.py", label="Dashboard", icon="🏠")
    st.page_link("pages/1_Full_Auto.py", label="Mode 1: Full Auto", icon="🤖")
    st.page_link("pages/2_Semi_Auto.py", label="Mode 2: Semi Auto", icon="🔧")
    st.page_link("pages/3_Minimal.py", label="Mode 3: Minimal", icon="📝")
    st.page_link("pages/4_Results.py", label="Results & Analysis", icon="📊")
    st.page_link("pages/5_Settings.py", label="Settings", icon="⚙️")
    st.page_link("pages/6_Gnuplot.py", label="Gnuplot", icon="📈")
