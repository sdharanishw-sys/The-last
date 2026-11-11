# ============================================================
#  TWIN REFERENCE ADAPTIVE BATTERY MANAGEMENT SYSTEM
#  WITH DEVIATION ATTRIBUTION FOR PERSONALIZED EV BATTERY HEALTH
#
#  app.py  –  Streamlit interactive dashboard
# ============================================================

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import time

from battery_engine import (
    DAY_ONE_FINGERPRINT,
    build_state,
    compute_deviation_attribution,
    aging_curve_data,
    aging_shadow_curve,
    resistance_aging,
)

# ------------------------------------------------------------------ #
# PAGE CONFIG                                                          #
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="Twin Reference Adaptive BMS",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# CUSTOM CSS                                                           #
# ------------------------------------------------------------------ #

st.markdown("""
<style>
/* ---- Global ---- */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
[data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}

/* ---- Title banner ---- */
.main-title {
    text-align: center;
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    background: linear-gradient(90deg, #58a6ff, #3fb950, #d29922);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding: 10px 0 2px 0;
    line-height: 1.4;
}
.subtitle {
    text-align: center;
    color: #8b949e;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
}

/* ---- Stage buttons ---- */
div[data-testid="column"] .stButton > button {
    width: 100%;
    padding: 16px 8px;
    font-size: 0.95rem;
    font-weight: 700;
    border-radius: 10px;
    border: 2px solid;
    cursor: pointer;
    transition: all 0.2s;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ---- Health gauge card ---- */
.health-card {
    border-radius: 16px;
    padding: 20px 10px 14px 10px;
    text-align: center;
    margin-bottom: 10px;
}
.health-pct {
    font-size: 3.6rem;
    font-weight: 900;
    line-height: 1.0;
}
.health-label {
    font-size: 0.75rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 4px;
    opacity: 0.75;
}

/* ---- Metric cards ---- */
.metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.metric-label { font-size: 0.72rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.06em; }
.metric-value { font-size: 1.5rem; font-weight: 700; }

/* ---- Status pills ---- */
.pill-normal   { background:#1a3a2a; color:#3fb950; border:1px solid #2ea043; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:700; }
.pill-warning  { background:#3a2a0a; color:#d29922; border:1px solid #9e6a03; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:700; }
.pill-critical { background:#3a0d0d; color:#f85149; border:1px solid #da3633; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:700; }

/* ---- Section headers ---- */
.section-head {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #8b949e;
    border-bottom: 1px solid #30363d;
    padding-bottom: 4px;
    margin: 14px 0 10px 0;
}

/* ---- Live badge ---- */
.live-badge {
    display:inline-block;
    background:#1a2a1a;
    color:#3fb950;
    border:1px solid #2ea043;
    border-radius:20px;
    padding:2px 10px;
    font-size:0.68rem;
    font-weight:700;
    letter-spacing:0.08em;
    animation: pulse 2s infinite;
}
@keyframes pulse {
  0%,100%{opacity:1} 50%{opacity:0.5}
}

/* ---- Concept tags ---- */
.concept-tag {
    display:inline-block;
    margin:3px;
    padding:5px 12px;
    border-radius:6px;
    font-size:0.73rem;
    font-weight:700;
    letter-spacing:0.05em;
}
.c1{background:#0d2039;border:1px solid #58a6ff;color:#58a6ff;}
.c2{background:#0d2d1a;border:1px solid #3fb950;color:#3fb950;}
.c3{background:#2d1a0d;border:1px solid #d29922;color:#d29922;}
.c4{background:#2d0d0d;border:1px solid #f85149;color:#f85149;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# HEADER                                                               #
# ------------------------------------------------------------------ #

st.markdown("""
<div class="main-title">
  Twin Reference Adaptive Battery Management System<br>
  with Deviation Attribution for Personalized EV Battery Health
</div>
<div class="subtitle">
  Academic Engineering Design Project &nbsp;|&nbsp;
  <span class="live-badge">● SIMULATED LIVE SENSOR DATA</span>
</div>
""", unsafe_allow_html=True)

# Four concept tags
st.markdown("""
<div style="text-align:center; margin:6px 0 16px 0;">
  <span class="concept-tag c1">① DAY-ONE FINGERPRINT</span>
  <span class="concept-tag c2">② EXPECTED AGING SHADOW CURVE</span>
  <span class="concept-tag c3">③ LIVE SENSOR STREAM</span>
  <span class="concept-tag c4">④ DEVIATION ATTRIBUTION LAYER</span>
</div>
""", unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------ #
# SESSION STATE                                                         #
# ------------------------------------------------------------------ #

if "stage" not in st.session_state:
    st.session_state.stage = "new"
if "tick" not in st.session_state:
    st.session_state.tick = 0

# ------------------------------------------------------------------ #
# THREE STAGE BUTTONS                                                   #
# ------------------------------------------------------------------ #

st.markdown('<div class="section-head">SELECT BATTERY LIFE STAGE</div>', unsafe_allow_html=True)

col_b1, col_b2, col_b3 = st.columns(3, gap="medium")

with col_b1:
    if st.button("🔋  STAGE 1\nNEW BATTERY\n(Day-One Fingerprint)", use_container_width=True):
        st.session_state.stage = "new"
        st.session_state.tick  = 0

with col_b2:
    if st.button("⚠️  STAGE 2\nEND OF LIFE\n(Severe Degradation)", use_container_width=True):
        st.session_state.stage = "eol"
        st.session_state.tick  = 0

with col_b3:
    if st.button("🤖  STAGE 3\nAI-ADAPTIVE EXTENDED\n(Twin Reference Model)", use_container_width=True):
        st.session_state.stage = "adaptive"
        st.session_state.tick  = 0

stage = st.session_state.stage

# ------------------------------------------------------------------ #
# LOAD STATE FOR SELECTED STAGE                                         #
# ------------------------------------------------------------------ #

fp    = DAY_ONE_FINGERPRINT
state = build_state(stage, fp)

# Stage colour scheme
STAGE_COLORS = {
    "new":      {"accent": "#3fb950", "bg": "#0d2d1a", "border": "#2ea043", "label": "NEW BATTERY"},
    "eol":      {"accent": "#f85149", "bg": "#2d0d0d", "border": "#da3633", "label": "END OF LIFE"},
    "adaptive": {"accent": "#58a6ff", "bg": "#0d2039", "border": "#1f6feb", "label": "AI-ADAPTIVE EXTENDED"},
}
sc = STAGE_COLORS[stage]

# Active stage banner
st.markdown(f"""
<div style="background:{sc['bg']};border:1px solid {sc['border']};
            border-radius:10px;padding:8px 18px;margin:12px 0;text-align:center;">
  <span style="color:{sc['accent']};font-weight:800;font-size:1.0rem;letter-spacing:0.08em;">
    ● ACTIVE STAGE: {sc['label']}
  </span>
  <span style="color:#8b949e;font-size:0.8rem;margin-left:16px;">
    {state.aging_state}  |  Cycle Count: {state.cycle_count}
  </span>
</div>
""", unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------ #
# MAIN LAYOUT: health gauge | parameters | deviation table            #
# ------------------------------------------------------------------ #

left, mid, right = st.columns([1, 2.4, 2.6], gap="medium")

# ---- LEFT: Battery Health Gauge ---- #
with left:
    health = state.soh_pct

    if health >= 80:
        h_color, h_bg, h_ring = "#3fb950", "#0d2d1a", "#2ea043"
        h_label = "EXCELLENT"
    elif health >= 70:
        h_color, h_bg, h_ring = "#d29922", "#2a1f0a", "#9e6a03"
        h_label = "GOOD"
    elif health >= 50:
        h_color, h_bg, h_ring = "#db6d28", "#2d1a0a", "#b96620"
        h_label = "DEGRADED"
    else:
        h_color, h_bg, h_ring = "#f85149", "#2d0d0d", "#da3633"
        h_label = "CRITICAL"

    st.markdown(f"""
    <div class="health-card" style="background:{h_bg};border:2px solid {h_ring};">
      <div style="font-size:0.68rem;color:#8b949e;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:6px;">
        🔋 BATTERY HEALTH
      </div>
      <div class="health-pct" style="color:{h_color};">{health:.1f}%</div>
      <div style="color:{h_color};font-weight:700;font-size:0.85rem;margin:4px 0;">{h_label}</div>
      <div style="color:#8b949e;font-size:0.7rem;margin-top:4px;">State of Health (SOH)</div>
      <hr style="border-color:#30363d;margin:10px 0;">
      <div style="font-size:0.68rem;color:#8b949e;">SOH vs Shadow Curve</div>
      <div style="font-size:1.1rem;font-weight:700;color:{'#3fb950' if state.soh_deviation_pct >= 0 else '#f85149'};">
        {state.soh_deviation_pct:+.1f}%
      </div>
      <div style="color:#8b949e;font-size:0.68rem;">deviation from expected</div>
      <hr style="border-color:#30363d;margin:10px 0;">
      <div style="font-size:0.68rem;color:#8b949e;">AI Life Extension</div>
      <div style="font-size:1.1rem;font-weight:700;color:#58a6ff;">
        {"N/A" if stage != "adaptive" else "+6 months estimated"}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Mini progress-bar style SOC
    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px;">
      <div style="font-size:0.68rem;color:#8b949e;letter-spacing:0.1em;text-transform:uppercase;">STATE OF CHARGE</div>
      <div style="font-size:1.8rem;font-weight:800;color:#58a6ff;">{state.soc_pct:.1f}%</div>
      <div style="background:#0d1117;border-radius:6px;height:10px;margin-top:6px;overflow:hidden;">
        <div style="background:#58a6ff;width:{state.soc_pct}%;height:100%;border-radius:6px;
                    transition:width 0.5s;"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ---- MIDDLE: Parameter Cards ---- #
with mid:
    st.markdown('<div class="section-head">⚡ LIVE SENSOR PARAMETERS</div>', unsafe_allow_html=True)

    def param_card(label, value, unit, icon="", ref=None, color="#e6edf3"):
        ref_html = f'<span style="color:#8b949e;font-size:0.68rem;">Ref: {ref}</span>' if ref else ""
        return f"""
        <div class="metric-card">
          <div class="metric-label">{icon} {label}</div>
          <div class="metric-value" style="color:{color};">{value} <span style="font-size:0.9rem;color:#8b949e;">{unit}</span></div>
          {ref_html}
        </div>"""

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        v_color = "#3fb950" if 3.2 <= state.voltage_V <= 4.15 else "#f85149"
        st.markdown(param_card("Terminal Voltage", f"{state.voltage_V:.3f}", "V", "⚡",
                               f"{fp['nominal_voltage_V']} V", v_color), unsafe_allow_html=True)

        t_color = "#3fb950" if state.temperature_C < 35 else ("#d29922" if state.temperature_C < 45 else "#f85149")
        st.markdown(param_card("Battery Temperature", f"{state.temperature_C:.1f}", "°C", "🌡️",
                               f"{fp['ambient_temp_C']} °C", t_color), unsafe_allow_html=True)

        st.markdown(param_card("Charge/Discharge Power", f"{state.power_kW:.2f}", "kW", "💡",
                               color="#d29922"), unsafe_allow_html=True)

        st.markdown(param_card("Cycle Count", f"{state.cycle_count}", "cycles", "🔁",
                               "0 (Day-One)"), unsafe_allow_html=True)

    with r1c2:
        i_color = "#58a6ff"
        st.markdown(param_card("Current", f"{state.current_A:.1f}", "A", "🔌",
                               "0 A (idle)", i_color), unsafe_allow_html=True)

        r_color = "#3fb950" if state.resistance_Ohm < 0.025 else ("#d29922" if state.resistance_Ohm < 0.04 else "#f85149")
        st.markdown(param_card("Internal Resistance", f"{state.resistance_Ohm*1000:.2f}", "mΩ", "〰️",
                               f"{fp['initial_resistance_Ohm']*1000:.1f} mΩ", r_color), unsafe_allow_html=True)

        st.markdown(param_card("Usable Capacity", f"{state.capacity_Ah:.1f}", "Ah", "📦",
                               f"{fp['rated_capacity_Ah']} Ah"), unsafe_allow_html=True)

        st.markdown(param_card("Charge Status", state.charge_status, "", "🔄",
                               color="#8b949e"), unsafe_allow_html=True)

    # Day-One Fingerprint summary
    st.markdown('<div class="section-head">🔎 DAY-ONE FINGERPRINT REFERENCE</div>', unsafe_allow_html=True)
    fp_cols = st.columns(3)
    fp_data = [
        ("Rated Capacity", f"{fp['rated_capacity_Ah']} Ah"),
        ("Nominal Voltage", f"{fp['nominal_voltage_V']} V"),
        ("Initial Resistance", f"{fp['initial_resistance_Ohm']*1000:.1f} mΩ"),
    ]
    for i, (k, v) in enumerate(fp_data):
        with fp_cols[i]:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                        padding:10px;text-align:center;margin-bottom:4px;">
              <div style="font-size:0.65rem;color:#8b949e;text-transform:uppercase;">{k}</div>
              <div style="font-size:1.1rem;font-weight:700;color:#58a6ff;">{v}</div>
            </div>""", unsafe_allow_html=True)

# ---- RIGHT: Deviation Attribution Layer ---- #
with right:
    st.markdown('<div class="section-head">🔬 DEVIATION ATTRIBUTION LAYER</div>', unsafe_allow_html=True)

    dev_df = compute_deviation_attribution(state, fp)

    STATUS_ICONS = {"NORMAL": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}
    PILL_CLASS   = {"NORMAL": "pill-normal", "WARNING": "pill-warning", "CRITICAL": "pill-critical"}

    for _, row in dev_df.iterrows():
        icon  = STATUS_ICONS.get(row["Status"], "⚪")
        pill  = PILL_CLASS.get(row["Status"], "pill-normal")
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                    padding:10px 14px;margin-bottom:7px;display:flex;align-items:center;gap:14px;">
          <div style="font-size:1.3rem;">{icon}</div>
          <div style="flex:1;">
            <div style="font-size:0.72rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.05em;">
              {row["Parameter"]}
            </div>
            <div style="display:flex;align-items:baseline;gap:12px;margin-top:2px;">
              <span style="font-size:1.05rem;font-weight:700;">{row["Live Value"]}</span>
              <span style="font-size:0.72rem;color:#8b949e;">ref: {row["Reference"]}</span>
              <span style="font-size:0.8rem;color:{'#3fb950' if '+' in row['Deviation'] or row['Deviation'].startswith('+') else '#f85149'};">
                {row["Deviation"]}
              </span>
            </div>
          </div>
          <span class="{pill}">{row["Status"]}</span>
        </div>
        """, unsafe_allow_html=True)

    # Warning summary box
    n_critical = (dev_df["Status"] == "CRITICAL").sum()
    n_warning  = (dev_df["Status"] == "WARNING").sum()
    n_normal   = (dev_df["Status"] == "NORMAL").sum()

    if n_critical > 0:
        alert_color, alert_bg, alert_icon = "#f85149", "#2d0d0d", "🚨"
        alert_msg = f"ALERT: {n_critical} critical parameter(s) detected!"
    elif n_warning > 0:
        alert_color, alert_bg, alert_icon = "#d29922", "#2a1f0a", "⚠️"
        alert_msg = f"WARNING: {n_warning} parameter(s) approaching limits."
    else:
        alert_color, alert_bg, alert_icon = "#3fb950", "#0d2d1a", "✅"
        alert_msg = "All parameters within normal operating range."

    st.markdown(f"""
    <div style="background:{alert_bg};border:1px solid {alert_color};border-radius:10px;
                padding:12px 18px;margin-top:8px;text-align:center;">
      <div style="font-size:1.2rem;">{alert_icon}</div>
      <div style="color:{alert_color};font-weight:700;font-size:0.85rem;">{alert_msg}</div>
      <div style="color:#8b949e;font-size:0.72rem;margin-top:4px;">
        🟢 Normal: {n_normal} &nbsp;|&nbsp; 🟡 Warning: {n_warning} &nbsp;|&nbsp; 🔴 Critical: {n_critical}
      </div>
    </div>
    """, unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# CHARTS ROW                                                            #
# ------------------------------------------------------------------ #

st.divider()
st.markdown('<div class="section-head">📊 ANALYSIS CHARTS</div>', unsafe_allow_html=True)

chart1, chart2, chart3 = st.columns(3, gap="medium")

# Chart 1 — Aging Shadow Curve
with chart1:
    st.markdown("**Expected Aging Shadow Curve vs AI-Adaptive**")
    aging_df = aging_curve_data(state)
    fig1 = go.Figure()

    fig1.add_trace(go.Scatter(
        x=aging_df["Cycle Count"], y=aging_df["Shadow (Manufacturer)"],
        name="Manufacturer Curve", line=dict(color="#d29922", width=2, dash="dash"),
        fill="tozeroy", fillcolor="rgba(210,153,34,0.05)"
    ))
    fig1.add_trace(go.Scatter(
        x=aging_df["Cycle Count"], y=aging_df["AI-Adaptive Extended"],
        name="AI-Adaptive Extended", line=dict(color="#58a6ff", width=2.5)
    ))
    fig1.add_hline(y=70, line_dash="dot", line_color="#f85149",
                   annotation_text="EOL Threshold (70%)", annotation_position="bottom right",
                   annotation_font_color="#f85149")

    # Current point
    fig1.add_trace(go.Scatter(
        x=[state.cycle_count], y=[state.soh_pct],
        mode="markers", name="Current State",
        marker=dict(size=12, color=sc["accent"], symbol="star",
                    line=dict(width=2, color="white"))
    ))

    fig1.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#e6edf3", size=11),
        xaxis=dict(title="Cycle Count", gridcolor="#21262d"),
        yaxis=dict(title="SOH (%)", gridcolor="#21262d", range=[40, 105]),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
        margin=dict(l=20, r=20, t=20, b=20), height=280
    )
    st.plotly_chart(fig1, use_container_width=True)

