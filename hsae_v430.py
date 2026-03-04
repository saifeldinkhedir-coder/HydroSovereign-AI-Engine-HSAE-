"""
HydroSovereign AI Engine (HSAE) v5.0.0 — Module: hsae_v430
Hybrid Decision Support System · SAR+NDWI+GPM+AI

Original Scientific Contributions (Alkedir, 2026):
  - Alkedir SAR-NDWI Cloud-Adaptive Fusion (ASCAF):
      Fused_Area = S1·w + S2·(1-w); optical_ok = NDWI ≥ threshold  [Lines ~99-100]
  - Alkedir Forensic Scoring Function (AFSF):
      AFSF = TD_Deficit.rolling(4).mean().max() × 100  [Line ~153]
  - Alkedir Transparency Deficit Index (ATDI):
      Computed as TD_Deficit time-series; ATDI summary = mean × 100  [Lines ~150-155]

Standard methods used (not invented here):
  - Random Forest (Breiman, 2001) for 90-day storage forecast

Author : Seifeldin M.G. Alkedir — Independent Researcher
ORCID  : 0000-0003-0821-2991
Ref    : Alkedir, S.M.G. (2026a). Remote Sensing of Environment (under review).
"""
# hsae_v430.py  ─  HSAE v500  Hybrid DSS
# =============================================================================
# FIXES applied vs original v500:
#  1. All basin parameters sourced from GLOBAL_BASINS (no local duplicate dict)
#  2. np.random seeded per basin → different basins give different values
#  3. Inflow uses basin eff_cat_km2 + runoff_c (not hardcoded 35000×0.35)
#  4. Outflow / Power / Flow clipped to ≥ 0  (no negative power)
#  5. Closure error = real residual (not algebraically zero)
#  6. KPI metrics use mean/representative values (not .iloc[-1] edge artefact)
#  7. fillna(method='bfill') → .bfill()  (pandas ≥ 2.0 compatibility)
#  8. model df stored in st.session_state["df"] for Science page
#  9. Global basin search + continent filter in sidebar
# 10. Ground Truth tab accepts any station CSV (flexible column detection)
# =============================================================================

from hsae_tdi import compute_tdi, add_tdi_to_df, tdi_summary, TDI_EPSILON, TDI_ALPHA
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import date, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
import folium
from streamlit_folium import st_folium

from basins_global import (
    GLOBAL_BASINS, search_basins, CONTINENTS, ALL_NAMES,
    list_by_continent,
)

# ── Treaty labels ─────────────────────────────────────────────────────────────
_TREATY_DISPLAY = {
    "UN1997":                  "UN Watercourses Convention 1997",
    "TigrisEuphratesProtocol": "Tigris-Euphrates Protocol",
    "MRC1995":                 "Mekong River Commission 1995",
    "IndusWatersTreaty1960":   "Indus Waters Treaty 1960",
    "GangesTreaty1996":        "Ganges Treaty 1996",
    "DanubeConvention1994":    "Danube Protection Convention 1994",
    "RhineConvention1999":     "Rhine Convention 1999",
    "ColumbiaTreaty1964":      "Columbia River Treaty 1964",
    "ColoradoCompact1922":     "Colorado River Compact 1922",
    "ZAMCOM2004":              "ZAMCOM Agreement 2004",
    "ItaipuTreaty1973":        "Itaipu Treaty 1973",
    "AmazonCooperation":       "Amazon Cooperation Treaty (ACTO)",
    "AralSeaAgreement":        "Aral Sea Basin Agreement",
    "LCBC":                    "Lake Chad Basin Commission",
    "NigerBasinAuthority":     "Niger Basin Authority",
    "Domestic":                "Domestic Regulation",
    "Contested":               "Legally Contested",
    "NoTreaty":                "No Treaty",
}


