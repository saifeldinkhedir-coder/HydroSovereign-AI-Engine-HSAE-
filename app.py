"""
app.py  ─  HSAE v6.0.0  Application Router
===========================================
Author : Seifeldin M.G. Alkhedir — University of Khartoum
Version: 6.0.0  |  March 2026

New in v6.0.0:
  + Real data: Open-Meteo ERA5 + GloFAS + USGS + GRACE-FO (26 basins)
  + Advanced AI: Ensemble (RF+MLP+GBM) + Anomaly Detection + Forecast
  + Climate: SSP1-2.6 / SSP2-4.5 / SSP3-7.0 / SSP5-8.5 projections
  + Database: SQLite persistence (run history, cache, audit)
  + Export: HTML + Excel + JSON Dossier + GeoJSON
"""
import streamlit as st
import json
import numpy as np
import pandas as pd

from gee_engine       import GEEEngine, render_gee_engine_panel
from basins_global   import GLOBAL_BASINS, search_basins, CONTINENTS, ALL_NAMES
from hsae_intro      import intro_page
from hsae_v430       import page_v430
from hsae_v990       import page_v990
from hsae_science    import render_science_page
from hsae_legal      import render_legal_page
from hsae_devops     import render_devops_page
from hsae_validation import render_validation_page
from hsae_alerts     import render_alerts_page
from hsae_hbv        import render_hbv_page
from hsae_opsroom    import render_opsroom_page
from hsae_groundwater import render_groundwater_page
from hsae_quality    import render_quality_page
from hsae_audit      import render_audit_page

# New v6.0.0 modules
from hsae_ai         import render_ai_page
from hsae_climate    import render_climate_page
from hsae_db         import render_db_page, init_db, save_run, log_action
from hsae_export     import render_export_page
from hsae_gee_data   import render_real_data_panel, fetch_open_meteo, fetch_glofas, fetch_usgs

# ── Init DB ───────────────────────────────────────────────────────────────────
init_db()

# ── Auto-simulation ───────────────────────────────────────────────────────────
def _get_or_simulate_df(basin_cfg: dict | None = None) -> "pd.DataFrame | None":
    df = st.session_state.get("df")
    if df is not None:
        return df
    try:
        cfg      = basin_cfg or st.session_state.get("active_basin_cfg", {})
        n        = 365
        cap      = float(cfg.get("cap", 40.0))
        area_max = float(cfg.get("area_max", 1000))
        head     = float(cfg.get("head", 100.0))
        a        = float(cfg.get("bathy_a", 0.038))
        b_exp    = float(cfg.get("bathy_b", 1.12))
        eff_cat  = float(cfg.get("eff_cat_km2", 35000.0))
        runoff_c = float(cfg.get("runoff_c", 0.35))
        evap_r   = float(cfg.get("evap_base", 5.0))

        rng    = np.random.default_rng(abs(hash(cfg.get("id","seed"))) % (2**31))
        dates  = pd.date_range("2022-01-01", periods=n, freq="D")
        doy    = np.array([d.dayofyear for d in dates])
        rain   = rng.gamma(2.0, 12.0, n) * (1 + 0.5*np.sin(2*np.pi*doy/365))
        rain_n = rain / (rain.max() + 1e-6)
        area   = np.clip(np.cumsum(rng.normal(0,5,n)) + area_max*0.6, area_max*0.1, area_max)
        volume = (a * (area**b_exp)).clip(0, cap)
        inflow = (rain * eff_cat * runoff_c) / 1e6
        delta_v = np.diff(volume, prepend=volume[0])
        losses  = area * evap_r / 1000 + volume * 0.005
        outflow = np.clip(inflow - delta_v - losses, 0, None)
        flow_m3s = outflow * 1e9 / 86400
        out_n    = outflow / (outflow.max() + 1e-6)
        evap_pm  = (area * evap_r / 1000).clip(0)
        seepage  = (volume * 0.0045).clip(0)
        dv_full  = inflow - outflow - evap_pm - seepage
        dv_obs   = np.diff(volume, prepend=volume[0])
        ndwi     = (volume/cap).clip(0,1)*0.7+0.1
        Rn       = 15+8*np.cos(2*np.pi*doy/365)
        T        = 25+8*np.sin(2*np.pi*doy/365)+rng.normal(0,2,n)
        et0      = np.clip(0.0023*(T+17.8)*np.sqrt(8)*Rn*0.5, 0, 12)

        df_sim = pd.DataFrame({
            "Date":          dates,
            "S1_VV_dB":      rng.normal(-18,2.2,n),
            "S1_Area":       area,
            "S2_NDWI":       ndwi,
            "S2_Area":       area*1.05,
            "Fused_Area":    area,
            "Effective_Area":area,
            "Optical_Valid": (ndwi>=0.25).astype(int),
            "GPM_Rain_mm":   rain,
            "Inflow_BCM_raw":inflow,
            "Inflow_BCM":    inflow,
            "Lag_Effect":    np.ones(n),
            "Volume_BCM":    volume,
            "Pct_Full":      (volume/cap*100).clip(0,100),
            "Delta_V":       delta_v,
            "Losses":        losses,
            "Outflow_BCM":   outflow,
            "Flow_m3s":      flow_m3s,
            "Power_MW":      np.clip(0.91*1000*9.81*flow_m3s*head/1e6,0,None),
            "Energy_GWh":    np.clip(0.91*1000*9.81*flow_m3s*head/1e6,0,None)*24/1000,
            "Evap_PM_BCM":   evap_pm,
            "Seepage_BCM":   seepage,
            "ET0_mm_day":    et0,
            "dV_full":       dv_full,
            "dV_obs_full":   dv_obs,
            "MB_full_Error": dv_obs - dv_full,
            "MB_full_pct":   np.abs(dv_obs-dv_full)/(cap+1e-9)*100,
            "Evap_BCM":      evap_pm,
            "TD_Deficit":    np.clip(rain_n-out_n,0,1),
            "NDVI":          ((ndwi-0.2)/(ndwi+0.2)).clip(-0.2,0.9),
        })
        st.session_state["df"]       = df_sim
        st.session_state["executed"] = True
        return df_sim
    except Exception:
        return None

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HydroSovereign AI Engine (HSAE) v6.0.0",
    layout="wide", page_icon="🌐",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