# Chart 2 — Parameter Deviation Radar
with chart2:
    st.markdown("**Parameter Deviation Radar**")
    # Normalize deviations 0-100 for radar (100 = perfect, 0 = critical)
    radar_cats = ["SOH", "SOC", "Voltage", "Temperature", "Resistance", "Capacity"]
    radar_vals = [
        state.soh_pct,
        state.soc_pct,
        min(100, max(0, (state.voltage_V - 2.5) / (4.3 - 2.5) * 100)),
        min(100, max(0, 100 - max(0, state.temperature_C - 25) * 2.5)),
        min(100, max(0, 100 - (state.resistance_Ohm - fp["initial_resistance_Ohm"]) /
            fp["initial_resistance_Ohm"] * 50)),
        state.capacity_Ah / fp["rated_capacity_Ah"] * 100,
    ]
    radar_cats_closed = radar_cats + [radar_cats[0]]
    radar_vals_closed = radar_vals + [radar_vals[0]]

    fig2 = go.Figure()
    fig2.add_trace(go.Scatterpolar(
        r=[100]*7, theta=radar_cats_closed,
        fill="toself", name="Day-One Reference",
        fillcolor="rgba(210,153,34,0.05)",
        line=dict(color="#d29922", dash="dash", width=1)
    ))
    fig2.add_trace(go.Scatterpolar(
        r=radar_vals_closed, theta=radar_cats_closed,
        fill="toself", name="Current State",
        fillcolor=f"rgba{tuple(int(sc['accent'].lstrip('#')[i:i+2], 16) for i in (0,2,4)) + (0.15,)}",
        line=dict(color=sc["accent"], width=2.5)
    ))
    fig2.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        polar=dict(
            bgcolor="#0d1117",
            radialaxis=dict(visible=True, range=[0,100], gridcolor="#21262d",
                            tickfont=dict(color="#8b949e", size=9)),
            angularaxis=dict(gridcolor="#21262d", tickfont=dict(color="#e6edf3"))
        ),
        font=dict(color="#e6edf3", size=11),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
        margin=dict(l=30, r=30, t=20, b=20), height=280
    )
    st.plotly_chart(fig2, use_container_width=True)