# ── Physics engine ─────────────────────────────────────────────────────────────
def _run_engine(basin: dict, s1_weight: float, evaporation: float,
                seepage_rate: float, lag_days: int, cloud_threshold: float,
                n_days: int = 365) -> pd.DataFrame:
    """
    Pure-physics simulation for any basin.
    Uses basin's own area_max, cap, head, bathy_a/b, eff_cat_km2, runoff_c.
    Seeded by basin id hash → different basin = different random profile.
    """
    seed = abs(hash(basin.get("id", "X"))) % (2**31)
    rng  = np.random.default_rng(seed)

    area_max  = basin["area_max"]
    cap       = basin["cap"]
    head      = basin["head"]
    bathy_a   = basin["bathy_a"]
    bathy_b   = basin["bathy_b"]
    eff_cat   = basin["eff_cat_km2"]
    runoff_c  = basin["runoff_c"]
    evap_base = basin.get("evap_base", evaporation)

    dates = pd.date_range(date.today() - timedelta(days=n_days - 1),
                          periods=n_days, freq="D")
    df = pd.DataFrame({"Date": dates})

    # ── Sentinel-1 SAR ────────────────────────────────────────────────────
    # seasonal + basin-specific VV signal
    doy   = np.array([d.timetuple().tm_yday for d in dates])
    seas  = -18.0 + 2.5 * np.sin(2 * np.pi * doy / 365)          # seasonal cycle
    noise = rng.normal(0, 2.2, n_days)
    df["S1_VV_dB"] = np.clip(seas + noise, -32, -10)

    # Area from SAR backscatter → reservoir surface
    df["S1_Area"] = np.clip(
        area_max * (0.55 + (df["S1_VV_dB"] + 25) / 30),
        area_max * 0.20, area_max
    )

    # ── Sentinel-2 NDWI ───────────────────────────────────────────────────
    ndwi_base = 0.35 + 0.25 * np.sin(2 * np.pi * doy / 365 + 1.0)
    df["S2_NDWI"] = np.clip(ndwi_base + rng.normal(0, 0.12, n_days), 0.05, 0.92)
    df["S2_Area"] = df["S1_Area"] * (1 + df["S2_NDWI"] * 0.12)

    # ── Alkedir SAR-NDWI Cloud-Adaptive Fusion (ASCAF) ──────────────────
    # A_fused = S1·w + S2·(1−w);  optical_ok: NDWI ≥ cloud_threshold
    # Ref: Alkedir, S.M.G. (2026a). Remote Sensing of Environment (under review).
    df["Fused_Area"] = df["S1_Area"] * s1_weight + df["S2_Area"] * (1 - s1_weight)
    optical_ok = df["S2_NDWI"] >= cloud_threshold  # ASCAF quality gate
    df["Effective_Area"] = np.where(optical_ok, df["Fused_Area"], df["S1_Area"])
    cloudy_ratio = (~optical_ok).mean() * 100

    # ── GPM rainfall ──────────────────────────────────────────────────────
    # seasonal monsoon / arid profile per basin
    rain_seas = np.maximum(0,
        8.0 * np.sin(np.pi * doy / 180) ** 2    # wet season peak
        + rng.gamma(1.5, 4.0, n_days)            # stochastic daily
    )
    df["GPM_Rain_mm"] = rain_seas

    # ── Inflow — uses basin catchment & runoff coefficient ─────────────────
    # I = Rain(mm) × Catchment(km²) × runoff_c × 1e6(m²/km²) / 1e9(m³/BCM)
    df["Inflow_BCM_raw"] = (df["GPM_Rain_mm"] * eff_cat * runoff_c * 1e6 / 1e9)
    df["Inflow_BCM"]     = df["Inflow_BCM_raw"].shift(lag_days).bfill()
    df["Lag_Effect"]     = (
        df["Inflow_BCM"] / (df["Inflow_BCM_raw"] + 1e-9)
    ).clip(0.1, 10.0)

    # ── Volume / storage (bathymetry) ─────────────────────────────────────
    df["Volume_BCM"] = (
        bathy_a * (df["Effective_Area"] ** bathy_b)
    ).clip(0, cap)
    df["Pct_Full"]   = (df["Volume_BCM"] / cap * 100).clip(0, 100)
    df["Delta_V"]    = df["Volume_BCM"].diff().fillna(0)

    # ── Losses ────────────────────────────────────────────────────────────
    df["Losses"] = (
        df["Effective_Area"] * evaporation / 1000        # evaporation
        + df["Volume_BCM"]   * seepage_rate / 100        # seepage
    ).clip(lower=0)

    # ── Outflow (FIX: clip to 0 — negative outflow is physically impossible) ─
    df["Outflow_BCM"] = (df["Inflow_BCM"] - df["Delta_V"] - df["Losses"]).clip(lower=0)

    # ── Hydropower (FIX: uses clipped positive outflow) ───────────────────
    flow_m3s     = df["Outflow_BCM"] * 1e9 / 86400
    df["Power_MW"] = (0.91 * 1000 * 9.81 * flow_m3s * head / 1e6).clip(lower=0)

    # ── Closure error (FIX: real residual, not algebraically zero) ─────────
    total_in   = df["Inflow_BCM"].sum()
    total_out  = df["Outflow_BCM"].sum()
    total_dv   = df["Delta_V"].sum()
    total_loss = df["Losses"].sum()
    residual   = total_in - total_out - total_dv - total_loss
    closure    = abs(residual) / max(abs(total_in), 1e-9) * 100

    # ── Alkedir Transparency Deficit Index (ATDI) ────────────────────────
    # ATDI time-series: normalised rain-outflow gap per time step
    rain_norm       = df["GPM_Rain_mm"] / (df["GPM_Rain_mm"].max() + 1e-9)
    out_norm        = df["Outflow_BCM"] / (df["Outflow_BCM"].max() + 1e-9)
    # ── Canonical ATDI (hsae_tdi.py — single source of truth) ──────────────
    df = add_tdi_to_df(df, inflow_col="Inflow_BCM", outflow_col="Outflow_BCM")
    df["TD_Deficit"] = df["TDI_adj"]              # backward compat alias
    td_index         = float(df["TDI_adj"].mean() * 100)
    # ── Alkedir Forensic Scoring Function (AFSF) ──────────────────────────
    # AFSF = rolling_4_mean(ATDI).max() × 100 — trend-amplified legal signal
    # Ref: Alkedir, S.M.G. (2026a). Remote Sensing of Environment (under review).
    forensic_score  = float(df["TD_Deficit"].rolling(4).mean().max() * 100)

    # Store scalars
    st.session_state["closure_error"]  = closure
    st.session_state["td_index"]       = td_index
    st.session_state["forensic_score"] = forensic_score
    st.session_state["cloudy_ratio"]   = cloudy_ratio

    return df


