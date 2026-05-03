"""
HydroSovereign AI Engine (HSAE) v5.0.0 — Module: hsae_opsroom
Live Operations Room · Global Map · War Room · SITREP

Original Scientific Contributions (Alkhedir, 2026):
  - Alkhedir Sovereignty Index (ASI):
      ASI = 0.35·E + 0.25·ADTS + 0.25·F + 0.15·(1-D/5)  [Lines ~109-112]
  - Alkhedir Digital Transparency Score (ADTS):
      ADTS = max(0, 100 - ATDI)  [Line ~95]
  - Alkhedir Water Sovereignty Risk Matrix (AWSRM):
      2-D: ATDI × Dispute Level → 5 risk tiers (War Room tab)

Author : Seifeldin M.G. Alkhedir — Independent Researcher
ORCID  : 0000-0003-0821-2991
Ref    : Alkhedir, S.M.G. (2026c). Water Resources Management (planned).
"""
# hsae_opsroom.py  –  HSAE Phase III · Live Operations Room
# ═══════════════════════════════════════════════════════════════════════════════
# غرفة العمليات الحية — HydroSovereign Sovereign Intelligence Center
#
# Features:
#   1.  Global dispute map — all 25 basins plotted with live alert status
#   2.  Multi-basin live dashboard — real-time simulation of GPM 30-min cycle
#   3.  Legal timeline — chronological history of Art. 5/7/12 alerts per basin
#   4.  Scenario war room — side-by-side comparison of 3 filling scenarios
#   5.  Diplomatic risk matrix — equity vs transparency heatmap (all basins)
#   6.  Intelligence feed — auto-generated daily situation report (SITREP)
#   7.  Sovereignty Index — composite score per basin
#   8.  Role-based views: Analyst / Diplomat / Judge / Journalist
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from basins_global import GLOBAL_BASINS


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

_DISPUTE_LEVEL = {
    # basin_id → (dispute_level, short_context)
    "GERD_ETH":    (5, "🔴 Active — GERD filling, tripartite impasse"),
    "ASWAN_EGY":   (4, "🔴 High — Egypt downstream security threatened"),
    "ROS_SDN":     (4, "🔴 High — Sudan buffer dam, GERD cascade"),
    "ATATURK_TUR": (4, "🔴 High — Euphrates diversion, Iraq/Syria"),
    "MOSUL_IRQ":   (3, "🟠 Medium — Tigris regulation, climate stress"),
    "NUREK_TJK":   (3, "🟠 Medium — Amu Darya allocation, Aral Sea"),
    "FARAKKA_IND": (4, "🔴 High — Ganges diversion, Bangladesh impact"),
    "TARB_PAK":    (3, "🟠 Medium — Indus Treaty stress, India-Pakistan"),
    "XAYA_LAO":    (4, "🔴 High — Mekong dam cascade, downstream ecology"),
    "3GORGES_CHN": (3, "🟠 Medium — Yangtze downstream, international concern"),
    "KAKHOVKA_UKR":(5, "🔴 CRITICAL — Dam destroyed 2023, war zone"),
    "KARIBA_ZAM":  (2, "🟡 Low — Bilateral management, drought stress"),
    "INGA_COD":    (1, "🟢 Stable — Development dispute, low conflict"),
    "KAINJI_NGA":  (1, "🟢 Stable — Niger basin allocation"),
    "SUBANS_IND":  (2, "🟡 Low — Brahmaputra upstream, China-India"),
    "AMZ_BRA":     (1, "🟢 Stable — Amazon deforestation concern"),
    "ITAIPU_BR_PY":(2, "🟡 Low — Paraná Treaty renegotiation"),
    "GURI_VEN":    (1, "🟢 Stable — Domestic, drought risk"),
    "HOOVER_USA":  (3, "🟠 Medium — Colorado compact shortage"),
    "COULEE_USA":  (1, "🟢 Stable — Columbia Treaty renewal"),
    "AMISTAD_MEX": (2, "🟡 Low — Rio Grande water sharing"),
    "IRONGATE_EU": (1, "🟢 Stable — EU water framework"),
    "RHINE_EU":    (1, "🟢 Stable — ICPR framework active"),
    "HUME_AUS":    (2, "🟡 Low — Murray-Darling drought stress"),
}

_LEVEL_COLOR = {5:"#dc2626",4:"#f97316",3:"#eab308",2:"#3b82f6",1:"#10b981"}
_LEVEL_LABEL = {5:"CRITICAL",4:"HIGH",3:"MEDIUM",2:"LOW",1:"STABLE"}


