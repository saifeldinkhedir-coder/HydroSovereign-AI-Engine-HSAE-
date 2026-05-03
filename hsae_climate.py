"""
hsae_climate.py  ─  HSAE v6.0.0  Climate Change Scenarios
==========================================================
Author : Seifeldin M.G. Alkhedir
Version: 1.0.0  |  March 2026

Climate projections based on CMIP6 / IPCC AR6 deltas:
  - SSP1-2.6  (optimistic — +1.5°C by 2100)
  - SSP2-4.5  (intermediate — +2.7°C by 2100)
  - SSP3-7.0  (pessimistic — +3.6°C by 2100)
  - SSP5-8.5  (worst case — +4.4°C by 2100)

For each scenario:
  - Projected temperature anomaly (IPCC AR6 Table SPM.1)
  - Precipitation change % (CMIP6 ensemble median)
  - ET₀ change (Penman-Monteith response to warming)
  - Reservoir storage impact
  - Legal vulnerability index

Data from IPCC AR6 WGI Table SPM.1 + regional projections
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# ── IPCC AR6 Climate delta table per region ───────────────────────────────────
# Source: IPCC AR6 WGI SPM Table 1 + regional fact sheets
# Format: {scenario: {year: (dT_C, dP_pct, dET_pct)}}
# dT = temperature change vs 1995-2014 baseline
# dP = precipitation change %  (negative = drier)
# dET = evapotranspiration change %

CLIMATE_SCENARIOS: dict[str, dict] = {
    "SSP1-2.6": {
        "label":    "SSP1-2.6 (Optimistic — Net Zero ~2050)",
        "color":    "#22c55e",
        "co2_ppm":  443,
        "desc":     "Sustainable development path. Emissions cut sharply after 2030.",
        "global_dT_2050": 1.2, "global_dT_2100": 1.5,
        "regions": {
            "Africa":        {"dP_2050":-8,  "dP_2100":-12, "dT_2050":1.4,"dT_2100":1.8},
            "Middle East":   {"dP_2050":-10, "dP_2100":-15, "dT_2050":1.5,"dT_2100":1.9},
            "Asia":          {"dP_2050":+3,  "dP_2100":+5,  "dT_2050":1.3,"dT_2100":1.6},
            "South America": {"dP_2050":-5,  "dP_2100":-8,  "dT_2050":1.2,"dT_2100":1.5},
            "North America": {"dP_2050":+2,  "dP_2100":+3,  "dT_2050":1.1,"dT_2100":1.4},
            "Europe":        {"dP_2050":+3,  "dP_2100":+4,  "dT_2050":1.2,"dT_2100":1.5},
            "Oceania":       {"dP_2050":-7,  "dP_2100":-10, "dT_2050":1.3,"dT_2100":1.6},
            "Central Asia":  {"dP_2050":-5,  "dP_2100":-8,  "dT_2050":1.5,"dT_2100":1.9},
        }
    },
    "SSP2-4.5": {
        "label":    "SSP2-4.5 (Intermediate — Current Pledges)",
        "color":    "#f59e0b",
        "co2_ppm":  538,
        "desc":     "Middle-of-the-road scenario. Modest mitigation after 2050.",
        "global_dT_2050": 1.7, "global_dT_2100": 2.7,
        "regions": {
            "Africa":        {"dP_2050":-12, "dP_2100":-20, "dT_2050":2.0,"dT_2100":3.2},
            "Middle East":   {"dP_2050":-14, "dP_2100":-22, "dT_2050":2.2,"dT_2100":3.5},
            "Asia":          {"dP_2050":+4,  "dP_2100":+8,  "dT_2050":1.8,"dT_2100":2.8},
            "South America": {"dP_2050":-8,  "dP_2100":-15, "dT_2050":1.7,"dT_2100":2.6},
            "North America": {"dP_2050":+3,  "dP_2100":+5,  "dT_2050":1.6,"dT_2100":2.4},
            "Europe":        {"dP_2050":+4,  "dP_2100":+6,  "dT_2050":1.7,"dT_2100":2.5},
            "Oceania":       {"dP_2050":-10, "dP_2100":-18, "dT_2050":1.8,"dT_2100":2.7},
            "Central Asia":  {"dP_2050":-8,  "dP_2100":-15, "dT_2050":2.1,"dT_2100":3.3},
        }
    },
    "SSP3-7.0": {
        "label":    "SSP3-7.0 (Pessimistic — Fragmented World)",
        "color":    "#f97316",
        "co2_ppm":  670,
        "desc":     "Regional rivalry, high emissions, limited cooperation.",
        "global_dT_2050": 2.1, "global_dT_2100": 3.6,
        "regions": {
            "Africa":        {"dP_2050":-16, "dP_2100":-28, "dT_2050":2.6,"dT_2100":4.3},
            "Middle East":   {"dP_2050":-18, "dP_2100":-30, "dT_2050":2.8,"dT_2100":4.7},
            "Asia":          {"dP_2050":+5,  "dP_2100":+12, "dT_2050":2.3,"dT_2100":3.8},
            "South America": {"dP_2050":-12, "dP_2100":-22, "dT_2050":2.2,"dT_2100":3.5},
            "North America": {"dP_2050":+4,  "dP_2100":+7,  "dT_2050":2.0,"dT_2100":3.2},
            "Europe":        {"dP_2050":+5,  "dP_2100":+8,  "dT_2050":2.1,"dT_2100":3.3},
            "Oceania":       {"dP_2050":-14, "dP_2100":-25, "dT_2050":2.3,"dT_2100":3.7},
            "Central Asia":  {"dP_2050":-12, "dP_2100":-22, "dT_2050":2.7,"dT_2100":4.5},
        }
    },
    "SSP5-8.5": {
        "label":    "SSP5-8.5 (Worst Case — Fossil-Fueled)",
        "color":    "#ef4444",
        "co2_ppm":  1135,
        "desc":     "Rapid economic growth, fossil fuel dependency, no mitigation.",
        "global_dT_2050": 2.4, "global_dT_2100": 4.4,
        "regions": {
            "Africa":        {"dP_2050":-20, "dP_2100":-35, "dT_2050":3.0,"dT_2100":5.5},
            "Middle East":   {"dP_2050":-22, "dP_2100":-38, "dT_2050":3.3,"dT_2100":5.9},
            "Asia":          {"dP_2050":+6,  "dP_2100":+15, "dT_2050":2.7,"dT_2100":4.8},
            "South America": {"dP_2050":-15, "dP_2100":-28, "dT_2050":2.6,"dT_2100":4.4},
            "North America": {"dP_2050":+5,  "dP_2100":+9,  "dT_2050":2.4,"dT_2100":4.0},
            "Europe":        {"dP_2050":+6,  "dP_2100":+10, "dT_2050":2.5,"dT_2100":4.1},
            "Oceania":       {"dP_2050":-18, "dP_2100":-32, "dT_2050":2.7,"dT_2100":4.7},
            "Central Asia":  {"dP_2050":-16, "dP_2100":-30, "dT_2050":3.2,"dT_2100":5.6},
        }
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# Project reservoir under climate scenario
# ══════════════════════════════════════════════════════════════════════════════
def project_reservoir(
    df_hist: pd.DataFrame,
    basin_cfg: dict,
    scenario_key: str,
    horizon_year: int = 2075,
) -> pd.DataFrame:
    """
    Project reservoir storage under a climate scenario from the last
    historical year to horizon_year.
    Returns DataFrame with Date, Volume_BCM, Inflow_BCM, Outflow_BCM, Evap_BCM.
    """
    sc      = CLIMATE_SCENARIOS[scenario_key]
    region  = basin_cfg.get("continent", "Africa")
    reg_d   = sc["regions"].get(region, sc["regions"]["Africa"])

    # Interpolate deltas linearly from today (2026) to 2100
    base_yr = 2026
    t2050   = (2050 - base_yr) / (2100 - base_yr)
    t100    = 1.0

    def _lerp(val_2050, val_2100, t):
        return val_2050 + (val_2100 - val_2050) * max(0, min(1, (t - t2050) / (t100 - t2050)))

    cap      = float(basin_cfg.get("cap", 40.0))
    eff_cat  = float(basin_cfg.get("eff_cat_km2", 35000.0))
    runoff_c = float(basin_cfg.get("runoff_c", 0.35))
    head     = float(basin_cfg.get("head", 100.0))
    evap_r   = float(basin_cfg.get("evap_base", 5.0))
    area_max = float(basin_cfg.get("area_max", 1000.0))

    # Historical annual means
    mean_rain    = float(df_hist["GPM_Rain_mm"].mean()) if "GPM_Rain_mm" in df_hist.columns else 10.0
    mean_inflow  = float(df_hist["Inflow_BCM"].mean())
    mean_outflow = float(df_hist["Outflow_BCM"].mean())

    # Projection: annual time steps
    years = np.arange(base_yr, horizon_year + 1)
    rows  = []

    vol = cap * 0.6  # start at current fill

    for yr in years:
        t = (yr - base_yr) / (2100 - base_yr)
        # Interpolated deltas
        dT = reg_d["dT_2050"] + (reg_d["dT_2100"] - reg_d["dT_2050"]) * t / (t100 if t > t2050 else t2050)
        dP = (reg_d["dP_2050"] + (reg_d["dP_2100"] - reg_d["dP_2050"]) * t / (t100 if t > t2050 else t2050)) / 100

        rain_yr     = mean_rain * (1 + dP)
        inflow_yr   = mean_inflow * (1 + dP) * max(0.5, 1 - 0.01*dT)
        # ET increases ~3% per °C (Penman-Monteith response)
        evap_mult   = 1 + 0.03 * dT
        evap_yr     = evap_r * evap_mult
        evap_bcm    = area_max * 0.6 * evap_yr / 1000 * 365   # annual BCM
        losses_yr   = evap_bcm + vol * 0.005 * 365

        # Demand increases 1.5% per year (population + irrigation)
        demand_mult = (1.015 ** (yr - base_yr))
        outflow_yr  = mean_outflow * demand_mult

        delta_v = inflow_yr*365 - outflow_yr*365 - losses_yr
        vol     = np.clip(vol + delta_v * 0.1, cap * 0.05, cap)  # dampen

        rows.append({
            "Year":          yr,
            "Volume_BCM":    vol,
            "Pct_Full":      vol/cap*100,
            "Inflow_BCM_yr": inflow_yr*365,
            "Outflow_BCM_yr":outflow_yr*365,
            "Evap_BCM_yr":   evap_bcm,
            "Rain_mm_yr":    rain_yr*365,
            "dT_C":          dT,
            "dP_pct":        dP*100,
        })

    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════════════════════════
# Vulnerability Index
# ══════════════════════════════════════════════════════════════════════════════
def compute_vulnerability(df_proj: pd.DataFrame, cap: float) -> dict:
    """
    Climate Vulnerability Index (CVI) for a basin under a scenario.
    0-100: 0=resilient, 100=critically vulnerable
    """
    min_vol   = float(df_proj["Volume_BCM"].min())
    end_vol   = float(df_proj["Volume_BCM"].iloc[-1])
    start_vol = float(df_proj["Volume_BCM"].iloc[0])
    max_dT    = float(df_proj["dT_C"].max())
    min_pct   = float(df_proj["Pct_Full"].min())

    # Components
    storage_loss = max(0, (start_vol - end_vol) / (start_vol + 1e-6)) * 100
    temp_stress  = min(max_dT / 5.0, 1.0) * 100   # normalize to 5°C max
    depletion    = max(0, 100 - min_pct)

    cvi = (storage_loss * 0.4 + temp_stress * 0.3 + depletion * 0.3)
    cvi = min(cvi, 100)

    if cvi < 25:  level = "🟢 Low"
    elif cvi < 50: level = "🟡 Moderate"
    elif cvi < 75: level = "🟠 High"
    else:          level = "🔴 Critical"

    return {
        "cvi": round(cvi, 1),
        "level": level,
        "storage_loss_pct": round(storage_loss, 1),
        "max_dT": round(max_dT, 2),
        "min_fill_pct": round(min_pct, 1),
    }

# ══════════════════════════════════════════════════════════════════════════════
# Streamlit Page
# ══════════════════════════════════════════════════════════════════════════════
def render_climate_page(df: pd.DataFrame | None, basin: dict) -> None:
    st.markdown("""
