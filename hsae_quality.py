# hsae_quality.py  –  HSAE Water Quality Monitoring Module
# ═══════════════════════════════════════════════════════════════════════════════
# Closes Gap #3: "جودة المياه" — full water quality monitoring
#
# Parameters modelled:
#   EC / TDS  — electrical conductivity / total dissolved solids (salinity)
#   BOD / DO  — biochemical oxygen demand / dissolved oxygen (organic pollution)
#   Turbidity — suspended sediment optical proxy
#   pH        — acidity/alkalinity
#   Nitrates  — agricultural runoff proxy (FAO threshold)
#   Heavy metals proxy — mining / industrial signal (Cd/Pb/Hg index)
#   Temperature — thermal stratification
#
# Legal mapping:
#   UN 1997 Art. 20 — ecosystem protection
#   UN 1997 Art. 21 — prevention of pollution
#   WHO 2017 Guidelines for Drinking-Water Quality
#   FAO Irrigation Water Quality Standards
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# WHO / FAO THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

THRESHOLDS = {
    "EC_uS_cm": {
        "excellent": 250,   "good": 750,    "acceptable": 1500,
        "concern":   2500,  "critical": 5000,
        "unit": "μS/cm", "label": "Electrical Conductivity (EC)",
        "standard": "WHO 2017 drinking: <1500 μS/cm | FAO irrigation: <750",
        "article": "Art. 21"
    },
    "TDS_mg_L": {
        "excellent": 150,  "good": 500,   "acceptable": 1000,
        "concern":   2000, "critical": 4000,
        "unit": "mg/L", "label": "Total Dissolved Solids (TDS)",
        "standard": "WHO drinking: <1000 mg/L",
        "article": "Art. 21"
    },
    "DO_mg_L": {
        "critical": 3.0, "concern": 5.0, "acceptable": 6.0,
        "good": 8.0,     "excellent": 10.0,
        "unit": "mg/L", "label": "Dissolved Oxygen (DO)",
        "standard": "WHO: >6 mg/L for aquatic life | min ecological: 3 mg/L",
        "article": "Art. 20", "inverted": True
    },
    "BOD_mg_L": {
        "excellent": 1.0, "good": 3.0,   "acceptable": 5.0,
        "concern":   10.0,"critical": 20.0,
        "unit": "mg/L", "label": "Biochemical Oxygen Demand (BOD)",
        "standard": "WHO drinking: <5 mg/L | pristine rivers: <2 mg/L",
        "article": "Art. 21"
    },
    "Turbidity_NTU": {
        "excellent": 1.0, "good": 5.0,   "acceptable": 25.0,
        "concern":   50.0,"critical": 200.0,
        "unit": "NTU", "label": "Turbidity",
        "standard": "WHO drinking: <4 NTU | aesthetic: <1 NTU",
        "article": "Art. 21"
    },
    "pH": {
        "critical_lo": 5.0, "concern_lo": 6.0, "excellent_lo": 6.5,
        "excellent_hi": 8.5,"concern_hi": 9.0,  "critical_hi": 10.0,
        "unit": "", "label": "pH",
        "standard": "WHO drinking: 6.5–8.5 | aquatic life: 6.0–9.0",
        "article": "Art. 20"
    },
    "Nitrate_mg_L": {
        "excellent": 2.0, "good": 5.0,   "acceptable": 10.0,
        "concern":   20.0,"critical": 50.0,
        "unit": "mg/L", "label": "Nitrate (NO₃⁻)",
        "standard": "WHO drinking: <10 mg/L (MCL) | EU: 50 mg/L",
        "article": "Art. 21"
    },
    "HeavyMetal_idx": {
        "excellent": 0.1, "good": 0.3,  "acceptable": 0.6,
        "concern":   0.8, "critical": 1.0,
        "unit": "idx", "label": "Heavy Metals Index (Cd/Pb/Hg)",
        "standard": "Composite index: >0.6 triggers monitoring; >1.0 remediation",
        "article": "Art. 21"
    },
    "Temp_C": {
        "excellent": 15.0,"good": 20.0,  "acceptable": 25.0,
        "concern":   30.0,"critical": 35.0,
        "unit": "°C", "label": "Water Temperature",
        "standard": "Thermal pollution: >3°C above natural baseline (Art. 20)",
        "article": "Art. 20"
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# WATER QUALITY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def simulate_water_quality(
    basin:   dict,
    df_sim:  pd.DataFrame,
    irr_ha:  float = 200_000,
    pop:     float = 5_000_000,
    mining:  float = 0.2,   # 0–1 mining activity index
) -> pd.DataFrame:
    """
    Physics-based proxy simulation of 9 water quality parameters.
    Each parameter responds realistically to:
    - flow regime (dilution effect)
    - seasonality (temperature, algae)
    - upstream land use (irrigation, urban, mining)
    """
    n    = len(df_sim)
    seed = abs(hash(basin.get("id","X"))) % (2**31) + 13
    rng  = np.random.default_rng(seed)

    dates = pd.to_datetime(df_sim["Date"])
    doy   = np.array([d.timetuple().tm_yday for d in dates])

    # Flow series (for dilution)
    Q     = np.maximum(df_sim["Outflow_BCM"].values, 1e-6)
    Q_norm= Q / (Q.mean() + 1e-9)  # normalized flow

    # Catchment area and population density
    area_km2   = basin.get("eff_cat_km2", 100_000)
    pop_density= pop / (area_km2 + 1)

    # ── EC / TDS (salinity) ─────────────────────────────────────────────────
    # EC rises when flow is low (concentration effect) and in arid basins
    evap_base = basin.get("evap_base", 5.0)
    EC_base   = 200 + 150 * evap_base / 5.0 + 100 * irr_ha / 500_000
    EC        = EC_base / Q_norm + rng.normal(0, 30, n)
    EC        = np.clip(EC, 50, 8000)
    TDS       = EC * 0.64 + rng.normal(0, 20, n)   # empirical TDS≈0.64×EC
    TDS       = np.clip(TDS, 30, 5000)

    # ── Temperature ─────────────────────────────────────────────────────────
    lat  = basin.get("lat", 15.0)
    T_base = 20 + 10 * np.exp(-abs(lat) / 30)
    T_amp  = 5  + 0.1 * abs(lat)
    Temp_C = T_base + T_amp * np.sin(2*np.pi*doy/365) + rng.normal(0,1.5,n)
    Temp_C = np.clip(Temp_C, 2, 38)

    # ── DO (dissolved oxygen) ────────────────────────────────────────────────
    # DO decreases with temperature (Henry's law) and organic load
    DO_sat  = 14.62 - 0.3898*Temp_C + 0.006969*Temp_C**2 - 0.00005896*Temp_C**3
    organic_load = (pop_density * 0.001 + irr_ha * 0.000001)
    DO      = DO_sat * (0.8 + 0.2*Q_norm) - organic_load + rng.normal(0, 0.5, n)
    DO      = np.clip(DO, 0.5, 15.0)

    # ── BOD ──────────────────────────────────────────────────────────────────
    BOD = (2.0 + organic_load * 10) / Q_norm + rng.gamma(1.2, 0.5, n)
    BOD = np.clip(BOD, 0.3, 50.0)

    # ── pH ───────────────────────────────────────────────────────────────────
    pH_base = 7.5 - 0.1 * mining
    pH = pH_base + 0.5 * np.sin(2*np.pi*doy/365) + rng.normal(0, 0.3, n)
    # Mining causes acid mine drainage → pH drops in high-flow
    if mining > 0.3:
        pH -= 0.5 * mining * (1 - Q_norm)
    pH = np.clip(pH, 4.5, 10.0)

    # ── Turbidity ────────────────────────────────────────────────────────────
    # Turbidity peaks during high-flow events (sediment mobilization)
    rain  = df_sim.get("GPM_Rain_mm", pd.Series(np.zeros(n))).values
    Turb  = 2 + 8 * Q_norm**0.7 * (1 + 0.5 * rain / (rain.mean()+1)) + rng.gamma(1,2,n)
    Turb  = np.clip(Turb, 0.5, 500.0)

    # ── Nitrates ─────────────────────────────────────────────────────────────
    # NO3 peaks after rainfall events (agricultural leaching)
    NO3   = (1.5 + 8 * irr_ha / 1_000_000) * (1 + np.roll(rain,3) / (rain.mean()+1)) / Q_norm
    NO3  += rng.gamma(1.2, 0.5, n)
    NO3   = np.clip(NO3, 0.1, 80.0)

    # ── Heavy metals index ────────────────────────────────────────────────────
    HM  = mining * (0.4 + 0.3 * (1 - Q_norm)) + rng.gamma(1.1, 0.05, n)
    HM  = np.clip(HM, 0.0, 1.5)

    # ── Water Quality Index (WQI) — weighted composite ──────────────────────
    # Higher = better (0–100)
    def _score(val, thr, inverted=False):
        """Score parameter 0-100."""
        if inverted:  # higher is better (DO)
            if val >= thr.get("excellent",10): return 100
            if val >= thr.get("good",8):       return 85
            if val >= thr.get("acceptable",6): return 70
            if val >= thr.get("concern",4):    return 40
            return 15
        else:
            if val <= thr.get("excellent",1):  return 100
            if val <= thr.get("good",5):       return 80
            if val <= thr.get("acceptable",15):return 60
            if val <= thr.get("concern",50):   return 35
            return 10

    weights = {"EC":0.15,"DO":0.20,"BOD":0.15,"Turb":0.10,
               "pH":0.10,"NO3":0.10,"HM":0.10,"Temp":0.10}
    WQI = np.zeros(n)
    for t in range(n):
        sc = {}
        sc["EC"]   = _score(EC[t],   THRESHOLDS["EC_uS_cm"])
        sc["DO"]   = _score(DO[t],   THRESHOLDS["DO_mg_L"],   inverted=True)
        sc["BOD"]  = _score(BOD[t],  THRESHOLDS["BOD_mg_L"])
        sc["Turb"] = _score(Turb[t], THRESHOLDS["Turbidity_NTU"])
        # pH scoring (range-based)
        p = pH[t]
        sc["pH"]   = 100 if 6.5<=p<=8.5 else (70 if 6.0<=p<=9.0 else (30 if 5.5<=p<=9.5 else 5))
        sc["NO3"]  = _score(NO3[t],  THRESHOLDS["Nitrate_mg_L"])
        sc["HM"]   = _score(HM[t],   THRESHOLDS["HeavyMetal_idx"])
        sc["Temp"] = _score(Temp_C[t],THRESHOLDS["Temp_C"])
        WQI[t]     = sum(sc[k]*weights[k] for k in weights)

    return pd.DataFrame({
        "Date":              dates,
        "EC_uS_cm":          EC.round(1),
        "TDS_mg_L":          TDS.round(1),
        "DO_mg_L":           DO.round(2),
        "BOD_mg_L":          BOD.round(2),
        "pH":                pH.round(2),
        "Turbidity_NTU":     Turb.round(1),
        "Nitrate_mg_L":      NO3.round(2),
        "HeavyMetal_idx":    HM.round(3),
        "Temp_C":            Temp_C.round(1),
        "WQI":               WQI.round(1),
        "Flow_BCM":          Q.round(5),
    })


# ══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def check_compliance(df_wq: pd.DataFrame) -> pd.DataFrame:
    """Returns per-parameter compliance summary."""
    results = []
    param_map = {
        "EC_uS_cm":       ("EC_uS_cm",  False),
        "TDS_mg_L":       ("TDS_mg_L",  False),
        "DO_mg_L":        ("DO_mg_L",   True),
        "BOD_mg_L":       ("BOD_mg_L",  False),
        "Turbidity_NTU":  ("Turbidity_NTU", False),
        "Nitrate_mg_L":   ("Nitrate_mg_L",  False),
        "HeavyMetal_idx": ("HeavyMetal_idx",False),
        "Temp_C":         ("Temp_C",    False),
    }
    for col, (thr_key, inv) in param_map.items():
        if col not in df_wq.columns:
            continue
        thr  = THRESHOLDS.get(thr_key, {})
        vals = df_wq[col].dropna().values
        if len(vals) == 0:
            continue

        if not inv:
            critical_days = int((vals > thr.get("critical",1e9)).sum())
            concern_days  = int((vals > thr.get("concern", 1e9)).sum())
        else:
            critical_days = int((vals < thr.get("critical",0)).sum())
            concern_days  = int((vals < thr.get("concern", 0)).sum())

        status = "✅ Compliant" if critical_days == 0 and concern_days < 10 else \
                 ("⚠️ Concern"  if critical_days == 0 else "🚨 Violation")

        results.append({
            "Parameter":     thr.get("label", col),
            "Unit":          thr.get("unit",""),
            "Mean":          f"{vals.mean():.2f}",
            "Max":           f"{vals.max():.2f}",
            "Min":           f"{vals.min():.2f}",
            "Critical Days": critical_days,
            "Concern Days":  concern_days,
            "WHO/FAO Ref":   thr.get("standard","—")[:55],
            "Article":       thr.get("article","—"),
            "Status":        status,
        })
    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def render_quality_page(df_sim: pd.DataFrame | None, basin: dict) -> None:

    st.markdown("""
<style>
.wq-card {
    background:linear-gradient(135deg,#0f172a,#071a2e);
    border:2px solid #0ea5e9;border-radius:16px;
    padding:1.2rem;box-shadow:0 10px 40px rgba(14,165,233,0.2);
}
.param-badge {
    display:inline-block;padding:3px 10px;border-radius:6px;
    font-size:0.78rem;font-weight:700;margin:2px;
}
</style>
""", unsafe_allow_html=True)

    basin_id = basin.get("id","—")
    st.markdown(f"""
<div class='wq-card'>
  <h1 style='color:#38bdf8;font-family:Orbitron;text-align:center;font-size:1.9rem;margin:0;'>
    🧪 Water Quality Monitoring
  </h1>
  <p style='text-align:center;color:#94a3b8;font-family:Orbitron;
            font-size:0.74rem;letter-spacing:2px;margin:0.4rem 0 0;'>
    EC · TDS · DO · BOD · pH · TURBIDITY · NITRATES · HEAVY METALS · WQI
  </p>
  <hr style='border-color:#0ea5e9;margin:0.6rem 0;'>
  <p style='text-align:center;color:#e2e8f0;margin:0;'>
    🎯 <b style='color:#7dd3fc;'>{basin_id}</b>  ·  {basin.get("river","—")}
    &nbsp;|&nbsp; WHO 2017 · FAO-56 · UN 1997 Art. 20 / 21
  </p>
</div>
""", unsafe_allow_html=True)

    if df_sim is None:
        st.warning("⚠️ Run the **v430 engine** first to generate simulation data.")
        return

    # Controls
    with st.sidebar:
        st.markdown("### 🧪 Quality Parameters")
        irr_ha  = st.number_input("Irrigated Area (ha)",  0, 5_000_000, 300_000, 50_000, key="wq_ha")
        pop     = st.number_input("Downstream Population",0, 200_000_000, 8_000_000, 500_000, key="wq_pop")
        mining  = st.slider("Mining Activity Index", 0.0, 1.0, 0.15, 0.05, key="wq_mine")

    with st.spinner("Simulating water quality parameters…"):
        df_wq = simulate_water_quality(basin, df_sim, irr_ha, pop, mining)

    compliance = check_compliance(df_wq)

    # Summary KPIs
    wqi_mean   = float(df_wq["WQI"].mean())
    n_critical = int((compliance["Status"] == "🚨 Violation").sum())
    n_concern  = int((compliance["Status"] == "⚠️ Concern").sum())
    n_ok       = int((compliance["Status"] == "✅ Compliant").sum())

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Water Quality Index", f"{wqi_mean:.1f}/100",
              "🟢 Good" if wqi_mean>70 else ("🟡 Moderate" if wqi_mean>50 else "🔴 Poor"))
    k2.metric("🚨 Violations",       n_critical)
    k3.metric("⚠️ Concerns",         n_concern)
    k4.metric("✅ Compliant Params", n_ok)

    tabs = st.tabs([
        "📊 Dashboard",
        "🌊 Dissolved Oxygen & BOD",
        "🧂 Salinity & TDS",
        "🌡️ Temperature & pH",
        "🌾 Nitrates & Metals",
        "📋 Compliance Table",
        "⚖️ Legal: Art. 20/21",
        "📥 Export",
    ])

    # ── Tab 1: Dashboard ─────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Water Quality Index (WQI) Dashboard")

        fig_wqi = go.Figure()
        fig_wqi.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["WQI"],
            name="WQI", fill="tozeroy",
            line=dict(width=2.5,
                color=np.where(df_wq["WQI"].values > 70, "#10b981", "#f97316")[0]),
            fillcolor="rgba(16,185,129,0.12)"
        ))
        fig_wqi.add_hline(y=70, line_dash="dash", line_color="#10b981",
                          annotation_text="Good (>70)")
        fig_wqi.add_hline(y=50, line_dash="dash", line_color="#f59e0b",
                          annotation_text="Moderate (>50)")
        fig_wqi.add_hline(y=30, line_dash="dash", line_color="#dc2626",
                          annotation_text="Poor (<30)")
        fig_wqi.update_layout(
            template="plotly_dark", height=360,
            title=f"Water Quality Index — {basin_id}",
            yaxis=dict(title="WQI (0–100)", range=[0,100])
        )
        st.plotly_chart(fig_wqi, use_container_width=True)

        # Radar chart for latest 30-day mean
        recent = df_wq.tail(30)
        params_radar = {
            "EC":   min(100, max(0, 100 - (recent["EC_uS_cm"].mean()-250)/25)),
            "DO":   min(100, max(0, (recent["DO_mg_L"].mean()-3)/7*100)),
            "BOD":  min(100, max(0, 100 - (recent["BOD_mg_L"].mean()-1)/4*100)),
            "Turb": min(100, max(0, 100 - (recent["Turbidity_NTU"].mean()-1)/24*100)),
            "NO₃":  min(100, max(0, 100 - (recent["Nitrate_mg_L"].mean()-2)/8*100)),
            "HM":   min(100, max(0, 100 - recent["HeavyMetal_idx"].mean()*100)),
            "pH":   min(100, max(0, 100 - abs(recent["pH"].mean()-7.0)*15)),
            "Temp": min(100, max(0, 100 - (recent["Temp_C"].mean()-15)/15*100)),
        }
        fig_radar = go.Figure(go.Scatterpolar(
            r=list(params_radar.values()),
            theta=list(params_radar.keys()),
            fill="toself",
            line=dict(color="#38bdf8"),
            fillcolor="rgba(56,189,248,0.15)",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0,100],
                       gridcolor="#334155", linecolor="#334155"),
                       angularaxis=dict(gridcolor="#334155")),
            template="plotly_dark", height=380,
            title="Quality Radar — Last 30 Days (higher = better)"
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # ── Tab 2: DO & BOD ──────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Dissolved Oxygen & Biochemical Oxygen Demand")
        st.caption("DO reflects ecosystem health. BOD reflects organic pollution. "
                   "Both are key Art. 20/21 indicators.")

        fig_do = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                subplot_titles=["Dissolved Oxygen (mg/L)",
                                                "BOD (mg/L)"])
        fig_do.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["DO_mg_L"], name="DO",
            line=dict(color="#22d3ee", width=2),
            fill="tozeroy", fillcolor="rgba(34,211,238,0.1)"), row=1,col=1)
        fig_do.add_hline(y=6,  row=1,col=1, line_dash="dot",  line_color="#10b981",
                         annotation_text="Min for aquatic life (6 mg/L)")
        fig_do.add_hline(y=3,  row=1,col=1, line_dash="dash", line_color="#dc2626",
                         annotation_text="Critical (3 mg/L)")
        fig_do.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["BOD_mg_L"], name="BOD",
            line=dict(color="#f97316", width=2)), row=2,col=1)
        fig_do.add_hline(y=5,  row=2,col=1, line_dash="dot",  line_color="#f59e0b",
                         annotation_text="WHO limit 5 mg/L")
        fig_do.add_hline(y=10, row=2,col=1, line_dash="dash", line_color="#dc2626",
                         annotation_text="Critical 10 mg/L")
        fig_do.update_layout(template="plotly_dark", height=520)
        st.plotly_chart(fig_do, use_container_width=True)

        # Scatter: DO vs Flow (dilution effect)
        fig_dof = px.scatter(
            df_wq.sample(min(500, len(df_wq))),
            x="Flow_BCM", y="DO_mg_L", color="BOD_mg_L",
            color_continuous_scale="RdYlGn_r",
            template="plotly_dark", height=360,
            title="DO vs Flow — Dilution Effect",
            labels={"Flow_BCM":"Flow (BCM/d)", "DO_mg_L":"DO (mg/L)"}
        )
        st.plotly_chart(fig_dof, use_container_width=True)

    # ── Tab 3: Salinity ──────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Electrical Conductivity & Total Dissolved Solids")

        fig_ec = make_subplots(rows=2,cols=1,shared_xaxes=True,
                               subplot_titles=["EC (μS/cm)","TDS (mg/L)"])
        fig_ec.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["EC_uS_cm"], name="EC",
            line=dict(color="#a78bfa")), row=1,col=1)
        fig_ec.add_hline(y=750,  row=1,col=1, line_dash="dot", line_color="#10b981",
                         annotation_text="FAO irrigation (750)")
        fig_ec.add_hline(y=1500, row=1,col=1, line_dash="dot", line_color="#f59e0b",
                         annotation_text="WHO drinking (1500)")
        fig_ec.add_hline(y=5000, row=1,col=1, line_dash="dash",line_color="#dc2626",
                         annotation_text="Critical (5000)")
        fig_ec.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["TDS_mg_L"], name="TDS",
            line=dict(color="#c084fc")), row=2,col=1)
        fig_ec.add_hline(y=1000, row=2,col=1, line_dash="dot", line_color="#f59e0b",
                         annotation_text="WHO limit 1000 mg/L")
        fig_ec.update_layout(template="plotly_dark", height=520)
        st.plotly_chart(fig_ec, use_container_width=True)

        # EC vs Flow inverse relationship
        _df_ecf = df_wq[["Flow_BCM","EC_uS_cm"]].replace([np.inf,-np.inf], np.nan).dropna()
        _df_ecf = _df_ecf[_df_ecf["Flow_BCM"] > 0]
        _df_ecf = _df_ecf.sample(min(500, len(_df_ecf))) if len(_df_ecf) > 0 else _df_ecf
        fig_ecf = px.scatter(
            _df_ecf,
            x="Flow_BCM", y="EC_uS_cm",
            trendline="lowess" if len(_df_ecf) >= 10 else None,
            template="plotly_dark", height=320,
            title="EC vs Flow — Concentration-Dilution Relationship",
            color_discrete_sequence=["#a78bfa"]
        )
        st.plotly_chart(fig_ecf, use_container_width=True)
        st.caption("EC rises when flow drops — classic concentration effect due to "
                   "evaporation and reduced dilution of naturally occurring salts.")

    # ── Tab 4: Temperature & pH ──────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Temperature & pH")

        fig_tp = make_subplots(rows=2,cols=1,shared_xaxes=True,
                               subplot_titles=["Water Temperature (°C)","pH"])
        fig_tp.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["Temp_C"], name="Temp",
            line=dict(color="#f97316")), row=1,col=1)
        fig_tp.add_hline(y=30, row=1,col=1, line_dash="dot", line_color="#f59e0b",
                         annotation_text="Thermal stress (30°C)")
        fig_tp.add_hline(y=35, row=1,col=1, line_dash="dash",line_color="#dc2626",
                         annotation_text="Critical (35°C)")
        fig_tp.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["pH"], name="pH",
            line=dict(color="#34d399")), row=2,col=1)
        fig_tp.add_hrect(y0=6.5, y1=8.5, row=2,col=1,
                         fillcolor="rgba(16,185,129,0.08)",
                         line_width=0, annotation_text="WHO range 6.5–8.5")
        fig_tp.add_hline(y=6.0, row=2,col=1, line_dash="dash",line_color="#f59e0b",
                         annotation_text="Concern (6.0)")
        fig_tp.add_hline(y=9.0, row=2,col=1, line_dash="dash",line_color="#f59e0b")
        fig_tp.update_layout(template="plotly_dark", height=520)
        st.plotly_chart(fig_tp, use_container_width=True)

        # Seasonal means
        df_wq["Month"] = pd.to_datetime(df_wq["Date"]).dt.month
        month_lbl = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        mo_temp   = df_wq.groupby("Month")["Temp_C"].mean()
        mo_ph     = df_wq.groupby("Month")["pH"].mean()
        fig_seas  = go.Figure()
        fig_seas.add_trace(go.Bar(x=month_lbl, y=mo_temp.values,
                                  name="Temp (°C)", marker_color="#f97316"))
        fig_seas.add_trace(go.Scatter(x=month_lbl, y=mo_ph.values*3,
                                      name="pH ×3", yaxis="y2",
                                      line=dict(color="#34d399",width=2)))
        fig_seas.update_layout(
            template="plotly_dark", height=320,
            title="Seasonal Temperature & pH",
            yaxis2=dict(overlaying="y",side="right",title="pH ×3",showgrid=False)
        )
        st.plotly_chart(fig_seas, use_container_width=True)

    # ── Tab 5: Nitrates & Metals ─────────────────────────────────────────────
    with tabs[4]:
        st.subheader("Agricultural Pollution & Heavy Metals")

        fig_nm = make_subplots(rows=2,cols=1,shared_xaxes=True,
                               subplot_titles=["Nitrate NO₃⁻ (mg/L)",
                                               "Heavy Metals Index"])
        fig_nm.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["Nitrate_mg_L"], name="Nitrate",
            line=dict(color="#84cc16"), fill="tozeroy",
            fillcolor="rgba(132,204,22,0.1)"), row=1,col=1)
        fig_nm.add_hline(y=10,  row=1,col=1, line_dash="dot", line_color="#f59e0b",
                         annotation_text="WHO drinking limit 10 mg/L")
        fig_nm.add_hline(y=50,  row=1,col=1, line_dash="dash",line_color="#dc2626",
                         annotation_text="EU limit 50 mg/L")
        fig_nm.add_trace(go.Scatter(
            x=df_wq["Date"], y=df_wq["HeavyMetal_idx"], name="Heavy Metals",
            line=dict(color="#f43f5e")), row=2,col=1)
        fig_nm.add_hline(y=0.6,  row=2,col=1, line_dash="dot", line_color="#f59e0b",
                         annotation_text="Monitoring threshold (0.6)")
        fig_nm.add_hline(y=1.0,  row=2,col=1, line_dash="dash",line_color="#dc2626",
                         annotation_text="Remediation trigger (1.0)")
        fig_nm.update_layout(template="plotly_dark", height=520)
        st.plotly_chart(fig_nm, use_container_width=True)

    # ── Tab 6: Compliance Table ──────────────────────────────────────────────
    with tabs[5]:
        st.subheader("📋 WHO/FAO Compliance Summary")

        def _style_status(val):
            if "Violation" in str(val): return "background-color:#1c0a0a;color:#fca5a5"
            if "Concern"   in str(val): return "background-color:#1c1005;color:#fde68a"
            return "background-color:#071a12;color:#6ee7b7"

        styled_comp = compliance.style.map(_style_status, subset=["Status"])
        st.dataframe(styled_comp, use_container_width=True, hide_index=True)

        # Monthly aggregates
        st.markdown("#### Monthly Mean Quality Parameters")
        df_wq["Month"] = pd.to_datetime(df_wq["Date"]).dt.month
        monthly = df_wq.groupby("Month").agg({
            "EC_uS_cm":"mean","DO_mg_L":"mean","BOD_mg_L":"mean",
            "pH":"mean","Turbidity_NTU":"mean","Nitrate_mg_L":"mean",
            "WQI":"mean"
        }).round(2).reset_index()
        monthly["Month"] = ["Jan","Feb","Mar","Apr","May","Jun",
                             "Jul","Aug","Sep","Oct","Nov","Dec"]
        st.dataframe(monthly, use_container_width=True, hide_index=True)

    # ── Tab 7: Legal Art. 20/21 ──────────────────────────────────────────────
    with tabs[6]:
        st.subheader("⚖️ Legal Compliance: Articles 20 & 21 (UN 1997)")

        st.markdown("""
| Article | Obligation | HSAE Indicator |
|---------|-----------|----------------|
| **Art. 20** | Protect and preserve ecosystems | DO > 6 mg/L  ·  Temp < 30°C  ·  pH 6–9 |
| **Art. 21** | Prevent, reduce and control pollution | EC < 1500  ·  BOD < 5  ·  NO₃ < 10  ·  HM < 0.6 |
| **Art. 9**  | Exchange water quality data | Full WQI time-series as transparency record |
""")

        # Art 20 status
        do_viol  = int((df_wq["DO_mg_L"]   < 3.0).sum())
        temp_viol= int((df_wq["Temp_C"]    > 35.0).sum())
        ph_viol  = int(((df_wq["pH"]<5.0) | (df_wq["pH"]>10.0)).sum())
        # Art 21 status
        ec_viol  = int((df_wq["EC_uS_cm"]    > 2500).sum())
        bod_viol = int((df_wq["BOD_mg_L"]    > 10.0).sum())
        no3_viol = int((df_wq["Nitrate_mg_L"]> 50.0).sum())
        hm_viol  = int((df_wq["HeavyMetal_idx"]> 1.0).sum())

        c1,c2 = st.columns(2)
        with c1:
            st.markdown("#### 🌿 Art. 20 — Ecosystem Protection")
            for metric, viol, ok_thr, label in [
                ("DO",   do_viol,   0,  "DO < 3 mg/L (ecosystem collapse)"),
                ("Temp", temp_viol, 0,  "Temp > 35°C (thermal pollution)"),
                ("pH",   ph_viol,   0,  "pH outside 5–10 (extreme)"),
            ]:
                color = "#dc2626" if viol > 0 else "#10b981"
                st.markdown(
                    f"<div style='padding:0.5rem;background:#0f172a;"
                    f"border-left:4px solid {color};border-radius:6px;margin:4px 0;'>"
                    f"<b style='color:{color};'>{metric}</b>: {viol} violation days — {label}"
                    f"</div>", unsafe_allow_html=True
                )
        with c2:
            st.markdown("#### 🚫 Art. 21 — Pollution Prevention")
            for metric, viol, label in [
                ("EC",  ec_viol,  "EC > 2500 μS/cm (salinity)"),
                ("BOD", bod_viol, "BOD > 10 mg/L (organic load)"),
                ("NO₃", no3_viol, "Nitrate > 50 mg/L (agriculture)"),
                ("HM",  hm_viol,  "Heavy Metal Index > 1.0 (mining)"),
            ]:
                color = "#dc2626" if viol > 0 else "#10b981"
                st.markdown(
                    f"<div style='padding:0.5rem;background:#0f172a;"
                    f"border-left:4px solid {color};border-radius:6px;margin:4px 0;'>"
                    f"<b style='color:{color};'>{metric}</b>: {viol} violation days — {label}"
                    f"</div>", unsafe_allow_html=True
                )

        total_violations = do_viol + temp_viol + ph_viol + ec_viol + bod_viol + no3_viol + hm_viol
        if total_violations == 0:
            st.success("✅ All Art. 20/21 water quality thresholds within compliance range.")
        else:
            st.error(
                f"🚨 **{total_violations} total violation-days** detected. "
                f"Art. 20/21 compliance requires immediate upstream notification "
                f"and remediation measures under UN 1997 Convention."
            )

    # ── Tab 8: Export ────────────────────────────────────────────────────────
    with tabs[7]:
        c1,c2,c3 = st.columns(3)
        c1.download_button(
            "📊 Full WQ CSV",
            df_wq.to_csv(index=False).encode("utf-8"),
            file_name=f"HSAE_WQ_{basin_id}.csv", mime="text/csv"
        )
        c2.download_button(
            "📋 Compliance Report CSV",
            compliance.to_csv(index=False).encode("utf-8"),
            file_name=f"HSAE_WQ_Compliance_{basin_id}.csv", mime="text/csv"
        )
        html_r = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>HSAE Water Quality Report — {basin_id}</title>