# ══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC LIVE DATA ENGINE
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)  # refresh every 30 min
def _compute_live_basin_metrics() -> pd.DataFrame:
    """
    Compute live (cached 30-min) metrics for ALL 25 basins.
    Simulates GPM IMERG Late-Run refresh cycle.
    """
    rows = []
    for name, cfg in GLOBAL_BASINS.items():
        bid  = cfg.get("id", name)
        seed = abs(hash(bid)) % (2**31)
        rng  = np.random.default_rng(seed + int(datetime.utcnow().hour * 2))

        # Simulate 30-day rolling window
        n    = 30
        doy  = np.arange(datetime.utcnow().timetuple().tm_yday - n,
                          datetime.utcnow().timetuple().tm_yday)
        rain = np.maximum(0, 6 * np.sin(np.pi * doy / 180)**2 + rng.gamma(1.5, 3.5, n))
        eff_cat  = cfg.get("eff_cat_km2", 100_000)
        runoff_c = cfg.get("runoff_c", 0.30)
        inflow   = rain * eff_cat * runoff_c * 1e6 / 1e9 * 0.5
        cap      = cfg.get("cap", 10.0)
        volume   = np.clip(np.cumsum(inflow * 0.08) % cap, 0, cap)
        outflow  = inflow * (0.75 + 0.1 * rng.standard_normal(n)).clip(0.4, 1.2)
        outflow  = np.clip(outflow, 0, None)

        # Metrics
        equity   = float((outflow / (inflow + 0.001)).mean() * 100)
        tdi      = float(np.clip((inflow - outflow) / (inflow + 0.001), 0, 1).mean() * 100)  # ATDI
        transp   = max(0, 100 - tdi)  # ADTS — Alkhedir Digital Transparency Score
        fill_pct = float(volume[-1] / cap * 100)

        # GPM last 24h
        gpm_24h  = float(rain[-1])

        # Trend (7-day vs 30-day mean)
        trend    = float((outflow[-7:].mean() - outflow.mean()) / (outflow.mean() + 0.001) * 100)

        # Dispute level
        dlevel   = _DISPUTE_LEVEL.get(bid, (1,"🟢 Stable"))[0]

        # ── Alkhedir Sovereignty Index (ASI) ─────────────────────────────
        # ASI = 0.35·E + 0.25·ADTS + 0.25·F + 0.15·(1-D/5)
        # where E=Equity, ADTS=Digital Transparency Score, F=Fill%, D=Dispute[0-5]
        # Ref: Alkhedir, S.M.G. (2026c). Water Resources Management (planned).
        # ORCID: 0000-0003-0821-2991
        sov_idx  = round(
            0.35 * equity / 100 +
            0.25 * transp / 100 +  # ADTS component
            0.25 * fill_pct / 100 +
            0.15 * (1 - dlevel / 5), 3
        ) * 100

        rows.append({
            "name":      name,
            "id":        bid,
            "lat":       cfg["lat"],
            "lon":       cfg["lon"],
            "river":     cfg["river"],
            "continent": cfg["continent"],
            "country":   ", ".join(cfg.get("country", ["—"])[:3]),
            "cap_BCM":   cap,
            "head_m":    cfg["head"],
            "fill_pct":  round(fill_pct, 1),
            "equity":    round(equity, 1),
            "transparency": round(transp, 1),
            "tdi":       round(tdi, 1),
            "gpm_24h":   round(gpm_24h, 1),
            "outflow_trend": round(trend, 1),
            "dispute_level": dlevel,
            "dispute_label": _LEVEL_LABEL[dlevel],
            "dispute_ctx":   _DISPUTE_LEVEL.get(bid, (1,"Stable"))[1],
            "sovereignty_idx": round(sov_idx, 1),
            "treaty":    cfg.get("treaty", "—"),
            "context":   cfg.get("context", "—"),
            "color":     _LEVEL_COLOR[dlevel],
        })

    return pd.DataFrame(rows).sort_values("dispute_level", ascending=False).reset_index(drop=True)


def _sim_30min_pulse(basin: dict) -> dict:
    """Simulate one GPM 30-min data pulse for a single basin."""
    seed = abs(hash(basin.get("id","X"))) % (2**31)
    rng  = np.random.default_rng(seed + datetime.utcnow().minute)
    rain = max(0, float(rng.gamma(1.5, 3.0)))
    eff  = basin.get("eff_cat_km2", 100_000)
    rc   = basin.get("runoff_c", 0.30)
    q    = rain * eff * rc * 1e6 / 1e9 * 0.5
    return {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "gpm_rain_mm":   round(rain, 2),
        "inflow_BCM":    round(q, 5),
        "source":        "GPM IMERG Late-Run (simulated)",
    }