<div style='background:linear-gradient(135deg,#020617,#0a1a0f);
            border:2px solid #22c55e;border-radius:16px;padding:1.2rem 1.8rem;margin-bottom:1.2rem;'>
  <span style='font-size:1.6rem;'>🌍</span>
  <b style='color:#22c55e;font-size:1.3rem;margin-left:0.6rem;'>Climate Change Scenarios</b><br>
  <span style='color:#94a3b8;font-size:0.83rem;'>
    IPCC AR6 · CMIP6 · SSP1-2.6 · SSP2-4.5 · SSP3-7.0 · SSP5-8.5 · 2026–2100
  </span>
</div>""", unsafe_allow_html=True)

    if df is None or len(df) < 30:
        st.warning("⚠️ Run v430 first to generate baseline data.")
        return

    basin_name = basin.get("name","—")
    continent  = basin.get("continent","Africa")
    cap        = float(basin.get("cap", 40.0))

    # ── Scenario selector ────────────────────────────────────────────────────
    sc_keys = list(CLIMATE_SCENARIOS.keys())
    cols_sc = st.columns(4)
    sel_scenarios: list[str] = []
    for i, k in enumerate(sc_keys):
        sc = CLIMATE_SCENARIOS[k]
        if cols_sc[i].checkbox(sc["label"].split("(")[0].strip(), value=True, key=f"sc_{k}"):
            sel_scenarios.append(k)

    horizon = st.slider("Projection Horizon", 2030, 2100, 2075, 5, key="cli_hor")

    if not sel_scenarios:
        st.info("Select at least one scenario above.")
        return

    run_btn = st.button("🌍 Run Climate Projections", type="primary", key="cli_run")
    if run_btn or st.session_state.get("cli_results"):
        if run_btn:
            results = {}
            with st.spinner("Computing projections…"):
                for k in sel_scenarios:
                    results[k] = project_reservoir(df, basin, k, horizon)
            st.session_state["cli_results"]  = results
            st.session_state["cli_sel_sc"]   = sel_scenarios
            st.session_state["cli_horizon"]  = horizon

        results = st.session_state.get("cli_results", {})
        sel_scenarios = st.session_state.get("cli_sel_sc", sel_scenarios)

        if not results: return

        tab_vol, tab_temp, tab_rain, tab_cvi, tab_legal = st.tabs(
            ["💧 Storage","🌡️ Temperature","🌧️ Precipitation","⚠️ Vulnerability","⚖️ Legal Impact"])

        # ── Storage ───────────────────────────────────────────────────────────
        with tab_vol:
            fig = go.Figure()
            # Historical
            if "Volume_BCM" in df.columns:
                fig.add_trace(go.Scatter(x=df["Date"],y=df["Volume_BCM"],mode="lines",
                    name="Historical",line=dict(color="#6b7280",width=1.5,dash="dot")))
            for k, df_p in results.items():
                sc = CLIMATE_SCENARIOS[k]
                fig.add_trace(go.Scatter(
                    x=pd.to_datetime(df_p["Year"].astype(str)+"-06-01"),
                    y=df_p["Volume_BCM"],mode="lines+markers",name=sc["label"].split("(")[0].strip(),
                    line=dict(color=sc["color"],width=2),marker=dict(size=4)))
            fig.add_hline(y=cap*0.3,line_dash="dash",line_color="#ef4444",annotation_text="30% — Critical threshold")
            fig.add_hline(y=cap*0.5,line_dash="dot", line_color="#f59e0b",annotation_text="50% — Warning")
            fig.update_layout(template="plotly_dark",height=460,
                title=f"Projected Storage — {basin_name} ({horizon})",yaxis_title="Volume (BCM)")
            st.plotly_chart(fig,use_container_width=True)

        # ── Temperature ───────────────────────────────────────────────────────
        with tab_temp:
            fig = go.Figure()
            for k, df_p in results.items():
                sc = CLIMATE_SCENARIOS[k]
                fig.add_trace(go.Scatter(x=df_p["Year"],y=df_p["dT_C"],mode="lines",
                    name=sc["label"].split("(")[0].strip(),
                    line=dict(color=sc["color"],width=2)))
            fig.update_layout(template="plotly_dark",height=380,
                title=f"Temperature Anomaly (ΔT vs 1995-2014 baseline) — {continent}",
                yaxis_title="ΔT (°C)",xaxis_title="Year")
            st.plotly_chart(fig,use_container_width=True)
            st.caption("Source: IPCC AR6 WGI Table SPM.1 — Regional projections")

        # ── Precipitation ─────────────────────────────────────────────────────
        with tab_rain:
            fig = go.Figure()
            for k, df_p in results.items():
                sc = CLIMATE_SCENARIOS[k]
                fig.add_trace(go.Scatter(x=df_p["Year"],y=df_p["dP_pct"],mode="lines",
                    name=sc["label"].split("(")[0].strip(),
                    line=dict(color=sc["color"],width=2)))
            fig.add_hline(y=0,line_dash="dash",line_color="#6b7280")
            fig.update_layout(template="plotly_dark",height=380,
                title=f"Precipitation Change % — {continent} (CMIP6 ensemble median)",
                yaxis_title="ΔP (%)",xaxis_title="Year")
            st.plotly_chart(fig,use_container_width=True)

        # ── Vulnerability ─────────────────────────────────────────────────────
        with tab_cvi:
            st.markdown("### ⚠️ Climate Vulnerability Index (CVI)")
            cvi_rows = []
            for k, df_p in results.items():
                v = compute_vulnerability(df_p, cap)
                cvi_rows.append({
                    "Scenario": CLIMATE_SCENARIOS[k]["label"].split("(")[0].strip(),
                    "CVI": v["cvi"], "Level": v["level"],
                    "Storage Loss %": v["storage_loss_pct"],
                    "Max ΔT (°C)": v["max_dT"],
                    "Min Fill %": v["min_fill_pct"],
                })
            cvi_df = pd.DataFrame(cvi_rows)
            st.dataframe(cvi_df, use_container_width=True, hide_index=True)

            fig = px.bar(cvi_df, x="Scenario", y="CVI", color="CVI",
                color_continuous_scale=["#22c55e","#f59e0b","#f97316","#ef4444"],
                range_color=[0,100], template="plotly_dark", height=380,
                title="Climate Vulnerability Index by Scenario")
            fig.update_layout(coloraxis_showscale=True, yaxis_range=[0,100])
            st.plotly_chart(fig, use_container_width=True)

        # ── Legal Impact ──────────────────────────────────────────────────────
        with tab_legal:
            st.markdown("### ⚖️ Legal Implications of Climate Change")
            worst_k   = max(results.keys(), key=lambda k: compute_vulnerability(results[k],cap)["cvi"])
            worst_cvi = compute_vulnerability(results[worst_k], cap)
            sc_label  = CLIMATE_SCENARIOS[worst_k]["label"]

            st.markdown(f"""