[data-testid="stSidebar"] {background:#020617;}
.stButton>button {border-radius:8px;}
</style>""", unsafe_allow_html=True)

# ── Session defaults ──────────────────────────────────────────────────────────
_DEFAULTS = {
    "active_page":       "🏠 Intro",
    "active_basin_name": ALL_NAMES[0],
    "active_basin_cfg":  GLOBAL_BASINS[ALL_NAMES[0]],
    "custom_geom":       None,
    "data_mode":         "Simulation",
    "time_start":        "2020-01-01",
    "time_end":          "2024-12-31",
    "df":                None,
    "executed":          False,
    "real_df":           None,
    "ai_ens":            None,
    "ai_anom":           None,
    "ai_fore":           None,
    "cli_results":       None,
    "last_metrics":      {},
}
for k,v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌐 HSAE **v6.0.0**")
    st.markdown("""
<span style='background:#10b981;color:#000;border-radius:4px;padding:2px 8px;font-size:0.7rem;font-weight:700;'>
  ✨ REAL DATA + AI + CLIMATE
</span>""", unsafe_allow_html=True)

    st.markdown("### 📑 Navigation")

    PAGES = [
        "🏠 Intro",
        "🌐 v430 · Hybrid DSS",
        "⚖️  v990 · Legal Nexus",
        "🔬 Science · Water Balance",
        "📜 Legal · Treaty Engine",
        "🛠️  DevOps · CI/CD",
        "📊 Validation · GRDC",
        "🚨 Alerts · Telegram",
        "🌊 HBV · Catchment Model",
        "🏛️  Operations Room",
        "💧 Groundwater & Irrigation",
        "🧪 Water Quality",
        "🗂️  Audit Trail",
        "─── v6.0 NEW ───",
        "📡 Real Data · APIs",
        "🤖 AI · ML Engine",
        "🌍 Climate · SSP Scenarios",
        "🗄️  Database · History",
        "📄 Export · Reports",
    ]
    cur = st.session_state["active_page"]
    if cur not in PAGES: cur = PAGES[0]

    page = st.radio("Module:", PAGES,
        index=PAGES.index(cur), key="nav_radio",
        label_visibility="collapsed")
    st.session_state["active_page"] = page

    st.markdown("---")
    st.markdown("### 🔍 Basin Search")
    sq = st.text_input("River / Dam / Country", placeholder="Nile · Mekong · الفرات", key="sb_search")
    sc = st.selectbox("Continent", ["🌐 All"]+CONTINENTS, key="sb_cont")
    if sq.strip():
        pool = search_basins(sq)
    elif sc != "🌐 All":
        from basins_global import list_by_continent
        pool = list_by_continent(sc.split(" ",1)[-1])
    else:
        pool = GLOBAL_BASINS
    pool = pool or GLOBAL_BASINS
    pool_names = list(pool.keys())
    cur_b = st.session_state["active_basin_name"]
    if cur_b not in pool_names: cur_b = pool_names[0]
    basin_name = st.selectbox(f"Active Basin ({len(pool_names)} found)", pool_names,
        index=pool_names.index(cur_b), key="sb_basin")
    st.session_state["active_basin_name"] = basin_name
    st.session_state["active_basin_cfg"]  = GLOBAL_BASINS[basin_name]
    basin = GLOBAL_BASINS[basin_name]

    st.markdown(f"""
<div style='background:#0f172a;border:1px solid #10b981;border-radius:10px;
            padding:0.8rem;font-size:0.82rem;margin-top:0.5rem;'>
  <b style='color:#10b981;'>{basin_name}</b><br>
  <span style='color:#94a3b8;'>
    🌊 {basin['river']}  ·  🏗️ {basin['dam']}<br>
    🌍 {basin['continent']}<br>
    💧 {basin['cap']} BCM  ·  ⚡ {basin['head']} m<br>
    📜 {basin.get('treaty','—')}
  </span>
</div>""", unsafe_allow_html=True)

    st.markdown("---")
    import datetime as _dt
    st.markdown("### 📅 Date Range")
    _c1, _c2 = st.columns(2)
    with _c1:
        _s = st.date_input("From", value=_dt.date(2020,1,1), key="sb_start")
    with _c2:
        _e = st.date_input("To", value=_dt.date.today(), key="sb_end")
    if _s > _e:
        st.warning("⚠️ Start must be before End")
    st.session_state["date_start"] = str(_s)
    st.session_state["date_end"]   = str(_e)

    st.markdown("---")
    data_mode = st.radio("📡 Data Mode",
        ["Simulation","Indirect CSV","Direct GEE","🆕 Real APIs (v6)"],
        index=0, key="sb_mode")
    st.session_state["data_mode"] = data_mode

    # If real data available, show badge
    if st.session_state.get("real_df") is not None:
        n_rd = len(st.session_state["real_df"])
        st.markdown(f"<span style='color:#22c55e;font-size:0.78rem;'>✅ Real data loaded: {n_rd:,} rows</span>",
                    unsafe_allow_html=True)

    st.markdown("---")
    st.caption("HSAE v6.0.0 · Dr. Seifeldin M.G. Alkhedir · University of Khartoum")

# ── Use real data if available and mode selected ──────────────────────────────
def _get_df(basin_cfg: dict) -> pd.DataFrame | None:
    if st.session_state.get("data_mode") == "🆕 Real APIs (v6)" and st.session_state.get("real_df") is not None:
        return st.session_state["real_df"]
    return _get_or_simulate_df(basin_cfg)

# ── Router ────────────────────────────────────────────────────────────────────
if page == "🏠 Intro":
    intro_page()

elif page == "🌐 v430 · Hybrid DSS":
    page_v430()

elif page == "⚖️  v990 · Legal Nexus":
    page_v990()

elif page == "🔬 Science · Water Balance":
    df = _get_df(basin)
    if df is not None: render_science_page(df, basin)
    else: st.warning("Run v430 first.")

elif page == "📜 Legal · Treaty Engine":
    render_legal_page(basin)

elif page == "🛠️  DevOps · CI/CD":
    render_devops_page()

elif page == "📊 Validation · GRDC":
    render_validation_page(_get_df(basin), basin)

elif page == "🚨 Alerts · Telegram":
    render_alerts_page(_get_df(basin), basin)

elif page == "🌊 HBV · Catchment Model":
    render_hbv_page(_get_df(basin), basin)

elif page == "🏛️  Operations Room":
    render_opsroom_page(_get_df(basin), basin)

elif page == "💧 Groundwater & Irrigation":
    render_groundwater_page(_get_df(basin), basin)

elif page == "🧪 Water Quality":
    render_quality_page(_get_df(basin), basin)

elif page == "🗂️  Audit Trail":
    render_audit_page()

elif page == "─── v6.0 NEW ───":
    st.info("Select a v6.0 module from the list below.")

elif page == "📡 Real Data · APIs":
    st.markdown("# 📡 Real Data — v6.0 APIs")
    df_real = render_real_data_panel(basin_name, basin)
    if df_real is not None:
        st.session_state["df"] = df_real   # feed to all modules
        log_action("REAL_DATA_LOADED", basin_name, f"{len(df_real)} rows")
        save_run(basin_name, "Real Data", "APIs", len(df_real), {})

elif page == "🤖 AI · ML Engine":
    df = _get_df(basin)
    render_ai_page(df, basin)
    if st.session_state.get("ai_anom") is not None:
        from hsae_db import save_anomalies
        n = save_anomalies(basin_name, st.session_state["ai_anom"])
        if n > 0:
            log_action("ANOMALIES_DETECTED", basin_name, f"{n} events", "AI")

elif page == "🌍 Climate · SSP Scenarios":
    df = _get_df(basin)
    render_climate_page(df, basin)

elif page == "🗄️  Database · History":
    render_db_page()

elif page == "📄 Export · Reports":
    df = _get_df(basin)
    render_export_page(df, basin)