<style>body{{font-family:Arial;margin:30px;}}h1{{color:#0284c7;}}
table{{border-collapse:collapse;width:100%;font-size:0.85rem;}}
th,td{{border:1px solid #cbd5e1;padding:7px;}}th{{background:#0c4a6e;color:#fff;}}
.viol{{background:#fef2f2;color:#dc2626;}}
.concern{{background:#fffbeb;color:#d97706;}}</style>
</head><body>
<h1>Water Quality Report — {basin_id}</h1>
<p><b>Basin:</b> {basin_id} — {basin.get("river","—")}<br>
<b>Period:</b> {df_wq["Date"].iloc[0].date()} → {df_wq["Date"].iloc[-1].date()}<br>
<b>WQI Mean:</b> {wqi_mean:.1f}/100 | <b>Violations:</b> {n_critical} params | 
<b>Concerns:</b> {n_concern} params</p>
<h2>Compliance Summary (WHO 2017 / FAO-56 / UN 1997)</h2>
<table><tr>{''.join(f"<th>{c}</th>" for c in compliance.columns)}</tr>
{''.join('<tr>' + ''.join(f'<td class={"viol" if "Violation" in str(row.get("Status","")) else "concern" if "Concern" in str(row.get("Status","")) else ""}>{v}</td>' for v in row.values()) + '</tr>' for row in compliance.to_dict("records"))}
</table>
<p style="font-size:0.8rem;color:#64748b;margin-top:20px;">
Generated: {datetime.utcnow().strftime("%d %B %Y %H:%M UTC")} | 
Legal basis: UN 1997 Watercourses Convention Arts. 20–21
</p></body></html>"""
        c3.download_button(
            "📄 HTML Legal Report",
            html_r.encode("utf-8"),
            file_name=f"HSAE_WQ_Legal_{basin_id}.html", mime="text/html"
        )