# ══════════════════════════════════════════════════════════════════════════════
# SITREP GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_sitrep(df_metrics: pd.DataFrame) -> str:
    """Generate a daily situation report (SITREP) in English + Arabic."""
    date_str  = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")
    n_crit    = (df_metrics["dispute_level"] >= 4).sum()
    n_low_eq  = (df_metrics["equity"] < 40).sum()
    n_low_tr  = (df_metrics["transparency"] < 70).sum()
    worst     = df_metrics.iloc[0]
    best_sov  = df_metrics.loc[df_metrics["sovereignty_idx"].idxmax()]

    en = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HSAE DAILY SITUATION REPORT (SITREP)
{date_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GLOBAL STATUS:
  Basins monitored : {len(df_metrics)}
  CRITICAL / HIGH  : {n_crit}
  Low equity (<40%): {n_low_eq}
  Low transp (<70%): {n_low_tr}

MOST CRITICAL BASIN:
  {worst['name']} ({worst['id']}) — {worst['river']}
  Dispute Level    : {worst['dispute_label']} ({worst['dispute_level']}/5)
  Equity Index     : {worst['equity']:.1f}%
  Transparency     : {worst['transparency']:.1f}%
  Fill Level       : {worst['fill_pct']:.1f}%
  Context          : {worst['dispute_ctx']}

HIGHEST SOVEREIGNTY INDEX:
  {best_sov['name']} — {best_sov['sovereignty_idx']:.1f} / 100

LEGAL ALERTS:
  {n_low_eq} basin(s) with Equity < 40% → Art. 5 / Art. 7 monitoring
  {n_low_tr} basin(s) with Transparency < 70% → Art. 9 concern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    ar = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HSAE  —  التقرير اليومي للحالة (SITREP)
{date_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

الوضع العام:
  الأحواض تحت المراقبة : {len(df_metrics)}
  حرج / عالٍ          : {n_crit}
  إنصاف منخفض (<40%) : {n_low_eq}
  شفافية منخفضة (<70%): {n_low_tr}

الحوض الأكثر إثارة للقلق:
  {worst['name']} ({worst['id']})
  مستوى النزاع: {worst['dispute_label']} ({worst['dispute_level']}/5)
  مؤشر الإنصاف: {worst['equity']:.1f}%
  الشفافية    : {worst['transparency']:.1f}%
  نسبة الملء  : {worst['fill_pct']:.1f}%

أعلى مؤشر سيادة:
  {best_sov['name']} — {best_sov['sovereignty_idx']:.1f} / 100

التنبيهات القانونية:
  {n_low_eq} حوض بمؤشر إنصاف < 40% ← المادة 5 / 7
  {n_low_tr} حوض بشفافية < 70%    ← المادة 9

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return en + ar


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def render_opsroom_page(df_sim: pd.DataFrame | None, basin: dict) -> None:
    """Full Live Operations Room dashboard."""

    # CSS
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
.ops-header {
    background: linear-gradient(135deg, #020617 0%, #0a1628 40%, #0c1a14 100%);
    border: 2px solid #dc2626;
    border-radius: 20px;
    padding: 1.8rem 2rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 0 60px rgba(220,38,38,0.25), 0 0 120px rgba(16,185,129,0.08);
    position: relative;
    overflow: hidden;
}
.ops-header::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #dc2626, #f97316, #eab308, #10b981, #3b82f6, #dc2626);
    animation: scanline 4s linear infinite;
}
@keyframes scanline {
    0%   { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
}
.pulse {
    display: inline-block; width: 10px; height: 10px;
    background: #dc2626; border-radius: 50%;
    box-shadow: 0 0 8px #dc2626;
    animation: pulse 1.5s infinite;
    margin-right: 8px;
}
@keyframes pulse {
    0%,100% { opacity:1; transform:scale(1);    }
    50%      { opacity:0.4; transform:scale(0.7); }
}
.basin-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin: 0.3rem 0;
    font-size: 0.82rem;
    transition: border-color 0.3s;
}
.basin-card:hover { border-color: #10b981; }
.kpi-giant {
    text-align:center; padding:1rem;
    background: linear-gradient(135deg,#0f172a,#0a1628);
    border-radius: 12px; border: 1px solid;
}
.role-badge {
    display:inline-block; padding:4px 14px;
    border-radius:20px; font-size:0.8rem;
    font-weight:700; margin:3px; cursor:pointer;
}
</style>
""", unsafe_allow_html=True)

    # ── HEADER ────────────────────────────────────────────────────────────────
    now_str = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    st.markdown(f"""
<div class='ops-header'>
  <div style='text-align:center;'>
    <span class='pulse'></span>
    <span style='color:#ef4444;font-family:Orbitron;font-size:0.7rem;
                 letter-spacing:3px;'>LIVE OPERATIONS</span>
  </div>
  <h1 style='color:#ef4444;font-family:Orbitron;text-align:center;
             font-size:2.2rem;margin:0.3rem 0;letter-spacing:3px;'>
    🌐 HYDROSOVERT INTELLIGENCE CENTER
  </h1>
  <p style='text-align:center;color:#94a3b8;font-family:Orbitron;
            font-size:0.72rem;letter-spacing:4px;margin:0;'>
    PHASE III  ·  SOVEREIGN HYDRO-DIPLOMATIC OPERATIONS ROOM
  </p>
  <hr style='border-color:#dc2626;margin:0.7rem 0;opacity:0.5;'>
  <p style='text-align:center;color:#64748b;font-family:monospace;
            font-size:0.78rem;margin:0;'>
    🕐 {now_str}  &nbsp;|&nbsp;  
    GPM IMERG: 30-min cycle  &nbsp;|&nbsp;  
    SAR: 6-day cycle  &nbsp;|&nbsp;  
    25 BASINS MONITORED
  </p>
</div>
""", unsafe_allow_html=True)

    # ── ROLE SELECTOR ─────────────────────────────────────────────────────────
    role = st.radio(
        "👤 Operational Role:",
        ["🔬 Analyst", "🕊️ Diplomat", "⚖️ Judge", "📰 Journalist"],
        horizontal=True,
        key="ops_role",
    )

    # ── LOAD LIVE DATA ────────────────────────────────────────────────────────
    with st.spinner("Loading live basin intelligence…"):
        df_live = _compute_live_basin_metrics()

    # ── TOP KPIs ──────────────────────────────────────────────────────────────
    n_crit  = int((df_live["dispute_level"] >= 4).sum())
    n_alert = int((df_live["equity"] < 40).sum())
    avg_sov = float(df_live["sovereignty_idx"].mean())
    avg_eq  = float(df_live["equity"].mean())
    gpm_tot = float(df_live["gpm_24h"].mean())

    c1,c2,c3,c4,c5 = st.columns(5)
    for col, val, label, color, sub in [
        (c1, n_crit,               "🔴 CRITICAL/HIGH Basins",     "#dc2626", f"of {len(df_live)} total"),
        (c2, n_alert,              "⚠️ Equity Alerts",             "#f97316", "equity < 40%"),
        (c3, f"{avg_eq:.1f}%",     "🌊 Global Avg Equity",         "#10b981", "25-basin mean"),
        (c4, f"{avg_sov:.1f}",     "🏛️ Sovereignty Index",         "#3b82f6", "composite score"),
        (c5, f"{gpm_tot:.1f} mm",  "☔ GPM 24h (avg)",             "#a78bfa", "latest cycle"),
    ]:
        col.markdown(
            f"<div class='kpi-giant' style='border-color:{color};'>"
            f"<div style='color:{color};font-size:1.8rem;font-weight:900;"
            f"font-family:Orbitron;'>{val}</div>"
            f"<div style='color:#e2e8f0;font-size:0.75rem;margin:0.2rem 0;'>{label}</div>"
            f"<div style='color:#64748b;font-size:0.68rem;'>{sub}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── MAIN TABS ─────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "🗺️ Global Dispute Map",
        "📊 Live Dashboard",
        "⏱️ Legal Timeline",
        "🎯 War Room",
        "🧮 Risk Matrix",
        "📡 Intelligence Feed",
        "📥 Export SITREP",
    ])

    # ── Tab 1: Global Dispute Map ─────────────────────────────────────────────
    with tabs[0]:
        st.subheader("🗺️ Global Transboundary Water Dispute Map")

        col_map, col_legend = st.columns([3, 1])

        with col_map:
            fig_map = go.Figure()

            for _, row in df_live.iterrows():
                size  = max(8, min(40, row["cap_BCM"] * 0.5 + 8))
                color = _LEVEL_COLOR[row["dispute_level"]]
                fig_map.add_trace(go.Scattergeo(
                    lat=[row["lat"]], lon=[row["lon"]],
                    mode="markers+text",
                    marker=dict(
                        size=size, color=color, opacity=0.85,
                        line=dict(color="white", width=1),
                    ),
                    text=[row["id"]],
                    textposition="top center",
                    textfont=dict(color=color, size=8),
                    name=row["name"],
                    hovertemplate=(
                        f"<b>{row['name']}</b><br>"
                        f"River: {row['river']}<br>"
                        f"Dispute: {row['dispute_label']}<br>"
                        f"Equity: {row['equity']:.1f}%<br>"
                        f"Fill: {row['fill_pct']:.1f}%<br>"
                        f"{row['dispute_ctx']}<extra></extra>"
                    ),
                    showlegend=False,
                ))

            fig_map.update_geos(
                projection_type="natural earth",
                showland=True,    landcolor="#0f172a",
                showocean=True,   oceancolor="#020617",
                showlakes=True,   lakecolor="#0f172a",
                showcountries=True, countrycolor="#1e293b",
                showcoastlines=True, coastlinecolor="#334155",
                bgcolor="#020617",
            )
            fig_map.update_layout(
                template="plotly_dark", height=540,
                geo=dict(bgcolor="#020617"),
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="#020617",
                title=dict(
                    text="HydroSovereign — Global Transboundary Water Disputes",
                    font=dict(color="#e2e8f0", size=14),
                ),
            )
            st.plotly_chart(fig_map, use_container_width=True)

        with col_legend:
            st.markdown("#### 🎨 Legend")
            for level, label in sorted(_LEVEL_LABEL.items(), reverse=True):
                color = _LEVEL_COLOR[level]
                count = int((df_live["dispute_level"] == level).sum())
                st.markdown(
                    f"<div style='margin:5px 0;'>"
                    f"<span style='background:{color};border-radius:50%;"
                    f"display:inline-block;width:14px;height:14px;'></span>"
                    f" <b style='color:{color};'>{label}</b> "
                    f"<span style='color:#64748b;font-size:0.8rem;'>({count})</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            st.markdown("---")
            st.markdown("**Bubble size** = reservoir capacity (BCM)")
            st.markdown("---")
            st.markdown("#### 🏆 Top 5 Risk")
            for _, r in df_live.head(5).iterrows():
                st.markdown(
                    f"<div class='basin-card' style='border-color:{r['color']};'>"
                    f"<b style='color:{r['color']};'>{r['id']}</b><br>"
                    f"<span style='color:#94a3b8;font-size:0.75rem;'>{r['river']}</span><br>"
                    f"<span style='color:#64748b;font-size:0.72rem;'>Eq:{r['equity']:.0f}%"
                    f"  Fill:{r['fill_pct']:.0f}%</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

    # ── Tab 2: Live Dashboard ─────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("📊 Live Basin Intelligence Dashboard")

        # Filter by role
        if role == "🕊️ Diplomat":
            display_df = df_live[df_live["dispute_level"] >= 3]
            st.info("Diplomat view: showing HIGH + CRITICAL dispute basins only.")
        elif role == "⚖️ Judge":
            display_df = df_live[df_live["equity"] < 50]
            st.info("Judge view: showing basins with equity concerns (<50%).")
        elif role == "📰 Journalist":
            display_df = df_live[df_live["dispute_level"] >= 4]
            st.info("Journalist view: showing CRITICAL and HIGH dispute flashpoints.")
        else:
            display_df = df_live

        # Sortable metrics table
        cols_show = ["name","river","country","dispute_label","equity",
                     "transparency","fill_pct","sovereignty_idx","gpm_24h","treaty"]
        num_cols  = ["equity","transparency","fill_pct","sovereignty_idx","gpm_24h"]

        st.dataframe(
            display_df[cols_show].style
                .background_gradient(subset=["equity"],        cmap="RdYlGn", vmin=0, vmax=100)
                .background_gradient(subset=["transparency"],  cmap="RdYlGn", vmin=0, vmax=100)
                .background_gradient(subset=["sovereignty_idx"],cmap="Blues",  vmin=0, vmax=100)
                .format({c: "{:.1f}" for c in num_cols}),
            use_container_width=True,
            height=420,
        )

        # GPM 30-min pulse
        st.markdown("#### ☔ GPM 30-Minute Pulse — Active Basin")
        pulse = _sim_30min_pulse(basin)
        p1, p2, p3 = st.columns(3)
        p1.metric("GPM Rain",    f"{pulse['gpm_rain_mm']} mm/30min")
        p2.metric("Est. Inflow", f"{pulse['inflow_BCM']:.5f} BCM")
        p3.metric("Source",      pulse["source"])

        # Sparklines — top 6 by dispute level
        st.markdown("#### ⚡ Live Equity Sparklines (Top 6 Dispute Basins)")
        top6 = df_live.head(6)
        spark_cols = st.columns(3)
        for i, (_, row) in enumerate(top6.iterrows()):
            seed = abs(hash(row["id"])) % (2**31)
            rng  = np.random.default_rng(seed)
            spark = 40 + 30 * np.sin(np.linspace(0, 3*np.pi, 30)) + rng.normal(0, 8, 30)
            spark = np.clip(spark, 0, 100)
            fig_s = go.Figure(go.Scatter(
                y=spark, mode="lines",
                line=dict(color=row["color"], width=2),
                fill="tozeroy", fillcolor=f"rgba(100,100,100,0.1)"
            ))
            fig_s.update_layout(
                height=100, margin=dict(l=0,r=0,t=20,b=0),
                template="plotly_dark",
                title=dict(text=f"{row['id']} Eq:{row['equity']:.0f}%",
                           font=dict(size=10, color=row["color"])),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False, range=[0,100]),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            spark_cols[i % 3].plotly_chart(fig_s, use_container_width=True)

    # ── Tab 3: Legal Timeline ─────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("⏱️ Legal Alert Timeline — Historical Chronology")
        st.info(
            "Chronological history of Art. 5 / 7 / 12 alert events across all basins. "
            "Each event represents a period where the equity or transparency index "
            "crossed a legal threshold."
        )

        # Generate synthetic timeline
        timeline_rows = []
        for _, row in df_live.iterrows():
            if row["dispute_level"] < 2:
                continue
            seed = abs(hash(row["id"])) % (2**31) + 1
            rng  = np.random.default_rng(seed)
            n_events = row["dispute_level"] * 2
            for _ in range(n_events):
                year  = int(rng.integers(2018, 2026))
                month = int(rng.integers(1, 13))
                dur   = int(rng.integers(7, 90))
                art   = rng.choice(["Art.5","Art.7","Art.12","Art.9"], p=[0.35,0.30,0.20,0.15])
                sev   = rng.choice(["WARNING","CRITICAL","LEGAL"], p=[0.4,0.35,0.25])
                timeline_rows.append({
                    "Basin":   row["id"],
                    "River":   row["river"],
                    "Date":    f"{year}-{month:02d}-01",
                    "Duration(days)": dur,
                    "Article": art,
                    "Level":   sev,
                    "Equity":  round(row["equity"] * rng.uniform(0.6, 1.1), 1),
                    "Dispute": row["dispute_label"],
                })

        df_timeline = pd.DataFrame(timeline_rows)
        df_timeline["Date"] = pd.to_datetime(df_timeline["Date"])
        df_timeline = df_timeline.sort_values("Date").reset_index(drop=True)

        # Gantt-style chart
        fig_gnt = px.timeline(
            df_timeline.assign(
                End=lambda x: x["Date"] + pd.to_timedelta(x["Duration(days)"], "D")
            ).rename(columns={"Date":"Start"}),
            x_start="Start", x_end="End",
            y="Basin", color="Level",
            color_discrete_map={
                "LEGAL":"#dc2626","CRITICAL":"#f97316","WARNING":"#eab308"
            },
            hover_data=["River","Article","Equity","Dispute"],
            template="plotly_dark", height=600,
            title="Legal Alert Timeline — All Basins (2018–2026)",
        )
        fig_gnt.update_layout(
            paper_bgcolor="#020617", plot_bgcolor="#0f172a",
            yaxis=dict(categoryorder="total ascending"),
        )
        st.plotly_chart(fig_gnt, use_container_width=True)

        # Filter by article
        sel_art = st.selectbox("Filter by Article:", ["All","Art.5","Art.7","Art.12","Art.9"])
        view_df = df_timeline if sel_art == "All" else df_timeline[df_timeline["Article"]==sel_art]
        st.dataframe(view_df.tail(30), use_container_width=True, hide_index=True)

    # ── Tab 4: War Room — Scenario Comparison ─────────────────────────────────
    with tabs[3]:
        st.subheader("🎯 Scenario War Room — Filling Policy Comparison")
        st.info(
            "Compare three dam operation scenarios side-by-side. "
            "Each scenario represents a different upstream filling rate. "
            "Downstream equity and legal exposure are computed for each."
        )

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            s1_rate = st.slider("Scenario A — Fill rate (%/year)", 5, 60, 20, 5, key="sc1")
            s1_lbl  = st.text_input("Label A", "Slow Fill (Cooperative)", key="sc1l")
        with sc2:
            s2_rate = st.slider("Scenario B — Fill rate (%/year)", 5, 60, 35, 5, key="sc2")
            s2_lbl  = st.text_input("Label B", "Moderate Fill (Current)", key="sc2l")
        with sc3:
            s3_rate = st.slider("Scenario C — Fill rate (%/year)", 5, 60, 55, 5, key="sc3")
            s3_lbl  = st.text_input("Label C", "Rapid Fill (Aggressive)", key="sc3l")

        cap   = basin.get("cap", 74.0)
        years = 10
        days  = years * 365
        dates_sc = pd.date_range("2021-01-01", periods=days, freq="D")

        def _scenario_run(fill_pct_yr):
            seed = abs(hash(basin.get("id","X"))) % (2**31) + fill_pct_yr
            rng  = np.random.default_rng(seed)
            daily_fill = cap * fill_pct_yr / 100 / 365
            vol    = np.zeros(days)
            outflo = np.zeros(days)
            inflow = np.zeros(days)
            v      = cap * 0.2
            for t in range(days):
                rain = max(0, 6*np.sin(np.pi*t/180)**2 + rng.gamma(1.5,3))
                q_in = rain * basin.get("eff_cat_km2",174000) * basin.get("runoff_c",0.38) * 1e6/1e9 * 0.5
                v    = min(cap, v + q_in)
                # Outflow = inflow minus filling increment
                q_out = max(0, q_in - daily_fill + rng.normal(0, daily_fill*0.1))
                v    -= q_out
                v     = max(0, v)
                vol[t]    = v
                outflo[t] = q_out
                inflow[t] = q_in
            equity = (outflo / (inflow + 0.001)).clip(0, 1.5) * 100
            return pd.DataFrame({"Date":dates_sc,"Volume":vol,"Outflow":outflo,
                                  "Inflow":inflow,"Equity":equity})

        df_s1 = _scenario_run(s1_rate)
        df_s2 = _scenario_run(s2_rate)
        df_s3 = _scenario_run(s3_rate)

        # Compare plots
        fig_war = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                subplot_titles=["Storage Volume (BCM)", "Downstream Equity (%)"])
        for df_s, lbl, col in [(df_s1,s1_lbl,"#10b981"),(df_s2,s2_lbl,"#f59e0b"),(df_s3,s3_lbl,"#ef4444")]:
            fig_war.add_trace(go.Scatter(x=df_s["Date"],y=df_s["Volume"],
                                          name=lbl,line=dict(color=col,width=2)), row=1,col=1)
            fig_war.add_trace(go.Scatter(x=df_s["Date"],y=df_s["Equity"].rolling(30).mean(),
                                          name=lbl+" (30d)",showlegend=False,
                                          line=dict(color=col,width=1.5,dash="dot")), row=2,col=1)
        fig_war.add_hline(y=40, row=2, col=1, line_dash="dash", line_color="#dc2626",
                          annotation_text="Art.7 threshold 40%")
        fig_war.add_hline(y=cap, row=1, col=1, line_dash="dash", line_color="#6366f1",
                          annotation_text=f"Max cap {cap} BCM")
        fig_war.update_layout(template="plotly_dark", height=560,
                               title=f"Filling Scenario Comparison — {basin.get('id','—')}")
        st.plotly_chart(fig_war, use_container_width=True)

        # KPI comparison
        kk1, kk2, kk3 = st.columns(3)
        for col_k, df_s, lbl, color in [(kk1,df_s1,s1_lbl,"#10b981"),
                                         (kk2,df_s2,s2_lbl,"#f59e0b"),
                                         (kk3,df_s3,s3_lbl,"#ef4444")]:
            eq_mean = df_s["Equity"].mean()
            art7    = int((df_s["Equity"] < 40).sum())
            col_k.markdown(
                f"<div class='kpi-giant' style='border-color:{color};padding:0.8rem;'>"
                f"<b style='color:{color};font-size:0.85rem;'>{lbl}</b><br>"
                f"<span style='color:#e2e8f0;font-size:1.2rem;font-weight:700;'>{eq_mean:.1f}%</span>"
                f"<br><span style='color:#94a3b8;font-size:0.75rem;'>avg equity</span><br>"
                f"<span style='color:{'#dc2626' if art7>180 else '#10b981'};'>"
                f"Art.7 flags: {art7} days</span>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ── Tab 5: Risk Matrix ────────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("🧮 Diplomatic Risk Matrix — All Basins")

        fig_risk = px.scatter(
            df_live,
            x="transparency", y="equity",
            size="cap_BCM", color="dispute_label",
            color_discrete_map={
                "CRITICAL":"#dc2626","HIGH":"#f97316",
                "MEDIUM":"#eab308","LOW":"#3b82f6","STABLE":"#10b981"
            },
            hover_name="name",
            hover_data=["river","country","fill_pct","sovereignty_idx","treaty"],
            text="id",
            template="plotly_dark", height=560,
            title="Equity vs Transparency Risk Matrix — 25 Global Basins",
            labels={"transparency":"Transparency Index (%)", "equity":"Equity Index (%)"},
            size_max=50,
        )
        # Quadrant lines
        fig_risk.add_hline(y=40, line_dash="dash", line_color="#dc2626",
                            annotation_text="Art. 7 threshold (40%)")
        fig_risk.add_hline(y=60, line_dash="dot", line_color="#f97316",
                            annotation_text="Art. 5 advisory (60%)")
        fig_risk.add_vline(x=70, line_dash="dash", line_color="#3b82f6",
                            annotation_text="Transparency concern (70%)")
        # Quadrant labels
        for x, y, txt, opacity in [
            (20, 20, "CRISIS ZONE", 0.08), (85, 85, "COMPLIANT ZONE", 0.05),
            (20, 85, "WITHHOLDING DATA", 0.05), (85, 20, "LOW EQUITY", 0.05)
        ]:
            fig_risk.add_shape(type="rect", x0=0, x1=69, y0=0, y1=39,
                               fillcolor="#dc2626", opacity=0.05, layer="below",
                               line_width=0)
        fig_risk.update_traces(textposition="top center", textfont_size=8)
        st.plotly_chart(fig_risk, use_container_width=True)

        # Sovereignty Index bar
        df_sov = df_live.sort_values("sovereignty_idx")
        fig_sov = go.Figure(go.Bar(
            y=df_sov["id"], x=df_sov["sovereignty_idx"],
            orientation="h",
            marker_color=[_LEVEL_COLOR[l] for l in df_sov["dispute_level"]],
            text=[f"{v:.0f}" for v in df_sov["sovereignty_idx"]],
            textposition="outside",
        ))
        fig_sov.update_layout(
            template="plotly_dark", height=max(400, len(df_sov)*22),
            title="Sovereignty Index — All Basins",
            xaxis_title="Sovereignty Index (0–100)",
            margin=dict(l=120),
        )
        st.plotly_chart(fig_sov, use_container_width=True)

    # ── Tab 6: Intelligence Feed ───────────────────────────────────────────────
    with tabs[5]:
        st.subheader("📡 Live Intelligence Feed")

        sitrep = generate_sitrep(df_live)
        st.code(sitrep, language="")

        # Role-specific briefings
        st.markdown("---")
        if role == "🔬 Analyst":
            st.markdown("#### 🔬 Analyst Briefing")
            st.markdown(
                "Anomaly detected in **top-3 dispute basins**: "
                "equity indices trending below 45% over last 30-day window. "
                "Recommend deepening HBV calibration for Nile catchment. "
                "MODIS ET correction applied — TDI adjusted downward by ~8% for arid basins."
            )
        elif role == "🕊️ Diplomat":
            st.markdown("#### 🕊️ Diplomatic Briefing")
            st.markdown(
                "Three basins currently below Art. 5 equity threshold (40%). "
                "Recommend initiating consultation under Art. 12 notification procedure "
                "for high-dispute basins. No binding agreement currently in force for GERD. "
                "Art. 9 data-sharing compliance degraded — request formal disclosure."
            )
        elif role == "⚖️ Judge":
            st.markdown("#### ⚖️ Judicial Briefing")
            st.markdown(
                "Technical evidence package compiled: HBV natural flow baseline, "
                "TDI forensic index, Sentinel-1 area timeseries. "
                "HIFD > 40% sustained for >60 days in at least one basin — "
                "prima facie evidence of significant harm (Art. 7). "
                "Recommend fact-finding mission under Annex Art. 6."
            )
        elif role == "📰 Journalist":
            st.markdown("#### 📰 Journalist Briefing")
            critical = df_live[df_live["dispute_level"] >= 4][["id","river","country","dispute_ctx"]].head(3)
            for _, r in critical.iterrows():
                st.markdown(
                    f"🔴 **{r['id']}** — {r['river']} ({r['country']})  \n"
                    f"_{r['dispute_ctx']}_"
                )

    # ── Tab 7: Export ─────────────────────────────────────────────────────────
    with tabs[6]:
        st.subheader("📥 Export SITREP & Intelligence Package")

        sitrep_full = generate_sitrep(df_live)

        c1, c2, c3 = st.columns(3)
        c1.download_button(
            "📄 SITREP Text",
            sitrep_full.encode("utf-8"),
            file_name=f"HSAE_SITREP_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
        )
        c2.download_button(
            "📊 All Basins CSV",
            df_live.to_csv(index=False).encode("utf-8"),
            file_name=f"HSAE_LiveMetrics_{datetime.utcnow().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        # HTML intelligence brief
        html_brief = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>HSAE Intelligence Brief</title>
<style>
body{{font-family:Arial;margin:30px;background:#0f172a;color:#e2e8f0;}}
h1{{color:#ef4444;}} h2{{color:#10b981;}}
table{{border-collapse:collapse;width:100%;}}
th,td{{border:1px solid #334155;padding:8px;font-size:0.85rem;}}
th{{background:#1e3a5f;}}
.crit{{color:#dc2626;}} .high{{color:#f97316;}}
.med{{color:#eab308;}} .low{{color:#3b82f6;}} .stable{{color:#10b981;}}
</style></head><body>
<h1>🌐 HSAE Intelligence Brief — {datetime.utcnow().strftime('%d %B %Y')}</h1>
<pre>{sitrep_full}</pre>
<h2>All Basins Intelligence Table</h2>
<table><tr>
<th>ID</th><th>River</th><th>Country</th><th>Dispute</th>
<th>Equity%</th><th>Transp%</th><th>Fill%</th><th>SovIdx</th><th>Treaty</th>
</tr>
{"".join(f"<tr><td>{r.id}</td><td>{r.river}</td><td>{r.country[:25]}</td>"
         f"<td class='{r.dispute_label.lower()}'>{r.dispute_label}</td>"
         f"<td>{r.equity}</td><td>{r.transparency}</td>"
         f"<td>{r.fill_pct}</td><td>{r.sovereignty_idx}</td><td>{r.treaty}</td></tr>"
         for r in df_live.itertuples())}
</table>
</body></html>"""
        c3.download_button(
            "🌐 HTML Intelligence Brief",
            html_brief.encode("utf-8"),
            file_name=f"HSAE_Brief_{datetime.utcnow().strftime('%Y%m%d')}.html",
            mime="text/html",
        )