# ── GPM predictive helper ──────────────────────────────────────────────────────
def _gpm_model(df: pd.DataFrame, lead_days: int = 5):
    if len(df) < 60:
        return None, None, None
    rain = df["GPM_Rain_mm"].values
    infl = df["Inflow_BCM"].values
    X, y = [], []
    for i in range(3, len(rain) - lead_days):
        X.append([rain[i], rain[i-1], rain[i-2], rain[i-3:i].mean()])
        y.append(infl[i + lead_days])
    X, y = np.array(X), np.array(y)
    rf = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
    rf.fit(X, y)
    yp = rf.predict(X)
    return rf, float(r2_score(y, yp)), float(np.sqrt(np.mean((y - yp)**2)))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def page_v430():

    # ── Session defaults ──────────────────────────────────────────────────
    for k, v in {
        "executed": False, "df": None, "basin_v430": None,
        "closure_error": 0.0, "td_index": 0.0,
        "forensic_score": 0.0, "cloudy_ratio": 0.0, "lag_days": 3,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── CSS ───────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
    .mono {background:linear-gradient(135deg,rgba(6,78,59,0.45),rgba(13,17,23,0.95));
           border:3px solid #10b981;border-radius:20px;padding:2rem;
           box-shadow:0 20px 60px rgba(16,185,129,0.25);}
    .basin-tag {display:inline-block;background:#064e3b;color:#6ee7b7;
                border:1px solid #10b981;border-radius:5px;
                padding:1px 8px;margin:2px;font-size:0.78rem;}
    </style>
    """, unsafe_allow_html=True)

    # ── Active basin from sidebar session state ────────────────────────────
    basin_name = st.session_state.get("active_basin_name", ALL_NAMES[0])
    basin      = GLOBAL_BASINS.get(basin_name, GLOBAL_BASINS[ALL_NAMES[0]])
    treaty_lbl = _TREATY_DISPLAY.get(basin.get("treaty",""), basin.get("treaty",""))

    # ── Header ────────────────────────────────────────────────────────────
    st.markdown(f"""
<div class='mono'>
  <h1 style='color:#10b981;font-family:Orbitron;text-align:center;
             font-size:2.4rem;margin:0;'>🌐 HSAE v430 · Global DSS</h1>
  <p style='text-align:center;color:#94a3b8;letter-spacing:3px;
            font-family:Orbitron;font-size:0.85rem;'>
    MULTI-SENSOR  ·  S1+S2+GPM  ·  AI FORECAST  ·  FORENSIC  ·  LEGAL
  </p>
  <hr style='border-color:#10b981;margin:0.8rem 0;'>
  <p style='text-align:center;color:#e2e8f0;font-size:1.05rem;margin:0;'>
    🎯 <b style='color:#10b981;'>{basin_name}</b>
    &nbsp;|&nbsp;🌊 {basin['river']}
    &nbsp;|&nbsp;🌍 {basin['continent']}
    &nbsp;|&nbsp;<span style='color:#fbbf24;'>📜 {treaty_lbl}</span>
  </p>
  <p style='text-align:center;color:#64748b;font-size:0.85rem;margin:0.3rem 0 0;'>
    {basin.get('context','')}
  </p>
</div>""", unsafe_allow_html=True)

    tag_html = " ".join(
        f"<span class='basin-tag'>{t}</span>" for t in basin.get("tags",[])[:10]
    )
    st.markdown(f"<div style='margin:0.4rem 0;'>{tag_html}</div>", unsafe_allow_html=True)

    # ── Controls (left) + Basin card (right) ──────────────────────────────
    col_c, col_i = st.columns([1, 2])

    with col_c:
        st.markdown("### ⚙️ Physics Parameters")
        s1_weight    = st.slider("🛰️ S1 SAR Weight",  0.3, 1.0, 0.75, 0.05, key="s1w")
        evaporation  = st.slider("☀️ Evaporation mm/d", 1.0, 15.0,
                                  float(basin.get("evap_base", 5.4)), 0.5, key="evap")
        seepage_rate = st.slider("💧 Seepage %/day",   0.01, 2.0, 0.45, 0.01, key="seep")
        lag_days     = st.slider("⏳ Runoff Lag (days)", 0, 15, 3, key="lag")
        cloud_thresh = st.slider("☁️ NDWI Cloud Threshold", 0.05, 0.50, 0.25, 0.05, key="cld")
        n_days       = st.slider("📅 Simulation period (days)", 180, 1825, 730, 30, key="nd")

        st.session_state["lag_days"] = lag_days

        c1b, c2b = st.columns(2)
        run_btn = c1b.button("🚀 RUN ENGINE", type="primary", use_container_width=True)
        if c2b.button("🔄 RESET", use_container_width=True):
            for k in ["executed","df","basin_v430","closure_error",
                      "td_index","forensic_score","cloudy_ratio"]:
                st.session_state[k] = None if k == "df" else (False if k=="executed" else 0.0)
            st.rerun()

    with col_i:
        st.markdown(f"""
<div class='mono'>
  <h4 style='color:#fbbf24;margin:0 0 0.6rem;'>📏 {basin_name}</h4>
  <table style='color:#e2e8f0;font-size:0.9rem;width:100%;'>
  <tr><td>🏗️ Dam</td><td><b>{basin['dam']}</b></td></tr>
  <tr><td>💧 Capacity</td><td><b style='color:#34d399;'>{basin['cap']} BCM</b></td></tr>
  <tr><td>⚡ Head</td><td>{basin['head']} m</td></tr>
  <tr><td>🗺️ Max Area</td><td>{basin['area_max']} km²</td></tr>
  <tr><td>🌧️ Catchment</td><td>{basin['eff_cat_km2']:,} km²</td></tr>
  <tr><td>🔄 Runoff C</td><td>{basin['runoff_c']}</td></tr>
  <tr><td>☀️ Evap Base</td><td>{basin.get('evap_base','—')} mm/d</td></tr>
  <tr><td>📜 Treaty</td><td style='color:#fbbf24;'>{treaty_lbl}</td></tr>
  <tr><td>⚖️ Articles</td><td>{basin.get('legal_arts','—')}</td></tr>
  <tr><td>🌍 Countries</td><td>{', '.join(basin.get('country',['—'])[:4])}</td></tr>
  </table>
</div>""", unsafe_allow_html=True)

    # ── World Map ─────────────────────────────────────────────────────────
    st.markdown("### 🌐 Global Basin Network")
    m = folium.Map(location=[basin["lat"], basin["lon"]],
                   zoom_start=4, tiles="CartoDB dark_matter")
    for nm, cfg in GLOBAL_BASINS.items():
        active = (nm == basin_name)
        folium.CircleMarker(
            [cfg["lat"], cfg["lon"]],
            radius=16 if active else 7,
            color="#10b981" if active else "#6b7280",
            fill=True, fill_opacity=0.85 if active else 0.5,
            weight=3 if active else 1,
            popup=folium.Popup(
                f"<b>{nm}</b><br>{cfg['river']} · {cfg['dam']}<br>"
                f"Cap: {cfg['cap']} BCM  Head: {cfg['head']} m<br>"
                f"{', '.join(cfg.get('country',[])[:3])}",
                max_width=260),
            tooltip=nm,
        ).add_to(m)
    c_map, c_spec = st.columns([2, 1])
    with c_map:
        st_folium(m, width=680, height=380, key="map_v430")
    with c_spec:
        st.latex(rf"V = {basin['bathy_a']:.3f} \times A^{{{basin['bathy_b']:.2f}}}")
        st.caption(
            f"A = surface area (km²)  |  V = storage (BCM)\n"
            f"Catchment: {basin['eff_cat_km2']:,} km²  |  "
            f"Runoff coeff: {basin['runoff_c']}"
        )

    # ══════════════════════════════════════════════════════════════════════
    # DATA MODE PANEL  — shown between controls and run button
    # Three fully-functional modes: Simulation · Indirect CSV · Direct GEE
    # ══════════════════════════════════════════════════════════════════════
    data_mode = st.session_state.get("data_mode", "Simulation")

    st.markdown("---")
    st.markdown("### 📡 Data Source Status")

    if data_mode == "Simulation":
        st.info(
            "**🔵 Simulation Mode** — Physics engine generates synthetic data "
            "seeded per basin. All sensor columns (S1, S2, GPM, MODIS ET) are modelled. "
            "No external files needed."
        )

    elif data_mode == "Indirect CSV (Archive)":
        st.markdown(
            "<div style='background:#1c1700;border:1px solid #d29922;border-radius:8px;"
            "padding:0.8rem 1rem;margin-bottom:0.5rem;'>"
            "<b style='color:#d29922;'>📂 Indirect CSV (Archive) Mode</b><br>"
            "<span style='color:#94a3b8;font-size:0.88rem;'>"
            "Upload a CSV exported from GEE Component 1 or the Python Pipeline. "
            "The engine merges real observed columns into the physics baseline.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        uploaded_csv = st.file_uploader(
            "Upload archive CSV  (Date column required)",
            type=["csv"],
            key="csv_uploader_v430",
            help="Expected columns: Date + any of: Inflow_BCM, Outflow_BCM, Volume_BCM, "
                 "S1_Area, S2_Area, GPM_Rain_mm, ATDI, fused_area_km2 …",
        )
        if uploaded_csv:
            try:
                df_preview = pd.read_csv(uploaded_csv)
                df_preview["Date"] = pd.to_datetime(df_preview["Date"], errors="coerce")
                df_preview = df_preview.dropna(subset=["Date"]).sort_values("Date")
                st.session_state["csv_df_v430"] = df_preview
                st.success(
                    f"✅ **{uploaded_csv.name}** loaded — "
                    f"{len(df_preview):,} rows · "
                    f"{df_preview['Date'].dt.date.min()} → "
                    f"{df_preview['Date'].dt.date.max()}"
                )
                st.dataframe(df_preview.head(5), use_container_width=True)
            except Exception as e:
                st.error(f"❌ CSV parse error: {e}")
        elif st.session_state.get("csv_df_v430") is not None:
            df_prev = st.session_state["csv_df_v430"]
            st.success(
                f"✅ Archive loaded ({len(df_prev):,} rows) — "
                f"{df_prev['Date'].dt.date.min()} → {df_prev['Date'].dt.date.max()}"
            )
        else:
            st.caption("No archive uploaded yet. Click RUN to use simulation fallback.")

    elif data_mode == "Direct GEE (Live)":
        st.markdown(
            "<div style='background:#1a0000;border:1px solid #f85149;border-radius:8px;"
            "padding:0.8rem 1rem;margin-bottom:0.5rem;'>"
            "<b style='color:#f85149;'>⚡ Direct GEE (Live) Mode</b><br>"
            "<span style='color:#94a3b8;font-size:0.88rem;'>"
            "Streams real-time satellite data from Google Earth Engine. "
            "Run COMPONENT1_GEE_Live.js → export CSV → upload below. "
            "All 4 datasets live: S1 SAR · S2 MSI · GPM IMERG · MODIS MOD16A2."
            "</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        col_gee1, col_gee2 = st.columns([2, 1])
        with col_gee1:
            gee_csv = st.file_uploader(
                "⚡ Upload GEE Live Export  ({basin}_atdi.csv from Google Drive)",
                type=["csv"],
                key="gee_uploader_v430",
                help="File exported by GEE Component 1 in Mode B or Mode C",
            )
            if gee_csv:
                try:
                    gee_df = pd.read_csv(gee_csv)
                    gee_df["Date"] = pd.to_datetime(
                        gee_df.get("date", gee_df.get("Date", "")), errors="coerce"
                    )
                    gee_df = gee_df.dropna(subset=["Date"]).sort_values("Date")
                    # Normalise column names from GEE lowercase to HSAE title-case
                    col_map = {
                        "fused_area_km2":  "Fused_Area",
                        "s1_area_km2":     "S1_Area",
                        "s2_area_km2":     "S2_Area",
                        "precip_mm":       "GPM_Rain_mm",
                        "et_mm":           "ET_mm",
                        "i_adj_bcm":       "Inflow_BCM",
                        "q_out_bcm":       "Outflow_BCM",
                        "atdi":            "TD_Deficit",
                        "optical_ok":      "optical_ok",
                        "mean_ndwi":       "S2_NDWI",
                    }
                    gee_df.rename(columns={k: v for k, v in col_map.items()
                                           if k in gee_df.columns}, inplace=True)
                    st.session_state["gee_df_v430"] = gee_df
                    rows = len(gee_df)
                    d0   = gee_df["Date"].dt.date.min()
                    d1   = gee_df["Date"].dt.date.max()
                    # Detect datasets present
                    has_s1  = "S1_Area"     in gee_df.columns
                    has_s2  = "S2_Area"     in gee_df.columns
                    has_gpm = "GPM_Rain_mm" in gee_df.columns
                    has_et  = "ET_mm"       in gee_df.columns
                    has_atdi= "TD_Deficit"  in gee_df.columns
                    st.success(f"⚡ **GEE Live data loaded** — {rows:,} rows · {d0} → {d1}")
                    ds_cols = st.columns(5)
                    for col, flag, lbl, clr in [
                        (ds_cols[0], has_s1,   "S1 SAR",   "#58a6ff"),
                        (ds_cols[1], has_s2,   "S2 MSI",   "#3fb950"),
                        (ds_cols[2], has_gpm,  "GPM",      "#d29922"),
                        (ds_cols[3], has_et,   "MOD16",    "#8b5cf6"),
                        (ds_cols[4], has_atdi, "ATDI",     "#f85149"),
                    ]:
                        icon = "✅" if flag else "⬜"
                        col.markdown(
                            f"<div style='text-align:center;background:#0d1117;"
                            f"border:1px solid {'#21262d' if not flag else clr};"
                            f"border-radius:5px;padding:4px;font-size:0.78rem;"
                            f"color:{clr if flag else '#484f58'};'>"
                            f"{icon} {lbl}</div>",
                            unsafe_allow_html=True,
                        )
                    st.dataframe(gee_df.head(5), use_container_width=True)
                except Exception as e:
                    st.error(f"❌ GEE CSV parse error: {e}")
        with col_gee2:
            st.markdown(
                "<div style='background:#0d1117;border:1px solid #30363d;"
                "border-radius:6px;padding:0.7rem;font-size:0.78rem;"
                "color:#8b949e;line-height:1.8;'>"
                "<b style='color:#f85149;'>GEE Workflow</b><br>"
                "1. Open GEE Code Editor<br>"
                "2. Paste COMPONENT1_GEE_Live.js<br>"
                "3. Select Mode B or Mode C<br>"
                "4. Click RUN → Tasks tab<br>"
                "5. Wait for export → Drive<br>"
                "6. Download CSV<br>"
                "7. Upload here ↑"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("🔗 Open GEE Code Editor", use_container_width=True):
                st.markdown(
                    "[Open GEE](https://code.earthengine.google.com)",
                    unsafe_allow_html=True,
                )
        _gee_csv_active = locals().get("gee_csv", None)
    if st.session_state.get("gee_df_v430") is not None and not _gee_csv_active:
            gdf = st.session_state["gee_df_v430"]
            st.success(
                f"⚡ GEE data active ({len(gdf):,} rows) — "
                f"{gdf['Date'].dt.date.min()} → {gdf['Date'].dt.date.max()}"
            )

    # ── RUN ENGINE ────────────────────────────────────────────────────────
    if run_btn:
        with st.spinner(f"🔬 Running [{data_mode}] for {basin_name} …"):

            # ── Always run physics baseline ──────────────────────────────
            df = _run_engine(
                basin, s1_weight, evaporation, seepage_rate,
                lag_days, cloud_thresh, n_days,
            )

            # ── MODE: Indirect CSV — merge real observed columns ─────────
            if data_mode == "Indirect CSV (Archive)":
                df_raw = st.session_state.get("csv_df_v430", pd.DataFrame())
                if not df_raw.empty:
                    # Align on nearest date
                    df_raw_idx = df_raw.set_index("Date")
                    common = [c for c in df_raw_idx.columns
                              if c in df.columns and c != "Date"]
                    if common:
                        merged = df_raw_idx[common].reindex(df["Date"], method="nearest",
                                                             tolerance=pd.Timedelta("32D"))
                        for c in common:
                            valid = merged[c].notna()
                            df.loc[valid, c] = merged.loc[valid, c].values
                        st.success(
                            f"✅ Merged {len(common)} real columns from archive: "
                            f"{', '.join(common[:6])}"
                        )
                    else:
                        st.warning("⚠️ No matching columns found in CSV. "
                                   "Ensure column names match (Date, Inflow_BCM, etc.)")
                else:
                    st.info("ℹ️ No CSV uploaded — running pure simulation fallback.")

            # ── MODE: Direct GEE Live — replace with satellite columns ───
            elif data_mode == "Direct GEE (Live)":
                gee_df = st.session_state.get("gee_df_v430", pd.DataFrame())
                if not gee_df.empty:
                    gee_idx = gee_df.set_index("Date")
                    gee_cols = [c for c in gee_idx.columns
                                if c in df.columns and c != "Date"]
                    if gee_cols:
                        merged = gee_idx[gee_cols].reindex(
                            df["Date"], method="nearest",
                            tolerance=pd.Timedelta("32D")
                        )
                        for c in gee_cols:
                            valid = merged[c].notna()
                            df.loc[valid, c] = merged.loc[valid, c].values
                        # Recompute ATDI from GEE TD_Deficit if present
                        if "TD_Deficit" in gee_cols:
                            td_index = float(df["TD_Deficit"].mean() * 100)
                            forensic  = float(
                                df["TD_Deficit"].rolling(4).mean().max() * 100
                            )
                            st.session_state["td_index"]       = td_index
                            st.session_state["forensic_score"] = forensic
                        st.success(
                            f"⚡ GEE Live columns merged: "
                            f"{', '.join(gee_cols[:8])}"
                        )
                    else:
                        st.warning("⚠️ No matching GEE columns. Using simulation baseline.")
                else:
                    st.info(
                        "ℹ️ No GEE export uploaded yet. "
                        "Running simulation. Upload {basin}_atdi.csv to activate live mode."
                    )

            st.session_state["df"]          = df
            st.session_state["basin_v430"]  = basin
            st.session_state["data_mode_used"] = data_mode
            st.session_state["executed"]    = True
            st.rerun()

    # ── RESULTS ───────────────────────────────────────────────────────────
    if not st.session_state.get("executed") or st.session_state.get("df") is None:
        st.info("👈 Configure parameters above and click **🚀 RUN ENGINE** to start analysis.")
        return

    df    = st.session_state["df"]
    basin = st.session_state.get("basin_v430", basin)

    closure      = st.session_state.get("closure_error", 0.0)
    td_index     = st.session_state.get("td_index",      0.0)
    forensic_sc  = st.session_state.get("forensic_score",0.0)
    cloudy_ratio = st.session_state.get("cloudy_ratio",  0.0)
    _lag         = st.session_state.get("lag_days", 3)

    # ── KPI row (FIX: mean for representative metrics) ────────────────────
    st.markdown("---")
    st.markdown("### 🚀 EXECUTIVE SUMMARY")

    fill_pct   = float(df["Pct_Full"].mean())
    # FIX: use mean — iloc[-1] picks an arbitrary edge row that may be unrepresentative
    area_mean  = float(df["Effective_Area"].mean())
    stor_mean  = float(df["Volume_BCM"].mean())
    rain_mean  = float(df["GPM_Rain_mm"].mean())
    power_mean = float(df["Power_MW"].clip(lower=0).mean())
    lag_mean   = float(df["Lag_Effect"].mean())

    k = st.columns(8)
    k[0].metric("🛰️ Fused Area",    f"{area_mean:.0f} km²")
    k[1].metric("💧 Storage",        f"{stor_mean:.2f} BCM",  f"avg {fill_pct:.1f}% full")
    k[2].metric("🌧️ GPM Rain (avg)", f"{rain_mean:.1f} mm/d")
    k[3].metric("⚡ Power (avg)",    f"{power_mean:.0f} MW")
    k[4].metric("🎯 Closure Error",  f"{closure:.2f}%",
                help="<2% excellent · <5% good · >5% review inputs")
    k[5].metric("⏱️ Lag Effect",     f"{lag_mean:.2f}×")
    k[6].metric("🔍 TDI",            f"{td_index:.1f}%",
                help="Transparency Deficit Index")
    k[7].metric("🕵️ Forensic",       f"{forensic_sc:.1f}%")

    # ── TABS ─────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "⚖️ Mass Balance", "🛰️ Sensor Fusion", "🌿 NDWI/NDVI",
        "🧠 AI Forecast",  "⏱️ Lag Analysis",  "☁️ Cloud Mask",
        "📊 Ground Truth", "🌧️ GPM Forecast",  "🕵️ Forensics",
        "🌍 Benchmark",
    ])
    (tab_mb, tab_sf, tab_ndwi, tab_ai,
     tab_lag, tab_cld, tab_gt, tab_gpm,
     tab_frn, tab_bm) = tabs

    # ── Tab 1: Mass Balance ───────────────────────────────────────────────
    with tab_mb:
        st.markdown(f"#### Water Mass Balance — {basin_name}")
        st.latex(
            rf"V = {basin['bathy_a']:.3f}\times A^{{{basin['bathy_b']:.2f}}}"
            rf"\quad\Delta V = I_{{in}} - Q_{{out}} - E_{{vap}} - S_{{eep}}"
        )
        st.metric("Closure Error", f"{closure:.2f}%",
                  help="Residual ÷ Total Inflow × 100")

        fig_mb = make_subplots(rows=2, cols=1, shared_xaxes=True,
                               subplot_titles=["Inflow & Outflow (BCM/day)",
                                               "Storage (BCM)"])
        fig_mb.add_trace(go.Bar(x=df["Date"], y=df["Inflow_BCM"],
                                name="Inflow", marker_color="#10b981"), row=1, col=1)
        fig_mb.add_trace(go.Bar(x=df["Date"], y=-df["Outflow_BCM"],
                                name="Outflow", marker_color="#ef4444"), row=1, col=1)
        fig_mb.add_trace(go.Scatter(x=df["Date"], y=df["Volume_BCM"],
                                    name="Storage",
                                    line=dict(color="#3b82f6", width=2)), row=2, col=1)
        fig_mb.add_hline(y=basin["cap"], line_dash="dash", line_color="#fbbf24",
                         annotation_text=f"Max {basin['cap']} BCM", row=2, col=1)
        fig_mb.update_layout(template="plotly_dark", height=520,
                             title=f"Mass Balance — {basin_name}",
                             barmode="overlay")
        st.plotly_chart(fig_mb, use_container_width=True)

        # Losses breakdown
        col_l1, col_l2, col_l3 = st.columns(3)
        col_l1.metric("Total Inflow",  f"{df['Inflow_BCM'].sum():.2f} BCM")
        col_l2.metric("Total Outflow", f"{df['Outflow_BCM'].sum():.2f} BCM")
        col_l3.metric("Total Losses",  f"{df['Losses'].sum():.2f} BCM")

    # ── Tab 2: Sensor Fusion ──────────────────────────────────────────────
    with tab_sf:
        st.markdown(f"#### Sensor Fusion (S1 SAR + S2 Optical) — {basin_name}")
        fig_sf = go.Figure()
        fig_sf.add_trace(go.Scatter(x=df["Date"], y=df["S1_Area"],
                                    name="S1 SAR", line=dict(color="#f97316")))
        fig_sf.add_trace(go.Scatter(x=df["Date"], y=df["S2_Area"],
                                    name="S2 Optical", line=dict(color="#a78bfa")))
        fig_sf.add_trace(go.Scatter(x=df["Date"], y=df["Effective_Area"],
                                    name="Fused / Effective",
                                    line=dict(color="#10b981", width=3)))
        fig_sf.add_hline(y=basin["area_max"], line_dash="dash", line_color="#fbbf24",
                         annotation_text=f"Max area {basin['area_max']} km²")
        fig_sf.update_layout(template="plotly_dark", height=420,
                             title=f"SAR + Optical Fusion — {basin_name}",
                             yaxis_title="Surface Area (km²)")
        st.plotly_chart(fig_sf, use_container_width=True)
        st.caption(
            f"Cloud/gap days (SAR-only fallback): **{cloudy_ratio:.1f}%**  |  "
            f"S1 weight: {s1_weight:.0%}  ·  S2 weight: {1-s1_weight:.0%}"
        )

    # ── Tab 3: NDWI / NDVI ───────────────────────────────────────────────
    with tab_ndwi:
        df["NDVI"] = np.clip((df["S2_NDWI"] - 0.2) / (df["S2_NDWI"] + 0.2), -0.2, 0.9)
        st.latex(r"\text{NDWI}=\frac{Green-NIR}{Green+NIR}"
                 r"\qquad\text{NDVI}=\frac{NIR-Red}{NIR+Red}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**NDWI — Water Index**")
            st.line_chart(df.set_index("Date")["S2_NDWI"])
        with c2:
            st.markdown("**NDVI — Vegetation Proxy**")
            st.line_chart(df.set_index("Date")["NDVI"])

    # ── Tab 4: AI Forecast ────────────────────────────────────────────────
    with tab_ai:
        st.markdown(f"#### AI Storage Forecast + 95% CI — {basin_name}")
        feats  = df[["S1_VV_dB","S2_NDWI","GPM_Rain_mm","Effective_Area"]].fillna(0)
        target = df["Volume_BCM"]
        rf_vol = RandomForestRegressor(n_estimators=150, max_depth=8, random_state=42)
        rf_vol.fit(feats, target)

        future_days = 90
        f_dates = pd.date_range(df["Date"].max() + timedelta(1), periods=future_days)
        f_feat  = feats.tail(14).mean().values.reshape(1, -1)
        preds, upp, low = [], [], []
        for _ in range(future_days):
            tp = np.array([t.predict(f_feat) for t in rf_vol.estimators_])
            preds.append(float(tp.mean()))
            upp.append(float(np.percentile(tp, 95)))
            low.append(float(np.percentile(tp, 5)))

        fig_ai = go.Figure()
        fig_ai.add_trace(go.Scatter(x=df["Date"], y=df["Volume_BCM"],
                                    name="Historical", line=dict(color="#10b981")))
        fig_ai.add_trace(go.Scatter(x=f_dates, y=preds,
                                    name="Forecast", line=dict(color="#fbbf24", width=3)))
        fig_ai.add_trace(go.Scatter(x=f_dates, y=upp, showlegend=False,
                                    line=dict(color="rgba(251,191,36,0)")))
        fig_ai.add_trace(go.Scatter(x=f_dates, y=low, fill="tonexty",
                                    fillcolor="rgba(251,191,36,0.15)",
                                    line=dict(color="rgba(251,191,36,0)"),
                                    name="95% CI"))
        fig_ai.add_hline(y=basin["cap"], line_dash="dash", line_color="#ef4444",
                         annotation_text=f"Max capacity {basin['cap']} BCM")
        fig_ai.update_layout(template="plotly_dark", height=480,
                             title=f"90-Day Storage Forecast — {basin_name}",
                             yaxis_title="Storage (BCM)")
        st.plotly_chart(fig_ai, use_container_width=True)

    # ── Tab 5: Lag Analysis ───────────────────────────────────────────────
    with tab_lag:
        st.markdown(f"#### Hydrological Lag Analysis — {basin_name}")
        fig_lag = make_subplots(specs=[[{"secondary_y": True}]])
        fig_lag.add_trace(go.Scatter(x=df["Date"], y=df["Inflow_BCM_raw"],
                                     name="Raw Inflow",
                                     line=dict(color="#3b82f6")), secondary_y=False)
        fig_lag.add_trace(go.Scatter(x=df["Date"], y=df["Inflow_BCM"],
                                     name=f"Lagged ({_lag}d)",
                                     line=dict(color="#10b981", width=3)), secondary_y=False)
        fig_lag.add_trace(go.Scatter(x=df["Date"], y=df["Lag_Effect"],
                                     name="Lag Multiplier",
                                     line=dict(color="#f97316")), secondary_y=True)
        fig_lag.update_layout(template="plotly_dark", height=440,
                             title=f"Lag={_lag} days — {basin_name}")
        fig_lag.update_yaxes(title_text="BCM/day", secondary_y=False)
        fig_lag.update_yaxes(title_text="Lag ×", secondary_y=True)
        st.plotly_chart(fig_lag, use_container_width=True)
        st.metric("Average Lag Multiplier", f"{df['Lag_Effect'].mean():.2f}×")

    # ── Tab 6: Cloud Masking ──────────────────────────────────────────────
    with tab_cld:
        st.markdown(f"#### Sentinel-2 Cloud Masking — {basin_name}")
        st.metric("Cloud / Gap Days", f"{cloudy_ratio:.1f}%",
                  help="Fraction of days where S2 was unavailable; SAR used as fallback")
        st.code("""
def mask_s2_clouds(image):
    qa            = image.select('QA60')
    cloud_mask    = qa.bitwiseAnd(1 << 10).eq(0)
    cirrus_mask   = qa.bitwiseAnd(1 << 11).eq(0)
    return image.updateMask(cloud_mask.And(cirrus_mask)).divide(10000)
        """, language="python")
        # Visual: optical valid timeline
        fig_cld = go.Figure()
        opt_arr = df["S2_NDWI"] >= (cloud_thresh if "cloud_thresh" in dir() else 0.25)
        fig_cld.add_trace(go.Bar(x=df["Date"], y=opt_arr.astype(int),
                                 name="Optical Valid", marker_color="#10b981"))
        fig_cld.add_trace(go.Bar(x=df["Date"], y=(~opt_arr).astype(int),
                                 name="SAR Fallback", marker_color="#f97316"))
        fig_cld.update_layout(template="plotly_dark", height=280,
                             barmode="stack", title="Data Availability Timeline",
                             yaxis=dict(tickvals=[0,1], ticktext=["No","Yes"]))
        st.plotly_chart(fig_cld, use_container_width=True)

    # ── Tab 7: Ground Truth ───────────────────────────────────────────────
    with tab_gt:
        st.markdown(f"#### Ground Truth Validation — {basin_name}")
        st.info(
            "Upload any gauge station CSV (worldwide).  \n"
            "**Flexible column names accepted:**  \n"
            "`Date` · `Inflow_obs` / `discharge` / `flow` / `q`  "
            "· `Volume_obs` / `storage`  · `Level_obs` / `stage`  "
            "· `Rain_obs` / `rainfall`  \n"
            "Discharge in m³/s is auto-converted to BCM/day."
        )

        gt_file = st.file_uploader(
            "Upload Ground Truth CSV (any station, any river)",
            type=["csv", "txt", "xlsx"],
            key="gt_v430",
        )

        if gt_file:
            try:
                df_gt = pd.read_csv(gt_file) if not gt_file.name.endswith(".xlsx") \
                        else pd.read_excel(gt_file)
            except Exception as e:
                st.error(f"File read error: {e}")
                df_gt = None

            if df_gt is not None:
                # Flexible column mapping
                col_map = {
                    "date":"Date","DATE":"Date","datetime":"Date",
                    "التاريخ":"Date",
                    "inflow":"Inflow_obs","discharge":"Inflow_obs",
                    "flow":"Inflow_obs","q":"Inflow_obs","q_obs":"Inflow_obs",
                    "التدفق":"Inflow_obs",
                    "volume":"Volume_obs","storage":"Volume_obs",
                    "التخزين":"Volume_obs",
                    "level":"Level_obs","stage":"Level_obs","wl":"Level_obs",
                    "المنسوب":"Level_obs",
                    "rain":"Rain_obs","rainfall":"Rain_obs","precip":"Rain_obs",
                    "المطر":"Rain_obs",
                }
                df_gt = df_gt.rename(columns={
                    c: col_map[c.strip().lower()] for c in df_gt.columns
                    if c.strip().lower() in col_map
                })

                if "Date" not in df_gt.columns:
                    st.error("Could not find a Date column.")
                else:
                    df_gt["Date"] = pd.to_datetime(df_gt["Date"], errors="coerce")
                    df_gt = df_gt.dropna(subset=["Date"])

                    # Auto-scale m³/s → BCM/day
                    for col in ["Inflow_obs", "Volume_obs"]:
                        if col in df_gt.columns:
                            med = df_gt[col].median()
                            if med > 500:   # likely m³/s
                                df_gt[col] = df_gt[col] * 86400 / 1e9

                    merged = df[["Date","Inflow_BCM","Volume_BCM","GPM_Rain_mm"]]\
                               .merge(df_gt, on="Date", how="inner")

                    st.success(
                        f"Merged: **{len(merged):,} rows** | "
                        f"{merged['Date'].min().date()} → {merged['Date'].max().date()}"
                    )

                    for obs_col, mdl_col, unit in [
                        ("Inflow_obs", "Inflow_BCM", "BCM/day"),
                        ("Volume_obs", "Volume_BCM", "BCM"),
                        ("Rain_obs",   "GPM_Rain_mm","mm/day"),
                    ]:
                        if obs_col not in merged.columns or mdl_col not in merged.columns:
                            continue
                        valid = merged[[obs_col, mdl_col]].dropna()
                        if len(valid) < 3:
                            continue
                        obs = valid[obs_col].values
                        sim = valid[mdl_col].values
                        rmse = float(np.sqrt(np.mean((sim - obs) ** 2)))
                        r2   = float(r2_score(obs, sim))
                        nse  = float(1 - np.sum((obs-sim)**2)/(np.sum((obs-np.mean(obs))**2)+1e-9))

                        lbl = obs_col.replace("_obs","")
                        st.markdown(f"**{lbl}** [{unit}]")
                        cc = st.columns(3)
                        cc[0].metric("RMSE",  f"{rmse:.4f}")
                        cc[1].metric("R²",    f"{r2:.3f}")
                        cc[2].metric("NSE",   f"{nse:.3f}")

                        fig_cmp = go.Figure()
                        fig_cmp.add_trace(go.Scatter(x=merged["Date"],
                            y=obs, name="Station", line=dict(color="#3b82f6",width=2)))
                        fig_cmp.add_trace(go.Scatter(x=merged["Date"],
                            y=sim, name="HSAE", line=dict(color="#10b981",width=2,dash="dot")))
                        fig_cmp.update_layout(template="plotly_dark", height=300,
                            title=f"{lbl}: Station vs HSAE Model — {basin_name}")
                        st.plotly_chart(fig_cmp, use_container_width=True)

    # ── Tab 8: GPM Forecast ───────────────────────────────────────────────
    with tab_gpm:
        st.markdown(f"#### GPM Inflow Forecast — {basin_name}")
        lead = st.slider("Lead time (days)", 3, 7, 5, key="gpm_lead")
        model_gpm, r2_gpm, rmse_gpm = _gpm_model(df, lead)
        if model_gpm is None:
            st.warning("Series too short (need ≥ 60 days). Increase simulation period.")
        else:
            g1, g2 = st.columns(2)
            g1.metric("R² (GPM→Inflow)", f"{r2_gpm:.3f}")
            g2.metric("RMSE (BCM/day)",   f"{rmse_gpm:.4f}")

            last_rain = df["GPM_Rain_mm"].tail(3).values
            rain_fut  = np.full(7, last_rain.mean())
            feats_fut = [
                [rain_fut[i],
                 last_rain[-1] if i == 0 else rain_fut[i-1],
                 last_rain[-2] if i <  2 else rain_fut[i-2],
                 rain_fut[max(0,i-3):i+1].mean()]
                for i in range(7)
            ]
            inflow_fc = model_gpm.predict(np.array(feats_fut))
            fut_dates = pd.date_range(df["Date"].max() + timedelta(1), periods=7)

            fig_gpm = go.Figure()
            fig_gpm.add_trace(go.Scatter(x=df["Date"].tail(60), y=df["Inflow_BCM"].tail(60),
                                         name="Historical", line=dict(color="#10b981")))
            fig_gpm.add_trace(go.Scatter(x=fut_dates, y=inflow_fc,
                                         name=f"Forecast (+{lead}d)",
                                         line=dict(color="#f97316", width=3)))
            fig_gpm.update_layout(template="plotly_dark", height=400,
                                  title=f"GPM Inflow Forecast (lead={lead}d) — {basin_name}",
                                  yaxis_title="Inflow (BCM/day)")
            st.plotly_chart(fig_gpm, use_container_width=True)

    # ── Tab 9: Hydro-Forensics ────────────────────────────────────────────
    with tab_frn:
        st.markdown(f"#### Hydro-Forensics · TDI — {basin_name}")
        st.caption(
            f"Under **{treaty_lbl}** ({basin.get('legal_arts','—')}): "
            "sustained positive deficit between expected rain-response and declared outflow "
            "may indicate undisclosed storage operations."
        )
        rain_n = df["GPM_Rain_mm"] / (df["GPM_Rain_mm"].max() + 1e-9)
        out_n  = df["Outflow_BCM"] / (df["Outflow_BCM"].max() + 1e-9)

        fig_frn = go.Figure()
        fig_frn.add_trace(go.Scatter(x=df["Date"], y=rain_n,
                                     name="GPM Rain (norm.)", line=dict(color="#3b82f6")))
        fig_frn.add_trace(go.Scatter(x=df["Date"], y=out_n,
                                     name="Outflow (norm.)",  line=dict(color="#10b981")))
        fig_frn.add_trace(go.Scatter(x=df["Date"], y=df["TD_Deficit"],
                                     fill="tozeroy", fillcolor="rgba(239,68,68,0.15)",
                                     name="TD Deficit", line=dict(color="#ef4444")))
        fig_frn.update_layout(template="plotly_dark", height=460,
                             title=f"Transparency Deficit Index — {basin_name}")
        st.plotly_chart(fig_frn, use_container_width=True)

        fc1, fc2 = st.columns(2)
        fc1.metric("TDI (mean)",           f"{td_index:.1f}%")
        fc2.metric("Peak Forensic Score",  f"{forensic_sc:.1f}%")

    # ── Tab 10: Global Benchmark ──────────────────────────────────────────
    with tab_bm:
        st.markdown("#### 🌍 Global Transparency Benchmark")

        @st.cache_data(show_spinner="Computing global benchmark …", ttl=900)
        def _benchmark_all(evap, seep, lag):
            rows = []
            for nm, cfg in GLOBAL_BASINS.items():
                try:
                    _d = _run_engine(cfg, 0.65, evap, seep, lag, 0.25, 365)
                    rows.append({
                        "Basin":        nm,
                        "Continent":    cfg["continent"],
                        "River":        cfg["river"],
                        "Cap (BCM)":    cfg["cap"],
                        "Head (m)":     cfg["head"],
                        "Countries":    ", ".join(cfg.get("country",[])[:3]),
                        "TDI (%)":      round(float(_d["TD_Deficit"].mean()*100), 1),
                        "Transp. (%)":  round(100 - float(_d["TD_Deficit"].mean()*100), 1),
                        "Power (MW)":   round(float(_d["Power_MW"].mean()), 0),
                        "Fill (%)":     round(float(_d["Pct_Full"].mean()), 1),
                        "Treaty":       cfg.get("treaty","—"),
                    })
                except Exception:
                    pass
            return pd.DataFrame(rows)

        df_bm = _benchmark_all(evaporation, seepage_rate, lag_days)

        if df_bm.empty:
            st.warning("Benchmark computation failed.")
        else:
            avg_t  = df_bm["Transp. (%)"].mean()
            act_r  = df_bm[df_bm["Basin"] == basin_name]
            act_t  = float(act_r["Transp. (%)"].iloc[0]) if len(act_r) else avg_t

            bm1, bm2, bm3, bm4 = st.columns(4)
            bm1.metric(f"Transp. — {basin_name[:22]}", f"{act_t:.1f}%",
                       f"{act_t-avg_t:+.1f}% vs global avg")
            bm2.metric("Global Avg",    f"{avg_t:.1f}%")
            bm3.metric("Most transp.",  df_bm.loc[df_bm["Transp. (%)"].idxmax(),"Basin"][:28])
            bm4.metric("Least transp.", df_bm.loc[df_bm["Transp. (%)"].idxmin(),"Basin"][:28])

            df_bm["Selected"] = df_bm["Basin"].apply(
                lambda x: "⭐ Selected" if x == basin_name else "Others"
            )
            fig_sc = px.scatter(
                df_bm, x="Cap (BCM)", y="Transp. (%)",
                color="Continent", size="Head (m)", hover_name="Basin",
                hover_data=["River","Countries","TDI (%)","Treaty"],
                symbol="Selected",
                symbol_map={"⭐ Selected":"star","Others":"circle"},
                template="plotly_dark", height=480,
                title="Transparency vs Storage Capacity (Global)",
                color_discrete_sequence=px.colors.qualitative.Vivid,
            )
            fig_sc.add_hline(y=avg_t, line_dash="dash", line_color="#fbbf24",
                             annotation_text=f"Global avg {avg_t:.1f}%")
            st.plotly_chart(fig_sc, use_container_width=True)

            # Ranking bar
            df_s = df_bm.sort_values("TDI (%)")
            colors = ["#f59e0b" if b == basin_name else "#3b82f6"
                      for b in df_s["Basin"]]
            fig_bar = go.Figure(go.Bar(
                y=df_s["Basin"], x=df_s["TDI (%)"],
                orientation="h", marker_color=colors,
                text=[f"{v:.1f}%" for v in df_s["TDI (%)"]],
                textposition="outside",
            ))
            fig_bar.update_layout(
                template="plotly_dark",
                height=max(400, len(df_bm) * 23),
                title="TDI Global Ranking  (🟡 = selected basin)",
                xaxis_title="TD Index %  (lower = more transparent)",
                margin=dict(l=230),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            with st.expander("📋 Full benchmark table"):
                num_cols = ["Cap (BCM)","Head (m)","TDI (%)","Transp. (%)","Power (MW)","Fill (%)"]
                for c in num_cols:
                    df_bm[c] = pd.to_numeric(df_bm[c], errors="coerce")
                st.dataframe(
                    df_bm.sort_values("Transp. (%)", ascending=False)
                         .reset_index(drop=True)
                         .style
                         .highlight_max(subset=["Transp. (%)"], color="#064e3b")
                         .highlight_min(subset=["TDI (%)"],     color="#1e3a5f")
                         .format({c: "{:.1f}" for c in num_cols}),
                    use_container_width=True,
                )