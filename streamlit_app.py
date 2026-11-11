# ============================================================
#  TWIN REFERENCE ADAPTIVE BATTERY MANAGEMENT SYSTEM
#  WITH DEVIATION ATTRIBUTION FOR PERSONALIZED EV BATTERY HEALTH
#
#  app.py  –  Streamlit Interactive Dashboard (Light Theme, Bold Title, High-Contrast Buttons)
# ============================================================

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import time

from battery_engine import (
    DAY_ONE_FINGERPRINT,
    build_state,
    compute_deviation_attribution,
    aging_curve_data,
)

# ------------------------------------------------------------------ #
# PAGE CONFIG                                                          #
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="Twin Reference Adaptive Battery Management System",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# BULLETPROOF LIGHT THEME CSS                                         #
# ------------------------------------------------------------------ #

st.markdown("""
<style>
/* ---- 1. Global Light Theme ---- */
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stToolbar"] {
    background-color: #f8fafc !important;
    color: #0f172a !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

/* Base text elements */
p, span, label, div {
    color: #0f172a;
}

/* ---- 2. Main Title (Bold & Prominent) ---- */
.main-title {
    text-align: center !important;
    font-size: 1.55rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
    color: #0f172a !important;
    padding: 10px 0 4px 0 !important;
    line-height: 1.35 !important;
    text-shadow: 0 1px 1px rgba(0,0,0,0.05) !important;
}
.subtitle {
    text-align: center !important;
    color: #475569 !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 8px !important;
}

/* ---- 3. Action Buttons (Fixing Color Mistake: Distinct & High Contrast) ---- */
/* General button styling */
.stButton > button {
    width: 100% !important;
    padding: 14px 10px !important;
    font-size: 0.90rem !important;
    font-weight: 800 !important;
    border-radius: 10px !important;
    cursor: pointer !important;
    transition: all 0.2s ease-in-out !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.06) !important;
    text-align: center !important;
    white-space: pre-line !important;
}

/* Stage 1 Button: Soft Green Background with Crisp Dark Green Text */
[data-testid="stColumn"]:nth-of-type(1) .stButton > button,
div[data-testid="column"]:nth-of-type(1) .stButton > button {
    background-color: #f0fdf4 !important;
    border: 2px solid #16a34a !important;
    color: #15803d !important;
}
[data-testid="stColumn"]:nth-of-type(1) .stButton > button p,
[data-testid="stColumn"]:nth-of-type(1) .stButton > button span,
[data-testid="stColumn"]:nth-of-type(1) .stButton > button div,
div[data-testid="column"]:nth-of-type(1) .stButton > button p,
div[data-testid="column"]:nth-of-type(1) .stButton > button span,
div[data-testid="column"]:nth-of-type(1) .stButton > button div {
    color: #15803d !important;
    font-weight: 900 !important;
}
[data-testid="stColumn"]:nth-of-type(1) .stButton > button:hover,
div[data-testid="column"]:nth-of-type(1) .stButton > button:hover {
    background-color: #dcfce7 !important;
    border-color: #15803d !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 6px -1px rgba(22, 163, 74, 0.2) !important;
}

/* Stage 2 Button: Soft Red/Rose Background with Crisp Dark Red Text */
[data-testid="stColumn"]:nth-of-type(2) .stButton > button,
div[data-testid="column"]:nth-of-type(2) .stButton > button {
    background-color: #fef2f2 !important;
    border: 2px solid #dc2626 !important;
    color: #b91c1c !important;
}
[data-testid="stColumn"]:nth-of-type(2) .stButton > button p,
[data-testid="stColumn"]:nth-of-type(2) .stButton > button span,
[data-testid="stColumn"]:nth-of-type(2) .stButton > button div,
div[data-testid="column"]:nth-of-type(2) .stButton > button p,
div[data-testid="column"]:nth-of-type(2) .stButton > button span,
div[data-testid="column"]:nth-of-type(2) .stButton > button div {
    color: #b91c1c !important;
    font-weight: 900 !important;
}
[data-testid="stColumn"]:nth-of-type(2) .stButton > button:hover,
div[data-testid="column"]:nth-of-type(2) .stButton > button:hover {
    background-color: #fee2e2 !important;
    border-color: #b91c1c !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 6px -1px rgba(220, 38, 38, 0.2) !important;
}

/* Stage 3 Button: Soft Blue Background with Crisp Dark Blue Text */
[data-testid="stColumn"]:nth-of-type(3) .stButton > button,
div[data-testid="column"]:nth-of-type(3) .stButton > button {
    background-color: #eff6ff !important;
    border: 2px solid #2563eb !important;
    color: #1d4ed8 !important;
}
[data-testid="stColumn"]:nth-of-type(3) .stButton > button p,
[data-testid="stColumn"]:nth-of-type(3) .stButton > button span,
[data-testid="stColumn"]:nth-of-type(3) .stButton > button div,
div[data-testid="column"]:nth-of-type(3) .stButton > button p,
div[data-testid="column"]:nth-of-type(3) .stButton > button span,
div[data-testid="column"]:nth-of-type(3) .stButton > button div {
    color: #1d4ed8 !important;
    font-weight: 900 !important;
}
[data-testid="stColumn"]:nth-of-type(3) .stButton > button:hover,
div[data-testid="column"]:nth-of-type(3) .stButton > button:hover {
    background-color: #dbeafe !important;
    border-color: #1d4ed8 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2) !important;
}

/* ---- 4. Sidebar Light Theme (Fixing White-on-White Washing Out) ---- */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 {
    color: #0f172a !important;
    font-weight: 900 !important;
}
[data-testid="stSidebar"] strong,
[data-testid="stSidebar"] b {
    color: #0f172a !important;
    font-weight: 800 !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {
    color: #334155 !important;
}
.sidebar-header-label {
    font-size: 0.78rem !important;
    font-weight: 900 !important;
    color: #1e293b !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    margin-bottom: 6px !important;
}

/* ---- 5. Health Gauge Card ---- */
.health-card {
    border-radius: 14px;
    padding: 20px 14px 16px 14px;
    text-align: center;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.health-pct {
    font-size: 3.6rem;
    font-weight: 900;
    line-height: 1.0;
}
.health-label {
    font-size: 0.78rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 800;
    margin-top: 4px;
}

/* ---- 6. Metric Cards ---- */
.metric-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.metric-label {
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 700;
}
.metric-value {
    font-size: 1.45rem;
    font-weight: 800;
    color: #0f172a;
    margin: 2px 0;
}

/* ---- 7. Status Pills ---- */
.pill-normal {
    background: #dcfce7 !important;
    color: #15803d !important;
    border: 1px solid #86efac !important;
    padding: 3px 10px !important;
    border-radius: 20px !important;
    font-size: 0.70rem !important;
    font-weight: 800 !important;
}
.pill-warning {
    background: #fef3c7 !important;
    color: #b45309 !important;
    border: 1px solid #fde68a !important;
    padding: 3px 10px !important;
    border-radius: 20px !important;
    font-size: 0.70rem !important;
    font-weight: 800 !important;
}
.pill-critical {
    background: #fee2e2 !important;
    color: #b91c1c !important;
    border: 1px solid #fca5a5 !important;
    padding: 3px 10px !important;
    border-radius: 20px !important;
    font-size: 0.70rem !important;
    font-weight: 800 !important;
}

/* ---- 8. Section Headers ---- */
.section-head {
    font-size: 0.78rem;
    font-weight: 900;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #1e293b;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 4px;
    margin: 14px 0 10px 0;
}

/* ---- 9. Live Badge (Dynamic Pulse) ---- */
.live-badge {
    display: inline-block;
    background: #ecfdf5;
    color: #047857;
    border: 1px solid #10b981;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    box-shadow: 0 1px 2px rgba(16, 185, 129, 0.2);
    animation: livepulse 1.6s infinite ease-in-out;
}
@keyframes livepulse {
    0%, 100% { opacity: 1.0; transform: scale(1.0); }
    50% { opacity: 0.65; transform: scale(1.02); }
}

/* ---- 10. Four Concept Tags ---- */
.concept-tag {
    display: inline-block;
    margin: 3px;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.c1 { background: #eff6ff; border: 1px solid #93c5fd; color: #1d4ed8; }
.c2 { background: #ecfdf5; border: 1px solid #a7f3d0; color: #047857; }
.c3 { background: #fffbeb; border: 1px solid #fde68a; color: #b45309; }
.c4 { background: #fef2f2; border: 1px solid #fecdd3; color: #b91c1c; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# APPLICATION HEADER (BOLD TITLE)                                     #
# ------------------------------------------------------------------ #

st.markdown("""
<div class="main-title">
  TWIN REFERENCE ADAPTIVE BATTERY MANAGEMENT SYSTEM<br>
  WITH DEVIATION ATTRIBUTION FOR PERSONALIZED EV BATTERY HEALTH
</div>
<div class="subtitle">
  Academic Engineering Design Project &nbsp;|&nbsp;
  <span class="live-badge">● SIMULATED LIVE SENSOR DATA (DYNAMIC STREAM)</span>
</div>
""", unsafe_allow_html=True)

# Four core concepts banner
st.markdown("""
<div style="text-align:center; margin:6px 0 14px 0;">
  <span class="concept-tag c1">① DAY-ONE FINGERPRINT</span>
  <span class="concept-tag c2">② EXPECTED AGING SHADOW CURVE</span>
  <span class="concept-tag c3">③ LIVE SENSOR STREAM</span>
  <span class="concept-tag c4">④ DEVIATION ATTRIBUTION LAYER</span>
</div>
""", unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------ #
# SESSION STATE INITIALIZATION                                        #
# ------------------------------------------------------------------ #

if "stage" not in st.session_state:
    st.session_state.stage = "new"

fp = DAY_ONE_FINGERPRINT

# ------------------------------------------------------------------ #
# THREE STAGE ACTION BUTTONS                                          #
# ------------------------------------------------------------------ #

st.markdown('<div class="section-head">SELECT BATTERY LIFE STAGE</div>', unsafe_allow_html=True)

col_b1, col_b2, col_b3 = st.columns(3, gap="medium")

with col_b1:
    if st.button("🔋  STAGE 1\nNEW BATTERY\n(Day-One Fingerprint)", key="btn_stage1"):
        st.session_state.stage = "new"

with col_b2:
    if st.button("⚠️  STAGE 2\nEND OF LIFE\n(Severe Degradation)", key="btn_stage2"):
        st.session_state.stage = "eol"

with col_b3:
    if st.button("🔄  STAGE 3\nADAPTIVE TWIN EXTENDED\n(Reference Model Tuning)", key="btn_stage3"):
        st.session_state.stage = "adaptive"

stage = st.session_state.stage

# Stage Styling Configuration (Light Theme)
STAGE_CONFIG = {
    "new": {
        "accent": "#15803d",
        "bg": "#f0fdf4",
        "border": "#16a34a",
        "label": "STAGE 1: NEW BATTERY (DAY-ONE CONDITION)"
    },
    "eol": {
        "accent": "#b91c1c",
        "bg": "#fef2f2",
        "border": "#dc2626",
        "label": "STAGE 2: END OF LIFE (SEVERE DEGRADATION)"
    },
    "adaptive": {
        "accent": "#1d4ed8",
        "bg": "#eff6ff",
        "border": "#2563eb",
        "label": "STAGE 3: ADAPTIVE TWIN EXTENDED (TWIN REFERENCE MODEL)"
    },
}
sc = STAGE_CONFIG[stage]

# Active Stage Indicator
st.markdown(f"""
<div style="background:{sc['bg']};border:2px solid {sc['border']};
            border-radius:10px;padding:9px 18px;margin:10px 0;text-align:center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
  <span style="color:{sc['accent']};font-weight:900;font-size:0.96rem;letter-spacing:0.06em;">
    ● {sc['label']}
  </span>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# DYNAMIC LIVE STREAM FRAGMENT (Auto-refreshes every 1 second)        #
# ------------------------------------------------------------------ #

@st.fragment(run_every="1s")
def render_dynamic_live_dashboard():
    """
    Renders the dynamic live sensor stream, battery health gauge,
    and deviation attribution layer. Re-executes every 1 second to vary
    all live sensor values dynamically.
    """
    current_time = time.time()
    state = build_state(st.session_state.stage, fp, t_sec=current_time)

    # -------------------------------------------------------------- #
    # 3-COLUMN MAIN LAYOUT: Health Box | Live Parameters | Attribution #
    # -------------------------------------------------------------- #
    left, mid, right = st.columns([1.1, 2.3, 2.6], gap="medium")

    # ---- 1. LEFT COLUMN: Dedicated Battery Health Gauge Box ---- #
    with left:
        health = state.soh_pct

        if health >= 80.0:
            h_color = "#15803d"
            h_bg = "#f0fdf4"
            h_ring = "#86efac"
            h_label = "EXCELLENT"
        elif health >= 70.0:
            h_color = "#b45309"
            h_bg = "#fffbeb"
            h_ring = "#fde68a"
            h_label = "GOOD"
        elif health >= 50.0:
            h_color = "#c2410c"
            h_bg = "#fff7ed"
            h_ring = "#fed7aa"
            h_label = "DEGRADED"
        else:
            h_color = "#b91c1c"
            h_bg = "#fef2f2"
            h_ring = "#fca5a5"
            h_label = "CRITICAL"

        extension_text = "+6 months estimated" if st.session_state.stage == "adaptive" else "N/A"

        st.markdown(f"""
        <div class="health-card" style="background:{h_bg};border:2px solid {h_ring};">
          <div style="font-size:0.72rem;color:#334155;letter-spacing:0.1em;text-transform:uppercase;font-weight:800;">
            🔋 BATTERY HEALTH
          </div>
          <div class="health-pct" style="color:{h_color};">{health:.1f}%</div>
          <div style="color:{h_color};font-weight:900;font-size:0.92rem;margin:4px 0;">{h_label}</div>
          <div style="color:#475569;font-size:0.74rem;font-weight:600;">State of Health (SOH)</div>
          <hr style="border-color:#cbd5e1;margin:10px 0;">
          <div style="font-size:0.70rem;color:#475569;font-weight:700;">SOH vs Shadow Curve</div>
          <div style="font-size:1.18rem;font-weight:900;color:{'#15803d' if state.soh_deviation_pct >= 0 else '#b91c1c'};">
            {state.soh_deviation_pct:+.2f}%
          </div>
          <div style="color:#64748b;font-size:0.68rem;font-weight:600;">deviation from expected</div>
          <hr style="border-color:#cbd5e1;margin:10px 0;">
          <div style="font-size:0.70rem;color:#475569;font-weight:700;">Adaptive Life Extension</div>
          <div style="font-size:1.05rem;font-weight:900;color:#1d4ed8;">
            {extension_text}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Dynamic State of Charge (SOC) Card
        st.markdown(f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:12px;box-shadow:0 1px 2px rgba(0,0,0,0.04);">
          <div style="font-size:0.70rem;color:#475569;letter-spacing:0.08em;text-transform:uppercase;font-weight:800;">
            STATE OF CHARGE
          </div>
          <div style="font-size:1.85rem;font-weight:900;color:#0284c7;margin:2px 0;">
            {state.soc_pct:.2f}%
          </div>
          <div style="background:#f1f5f9;border-radius:6px;height:10px;margin-top:6px;overflow:hidden;border:1px solid #e2e8f0;">
            <div style="background:linear-gradient(90deg, #38bdf8, #0284c7);width:{state.soc_pct}%;height:100%;border-radius:6px;transition:width 0.3s ease;"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ---- 2. MIDDLE COLUMN: Dynamic Live Sensor Parameters ---- #
    with mid:
        st.markdown('<div class="section-head">⚡ LIVE SENSOR PARAMETERS (DYNAMIC)</div>', unsafe_allow_html=True)

        def param_card(label, value, unit, icon="", ref=None, color="#0f172a"):
            ref_html = f'<div style="color:#64748b;font-size:0.70rem;margin-top:2px;font-weight:600;">Baseline: {ref}</div>' if ref else ""
            return f"""
            <div class="metric-card">
              <div class="metric-label">{icon} {label}</div>
              <div class="metric-value" style="color:{color};">{value} <span style="font-size:0.85rem;color:#64748b;font-weight:700;">{unit}</span></div>
              {ref_html}
            </div>"""

        r1c1, r1c2 = st.columns(2)
        with r1c1:
            v_color = "#15803d" if 3.2 <= state.voltage_V <= 4.25 else "#b91c1c"
            st.markdown(param_card("Terminal Voltage", f"{state.voltage_V:.3f}", "V", "⚡",
                                   f"{fp['nominal_voltage_V']:.2f} V", v_color), unsafe_allow_html=True)

            t_color = "#15803d" if state.temperature_C < 33 else ("#b45309" if state.temperature_C < 40 else "#b91c1c")
            st.markdown(param_card("Battery Temperature", f"{state.temperature_C:.2f}", "°C", "🌡️",
                                   f"{fp['ambient_temp_C']:.1f} °C", t_color), unsafe_allow_html=True)

            st.markdown(param_card("Pack Power", f"{state.power_kW:.3f}", "kW", "💡",
                                   color="#d97706"), unsafe_allow_html=True)

            st.markdown(param_card("Cycle Count", f"{state.cycle_count}", "cycles", "🔁",
                                   "0 (Day-One)"), unsafe_allow_html=True)

        with r1c2:
            st.markdown(param_card("Discharge Current", f"{state.current_A:.2f}", "A", "🔌",
                                   "0 A (idle)", "#0284c7"), unsafe_allow_html=True)

            r_color = "#15803d" if state.resistance_Ohm < 0.020 else ("#b45309" if state.resistance_Ohm < 0.035 else "#b91c1c")
            st.markdown(param_card("Internal Resistance", f"{state.resistance_Ohm * 1000.0:.2f}", "mΩ", "〰️",
                                   f"{fp['initial_resistance_Ohm'] * 1000.0:.1f} mΩ", r_color), unsafe_allow_html=True)

            st.markdown(param_card("Usable Capacity", f"{state.capacity_Ah:.2f}", "Ah", "📦",
                                   f"{fp['rated_capacity_Ah']:.1f} Ah"), unsafe_allow_html=True)

            st.markdown(param_card("Charge Status", state.charge_status, "", "🔄",
                                   color="#334155"), unsafe_allow_html=True)

        # Day-One Fingerprint Reference Box
        st.markdown('<div class="section-head">🔎 DAY-ONE FINGERPRINT REFERENCE</div>', unsafe_allow_html=True)
        fpc1, fpc2, fpc3 = st.columns(3)
        with fpc1:
            st.markdown(f"""
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px;text-align:center;">
              <div style="font-size:0.68rem;color:#475569;text-transform:uppercase;font-weight:800;">Rated Capacity</div>
              <div style="font-size:1.08rem;font-weight:900;color:#1d4ed8;">{fp['rated_capacity_Ah']} Ah</div>
            </div>""", unsafe_allow_html=True)
        with fpc2:
            st.markdown(f"""
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px;text-align:center;">
              <div style="font-size:0.68rem;color:#475569;text-transform:uppercase;font-weight:800;">Nominal Voltage</div>
              <div style="font-size:1.08rem;font-weight:900;color:#1d4ed8;">{fp['nominal_voltage_V']} V</div>
            </div>""", unsafe_allow_html=True)
        with fpc3:
            st.markdown(f"""
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px;text-align:center;">
              <div style="font-size:0.68rem;color:#475569;text-transform:uppercase;font-weight:800;">Initial Resistance</div>
              <div style="font-size:1.08rem;font-weight:900;color:#1d4ed8;">{fp['initial_resistance_Ohm']*1000.0:.1f} mΩ</div>
            </div>""", unsafe_allow_html=True)

    # ---- 3. RIGHT COLUMN: Deviation Attribution Layer & Warning Box ---- #
    with right:
        st.markdown('<div class="section-head">🔬 DEVIATION ATTRIBUTION LAYER</div>', unsafe_allow_html=True)

        dev_df = compute_deviation_attribution(state, fp)

        STATUS_ICONS = {"NORMAL": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}
        PILL_CLASS   = {"NORMAL": "pill-normal", "WARNING": "pill-warning", "CRITICAL": "pill-critical"}

        for _, row in dev_df.iterrows():
            icon = STATUS_ICONS.get(row["Status"], "⚪")
            pill = PILL_CLASS.get(row["Status"], "pill-normal")
            dev_str = row["Deviation"]
            dev_color = "#15803d" if ("+" in dev_str and "Temperature" not in row["Parameter"] and "Resistance" not in row["Parameter"]) else ("#b91c1c" if "-" in dev_str else "#475569")

            st.markdown(f"""
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;
                        padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:12px;
                        box-shadow:0 1px 2px rgba(0,0,0,0.03);">
              <div style="font-size:1.15rem;">{icon}</div>
              <div style="flex:1;">
                <div style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.04em;font-weight:800;">
                  {row["Parameter"]}
                </div>
                <div style="display:flex;align-items:baseline;gap:10px;margin-top:1px;">
                  <span style="font-size:0.98rem;font-weight:900;color:#0f172a;">{row["Live Value"]}</span>
                  <span style="font-size:0.70rem;color:#64748b;font-weight:600;">ref: {row["Reference"]}</span>
                  <span style="font-size:0.78rem;font-weight:800;color:{dev_color};">
                    {dev_str}
                  </span>
                </div>
              </div>
              <span class="{pill}">{row["Status"]}</span>
            </div>
            """, unsafe_allow_html=True)

        # Dynamic Warning Summary Box
        n_critical = (dev_df["Status"] == "CRITICAL").sum()
        n_warning  = (dev_df["Status"] == "WARNING").sum()
        n_normal   = (dev_df["Status"] == "NORMAL").sum()

        if n_critical > 0:
            alert_color, alert_bg, alert_border, alert_icon = "#b91c1c", "#fef2f2", "#f87171", "🚨"
            alert_msg = f"CRITICAL ALERT: {n_critical} parameter(s) exceeded safety thresholds!"
        elif n_warning > 0:
            alert_color, alert_bg, alert_border, alert_icon = "#b45309", "#fffbeb", "#fbbf24", "⚠️"
            alert_msg = f"WARNING LIGHT: {n_warning} parameter(s) approaching limits."
        else:
            alert_color, alert_bg, alert_border, alert_icon = "#15803d", "#f0fdf4", "#4ade80", "✅"
            alert_msg = "HEALTHY: All parameters within nominal reference boundaries."

        st.markdown(f"""
        <div style="background:{alert_bg};border:1.5px solid {alert_border};border-radius:10px;
                    padding:10px 14px;margin-top:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);">
          <div style="font-size:1.15rem;">{alert_icon}</div>
          <div style="color:{alert_color};font-weight:900;font-size:0.88rem;margin:2px 0;">{alert_msg}</div>
          <div style="color:#475569;font-size:0.72rem;font-weight:700;">
            🟢 Normal: {n_normal} &nbsp;|&nbsp; 🟡 Warning: {n_warning} &nbsp;|&nbsp; 🔴 Critical: {n_critical}
          </div>
        </div>
        """, unsafe_allow_html=True)


# Execute the dynamic live fragment
render_dynamic_live_dashboard()

st.divider()

# ------------------------------------------------------------------ #
# ANALYSIS CHARTS (Light Theme)                                      #
# ------------------------------------------------------------------ #

st.markdown('<div class="section-head">📊 INTERACTIVE ANALYSIS CHARTS (LIGHT THEME)</div>', unsafe_allow_html=True)

chart1, chart2, chart3 = st.columns(3, gap="medium")

# Chart 1 — Expected Aging Shadow Curve vs Adaptive Twin Model
with chart1:
    st.markdown("**Expected Aging Shadow Curve vs Adaptive Twin Model**")
    current_state = build_state(stage, fp, t_sec=time.time())
    aging_df = aging_curve_data(current_state)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=aging_df["Cycle Count"],
        y=aging_df["Shadow (Manufacturer)"],
        name="Manufacturer Curve",
        line=dict(color="#d97706", width=2, dash="dash"),
        fill="tozeroy",
        fillcolor="rgba(217,119,6,0.06)"
    ))
    fig1.add_trace(go.Scatter(
        x=aging_df["Cycle Count"],
        y=aging_df["Adaptive Twin Extended"],
        name="Adaptive Twin Extended",
        line=dict(color="#2563eb", width=2.5)
    ))
    fig1.add_hline(
        y=70, line_dash="dot", line_color="#dc2626",
        annotation_text="EOL Threshold (70%)",
        annotation_position="bottom right",
        annotation_font_color="#dc2626"
    )
    # Current State Marker
    fig1.add_trace(go.Scatter(
        x=[current_state.cycle_count],
        y=[current_state.soh_pct],
        mode="markers",
        name="Current State",
        marker=dict(size=12, color=sc["accent"], symbol="star",
                    line=dict(width=2, color="#ffffff"))
    ))
    fig1.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b", size=11),
        xaxis=dict(title="Cycle Count", gridcolor="#e2e8f0", linecolor="#cbd5e1"),
        yaxis=dict(title="SOH (%)", gridcolor="#e2e8f0", linecolor="#cbd5e1", range=[40, 105]),
        legend=dict(bgcolor="#f8fafc", bordercolor="#e2e8f0"),
        margin=dict(l=20, r=20, t=20, b=20),
        height=280
    )
    st.plotly_chart(fig1, width='stretch')

# Chart 2 — Parameter Deviation Radar
with chart2:
    st.markdown("**Parameter Deviation Radar vs Day-One Baseline**")
    current_state = build_state(stage, fp, t_sec=time.time())

    radar_cats = ["SOH", "SOC", "Voltage", "Temperature", "Resistance", "Capacity"]
    radar_vals = [
        current_state.soh_pct,
        current_state.soc_pct,
        min(100.0, max(0.0, (current_state.voltage_V - 2.5) / (4.3 - 2.5) * 100.0)),
        min(100.0, max(0.0, 100.0 - max(0.0, current_state.temperature_C - 25.0) * 2.5)),
        min(100.0, max(0.0, 100.0 - (current_state.resistance_Ohm - fp["initial_resistance_Ohm"]) / fp["initial_resistance_Ohm"] * 50.0)),
        current_state.capacity_Ah / fp["rated_capacity_Ah"] * 100.0,
    ]
    radar_cats_closed = radar_cats + [radar_cats[0]]
    radar_vals_closed = radar_vals + [radar_vals[0]]

    fig2 = go.Figure()
    fig2.add_trace(go.Scatterpolar(
        r=[100]*7, theta=radar_cats_closed,
        fill="toself", name="Day-One Reference",
        fillcolor="rgba(217,119,6,0.06)",
        line=dict(color="#d97706", dash="dash", width=1.5)
    ))
    fig2.add_trace(go.Scatterpolar(
        r=radar_vals_closed, theta=radar_cats_closed,
        fill="toself", name="Current State",
        fillcolor="rgba(37,99,235,0.12)",
        line=dict(color=sc["accent"], width=2.5)
    ))
    fig2.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        polar=dict(
            bgcolor="#ffffff",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#e2e8f0",
                            tickfont=dict(color="#64748b", size=9)),
            angularaxis=dict(gridcolor="#e2e8f0", tickfont=dict(color="#1e293b", size=10))
        ),
        font=dict(color="#1e293b", size=11),
        legend=dict(bgcolor="#f8fafc", bordercolor="#e2e8f0"),
        margin=dict(l=30, r=30, t=20, b=20),
        height=280
    )
    st.plotly_chart(fig2, width='stretch')

# Chart 3 — Three-Stage Benchmark Comparison
with chart3:
    st.markdown("**Three-Stage Benchmark Comparison**")

    stages_data = {
        "Stage":        ["New Battery", "End of Life", "Adaptive Twin"],
        "SOH (%)":      [99.5, 54.0, 76.4],
        "SOC (%)":      [94.8, 41.5, 71.2],
        "Temperature":  [26.2, 38.6, 29.1],
        "Capacity (Ah)":[99.5, 54.0, 76.4],
    }

    stage_colors = ["#16a34a", "#dc2626", "#2563eb"]
    fig3 = go.Figure()
    for i, (stage_name, soh, soc, temp, cap) in enumerate(zip(
        stages_data["Stage"], stages_data["SOH (%)"],
        stages_data["SOC (%)"], stages_data["Temperature"],
        stages_data["Capacity (Ah)"]
    )):
        fig3.add_trace(go.Bar(
            name=stage_name,
            x=["SOH (%)", "SOC (%)", "Temp (°C)", "Capacity (Ah)"],
            y=[soh, soc, temp, cap],
            marker_color=stage_colors[i],
            opacity=0.88,
        ))

    fig3.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b", size=11),
        barmode="group",
        xaxis=dict(gridcolor="#e2e8f0", linecolor="#cbd5e1"),
        yaxis=dict(title="Value", gridcolor="#e2e8f0", linecolor="#cbd5e1", range=[0, 115]),
        legend=dict(bgcolor="#f8fafc", bordercolor="#e2e8f0"),
        margin=dict(l=20, r=20, t=20, b=20),
        height=280
    )
    st.plotly_chart(fig3, width='stretch')

# ------------------------------------------------------------------ #
# FOUR CORE CONCEPTS ARCHITECTURE SECTION                             #
# ------------------------------------------------------------------ #

st.divider()
st.markdown('<div class="section-head">📖 FOUR CORE CONCEPTS ARCHITECTURE</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4, gap="medium")

with c1:
    st.markdown("""
    <div style="background:#eff6ff;border:1.5px solid #93c5fd;border-radius:10px;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
      <div style="color:#1d4ed8;font-weight:900;font-size:0.82rem;letter-spacing:0.06em;">① DAY-ONE FINGERPRINT</div>
      <div style="color:#1e293b;font-size:0.75rem;margin-top:8px;line-height:1.45;font-weight:500;">
        A permanent reference snapshot of the battery's initial pristine condition when it was manufactured.
        Stores rated capacity (100 Ah), nominal voltage (3.65 V), initial impedance (12 mΩ), and baseline OCV curves.
        This fingerprint remains immutable throughout vehicle lifetime.
      </div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div style="background:#ecfdf5;border:1.5px solid #a7f3d0;border-radius:10px;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
      <div style="color:#047857;font-weight:900;font-size:0.82rem;letter-spacing:0.06em;">② EXPECTED AGING SHADOW CURVE</div>
      <div style="color:#1e293b;font-size:0.75rem;margin-top:8px;line-height:1.45;font-weight:500;">
        The manufacturer-claimed degradation baseline modeling expected SOH decline over cycle count.
        The Adaptive Twin Reference model extends this baseline by dynamically managing current rates and thermal stress
        to push actual battery life well above the shadow curve.
      </div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div style="background:#fffbeb;border:1.5px solid #fde68a;border-radius:10px;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
      <div style="color:#b45309;font-weight:900;font-size:0.82rem;letter-spacing:0.06em;">③ LIVE SENSOR STREAM</div>
      <div style="color:#1e293b;font-size:0.75rem;margin-top:8px;line-height:1.45;font-weight:500;">
        Continuous real-time simulated telemetry generated by the 2-RC equivalent-circuit model,
        coulomb counting, and lumped thermal balance equations.
        All readings vary dynamically with simulated driver behavior and load transients.
      </div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown("""
    <div style="background:#fef2f2;border:1.5px solid #fecdd3;border-radius:10px;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
      <div style="color:#b91c1c;font-weight:900;font-size:0.82rem;letter-spacing:0.06em;">④ DEVIATION ATTRIBUTION LAYER</div>
      <div style="color:#1e293b;font-size:0.75rem;margin-top:8px;line-height:1.45;font-weight:500;">
        Compares each dynamic live reading against the Day-One Fingerprint and aging shadow curve.
        Classifies deviations into NORMAL, WARNING, or CRITICAL status with colored warning lights
        to isolate degradation causes in real time.
      </div>
    </div>""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# SIDEBAR CONTROL PANEL (FIXING ALL COLOR ISSUES)                     #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.markdown('<div class="sidebar-title" style="font-size:1.35rem;font-weight:900;color:#0f172a !important;margin-bottom:2px;">🔋 BMS Control Panel</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.76rem;color:#475569 !important;font-weight:700;">Light Theme • Dynamic Physics</div>', unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="sidebar-header-label" style="color:#0f172a !important;font-weight:900;font-size:0.82rem;">CURRENT ACTIVE STAGE</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:{sc['bg']};border:2px solid {sc['border']};
                border-radius:8px;padding:10px;text-align:center;">
      <div style="color:{sc['accent']};font-weight:900;font-size:0.88rem;">{sc['label']}</div>
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="sidebar-header-label" style="color:#0f172a !important;font-weight:900;font-size:0.82rem;">DAY-ONE SPECIFICATIONS</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-size:0.78rem;color:#1e293b !important;line-height:1.7;">
      <strong style="color:#0f172a !important;">Chemistry:</strong> {fp['cell_chemistry']}<br>
      <strong style="color:#0f172a !important;">Rated Capacity:</strong> {fp['rated_capacity_Ah']} Ah<br>
      <strong style="color:#0f172a !important;">Nominal Voltage:</strong> {fp['nominal_voltage_V']} V<br>
      <strong style="color:#0f172a !important;">Initial Impedance:</strong> {fp['initial_resistance_Ohm']*1000.0:.1f} mΩ<br>
      <strong style="color:#0f172a !important;">Thermal Mass:</strong> {fp['thermal_mass_J_per_K']} J/K<br>
      <strong style="color:#0f172a !important;">Ambient Baseline:</strong> {fp['ambient_temp_C']} °C
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("""
    <div style="font-size:0.72rem;color:#475569 !important;text-align:center;line-height:1.5;font-weight:700;">
      <span style="color:#16a34a !important;font-weight:900;">● STREAMING LIVE AT 1 HZ</span><br>
      Twin Reference Adaptive BMS<br>
      Academic Engineering Design Project
    </div>""", unsafe_allow_html=True)