<div style='background:#0f172a;border:1px solid #ef4444;border-radius:12px;padding:1.2rem;'>
<b style='color:#ef4444;'>Worst Case: {sc_label}</b><br><br>
<b style='color:#f59e0b;'>CVI: {worst_cvi['cvi']}/100 — {worst_cvi['level']}</b><br><br>

<b style='color:#a78bfa;'>UN 1997 Article 7 — No Significant Harm:</b><br>
<span style='color:#94a3b8;'>
Climate change amplifies harm to downstream states. Under {sc_label}, storage loss of
<b>{worst_cvi['storage_loss_pct']}%</b> constitutes "significant harm" requiring notification
under Art. 12 and negotiation under Art. 17.</span><br><br>

<b style='color:#a78bfa;'>UN 1997 Article 5 — Equitable Utilization:</b><br>
<span style='color:#94a3b8;'>
Temperature rise of <b>+{worst_cvi['max_dT']}°C</b> increases upstream irrigation demand,
reducing downstream equitable share. Parties must renegotiate allocation under Art. 5(2).</span><br><br>

<b style='color:#a78bfa;'>UN 1997 Article 20 — Ecosystem Protection:</b><br>
<span style='color:#94a3b8;'>
Minimum environmental flow (E-flow) must be maintained even under climate stress.
Minimum fill of <b>{worst_cvi['min_fill_pct']}%</b> threatens E-flow commitments.</span>
</div>""", unsafe_allow_html=True)

            st.download_button("⬇️ Download Climate Report (CSV)",
                pd.concat([results[k].assign(scenario=k) for k in results]).to_csv(index=False).encode(),
                "HSAE_climate_projections.csv","text/csv")