# Chart 3 — Stage Comparison Bar
with chart3:
    st.markdown("**Three-Stage Parameter Comparison**")

    stages_data = {
        "Stage":        ["New Battery", "End of Life", "AI-Adaptive"],
        "SOH (%)":      [99.5, 54.0, 76.4],
        "SOC (%)":      [95.0, 42.0, 71.0],
        "Temperature":  [26.5, 38.5, 29.2],
        "Capacity (Ah)":[99.5, 54.0, 76.4],
    }

    stage_colors = ["#3fb950", "#f85149", "#58a6ff"]
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
            opacity=0.85,
        ))

    fig3.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#e6edf3", size=11),
        barmode="group",
        xaxis=dict(gridcolor="#21262d"),
        yaxis=dict(title="Value", gridcolor="#21262d", range=[0, 115]),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
        margin=dict(l=20, r=20, t=20, b=20), height=280
    )
    st.plotly_chart(fig3, use_container_width=True)

# ------------------------------------------------------------------ #
# CONCEPT EXPLANATION SECTION                                           #
# ------------------------------------------------------------------ #

st.divider()
st.markdown('<div class="section-head">📖 FOUR CORE CONCEPTS</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4, gap="medium")

with c1:
    st.markdown("""
    <div style="background:#0d2039;border:1px solid #58a6ff;border-radius:10px;padding:14px;">
      <div style="color:#58a6ff;font-weight:800;font-size:0.8rem;letter-spacing:0.08em;">① DAY-ONE FINGERPRINT</div>
      <div style="color:#e6edf3;font-size:0.75rem;margin-top:8px;">
        A permanent reference snapshot of the battery's initial condition when it was new.
        Stores rated capacity, nominal voltage, initial resistance, and baseline characteristics.
        This fingerprint never changes and serves as the absolute comparison baseline.
      </div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div style="background:#0d2d1a;border:1px solid #3fb950;border-radius:10px;padding:14px;">
      <div style="color:#3fb950;font-weight:800;font-size:0.8rem;letter-spacing:0.08em;">② EXPECTED AGING SHADOW CURVE</div>
      <div style="color:#e6edf3;font-size:0.75rem;margin-top:8px;">
        The manufacturer-claimed degradation curve that shows how SOH should decline with cycle count.
        The Twin Reference model extends this by applying AI-adaptive personalised corrections
        to push the actual SOH above the shadow curve.
      </div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div style="background:#2d1a0d;border:1px solid #d29922;border-radius:10px;padding:14px;">
      <div style="color:#d29922;font-weight:800;font-size:0.8rem;letter-spacing:0.08em;">③ LIVE SENSOR STREAM</div>
      <div style="color:#e6edf3;font-size:0.75rem;margin-top:8px;">
        Real-time simulated sensor data generated by the mathematical battery engine using
        an equivalent-circuit model, coulomb counting, and a thermal model.
        All readings clearly labelled as SIMULATED LIVE SENSOR DATA.
      </div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown("""
    <div style="background:#2d0d0d;border:1px solid #f85149;border-radius:10px;padding:14px;">
      <div style="color:#f85149;font-weight:800;font-size:0.8rem;letter-spacing:0.08em;">④ DEVIATION ATTRIBUTION LAYER</div>
      <div style="color:#e6edf3;font-size:0.75rem;margin-top:8px;">
        Compares every live sensor reading against the Day-One Fingerprint and the shadow curve.
        Each parameter is attributed a status (NORMAL / WARNING / CRITICAL) with deviation
        magnitude. Diagnostic warnings are issued for parameters outside safe thresholds.
      </div>
    </div>""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# SIDEBAR                                                               #
# ------------------------------------------------------------------ #

with st.sidebar:
    st.markdown("### 🔋 BMS Control Panel")
    st.divider()

    st.markdown("**ACTIVE STAGE**")
    st.markdown(f"""
    <div style="background:{sc['bg']};border:1px solid {sc['border']};
                border-radius:8px;padding:10px;text-align:center;">
      <div style="color:{sc['accent']};font-weight:800;">{sc['label']}</div>
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("**KEY METRICS**")

    metrics = [
        ("SOH", f"{state.soh_pct:.1f}%"),
        ("SOC", f"{state.soc_pct:.1f}%"),
        ("Voltage", f"{state.voltage_V:.3f} V"),
        ("Current", f"{state.current_A:.1f} A"),
        ("Temperature", f"{state.temperature_C:.1f} °C"),
        ("Resistance", f"{state.resistance_Ohm*1000:.2f} mΩ"),
        ("Capacity", f"{state.capacity_Ah:.1f} Ah"),
        ("Cycles", f"{state.cycle_count}"),
        ("Power", f"{state.power_kW:.2f} kW"),
    ]
    for k, v in metrics:
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;padding:4px 0;
                    border-bottom:1px solid #21262d;font-size:0.8rem;">
          <span style="color:#8b949e;">{k}</span>
          <span style="font-weight:700;">{v}</span>
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("**DAY-ONE FINGERPRINT**")
    st.markdown(f"""
    <div style="font-size:0.75rem;color:#8b949e;">
      Chemistry: {fp['cell_chemistry']}<br>
      Capacity: {fp['rated_capacity_Ah']} Ah<br>
      Voltage: {fp['nominal_voltage_V']} V<br>
      Resistance: {fp['initial_resistance_Ohm']*1000:.1f} mΩ<br>
      Initial SOH: {fp['initial_SOH_pct']}%
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("""
    <div style="font-size:0.65rem;color:#8b949e;text-align:center;">
      <span style="color:#3fb950;">●</span> SIMULATED LIVE SENSOR DATA<br>
      Academic Engineering Design Project<br>
      NMC Lithium-Ion Battery Model
    </div>""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# AUTO-REFRESH TOGGLE                                                   #
# ------------------------------------------------------------------ #

st.divider()
auto_refresh = st.toggle("🔄 Auto-refresh sensor stream (1 s)", value=False)
if auto_refresh:
    st.session_state.tick += 1
    time.sleep(1)
    st.rerun()
