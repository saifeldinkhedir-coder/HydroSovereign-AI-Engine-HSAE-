# hsae_science.py  –  HSAE Scientific Enhancement Module
# Updated: 2026-02-26  |  Author: Seifeldin M. G. Alkedir
# Covers:
#   1. Sentinel-2 Water Mask overlay (folium ImageOverlay)
#   2. Penman-Monteith Evapotranspiration
#   3. Power Generation (ρ·g·Q·H·η)
#   4. Full 100% Water Balance
#   5. Monte Carlo Uncertainty Quantification

from __future__ import annotations
from hsae_tdi import add_tdi_to_df, tdi_summary, tdi_legal_status
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import Optional
import io, base64

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except ImportError:
    FOLIUM_OK = False


# ══════════════════════════════════════════════════════════════════════════════
# 1. SENTINEL-2 WATER MASK — folium ImageOverlay
# ══════════════════════════════════════════════════════════════════════════════

def _ndwi_to_rgba_png(ndwi_grid: np.ndarray) -> str:
    """
    Convert a 2-D NDWI grid → RGBA PNG → base64 string for folium overlay.
    Water pixels (NDWI > 0.2) → semi-transparent blue.
    """
    import struct, zlib

    h, w = ndwi_grid.shape
    water_mask = ndwi_grid > 0.2

    # Build RGBA array: water=blue(0,120,255,180), land=transparent
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[water_mask] = [0, 120, 255, 180]

    # Minimal PNG encoder (no external libs needed)
    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return (
            len(data).to_bytes(4, "big") + c
            + zlib.crc32(c).to_bytes(4, "big")
        )

    rows = b""
    for row in rgba:
        rows += b"\x00"  # filter byte
        rows += row.flatten().tobytes()

    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR",
                     struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(rows, 9))
        + _png_chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()


def render_water_mask_map(
    basin: dict,
    ndwi_series: Optional[pd.Series] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> None:
    """
    Render a folium map with a Sentinel-2 NDWI water mask overlay.
    If no real NDWI raster is available, generates a synthetic demo grid.
    """
    if not FOLIUM_OK:
        st.warning("Install `folium` and `streamlit-folium` for map overlays.")
        return

    basin_lat = lat or basin.get("lat", 0.0)
    basin_lon = lon or basin.get("lon", 0.0)
    bbox      = basin.get("bbox", [basin_lon-1, basin_lat-1,
                                   basin_lon+1, basin_lat+1])

    # ── Synthetic NDWI raster (demo) ──────────────────────────────────────
    grid_size = 64
    rng = np.random.default_rng(abs(hash(basin.get("id","x"))) % (2**31))

    # Gaussian water body centred on basin
    y_idx, x_idx = np.mgrid[0:grid_size, 0:grid_size]
    cy, cx = grid_size // 2, grid_size // 2
    sigma  = grid_size * 0.22
    ndwi_grid = np.exp(
        -((x_idx - cx)**2 + (y_idx - cy)**2) / (2 * sigma**2)
    ) * 0.9 - 0.1 + rng.normal(0, 0.04, (grid_size, grid_size))

    # Boost if recent NDWI is high
    if ndwi_series is not None and len(ndwi_series) > 0:
        boost = float(ndwi_series.iloc[-30:].mean())
        ndwi_grid = np.clip(ndwi_grid + boost * 0.3, -0.5, 1.0)

    # ── Build map ──────────────────────────────────────────────────────────
    m = folium.Map(
        location=[basin_lat, basin_lon],
        zoom_start=7,
        tiles="CartoDB dark_matter",
    )

    # NDWI water mask overlay
    png_b64 = _ndwi_to_rgba_png(ndwi_grid)
    folium.raster_layers.ImageOverlay(
        image=png_b64,
        bounds=[[bbox[1], bbox[0]], [bbox[3], bbox[2]]],
        opacity=0.70,
        name="Sentinel-2 NDWI Water Mask",
        interactive=True,
        cross_origin=False,
        zindex=1,
    ).add_to(m)

    # Dam marker
    folium.Marker(
        location=[basin_lat, basin_lon],
        popup=folium.Popup(
            f"<b>{basin.get('id','Basin')}</b><br>"
            f"Cap: {basin.get('cap',0):.1f} BCM<br>"
            f"River: {basin.get('river','')}",
            max_width=220,
        ),
        icon=folium.Icon(color="blue", icon="tint", prefix="fa"),
    ).add_to(m)

    folium.LayerControl().add_to(m)

    st_folium(m, width="100%", height=450, key="s2_water_mask_map")

    # Legend
    st.markdown("""
<div style="background:#0d1117;border:1px solid #1e40af;border-radius:8px;
     padding:.7rem 1rem;margin-top:.5rem;font-size:.82rem;color:#93c5fd;">
  🟦 <b>Water body</b> — Sentinel-2 NDWI &gt; 0.2 &nbsp;|&nbsp;
  🔵 Marker = Dam location &nbsp;|&nbsp;
  Opacity = 70% (adjustable) &nbsp;|&nbsp;
  <i>Demo raster — connect GEE for live imagery</i>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. PENMAN-MONTEITH EVAPOTRANSPIRATION
# ══════════════════════════════════════════════════════════════════════════════

def penman_monteith(
    T_mean_C:  np.ndarray,         # Mean air temperature (°C)
    RH_pct:    np.ndarray,         # Relative humidity (%)
    u2_ms:     np.ndarray,         # Wind speed at 2m (m/s)
    Rs_MJm2:   np.ndarray,         # Solar radiation (MJ/m²/day)
    lat_deg:   float = 15.0,
    doy:       Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    FAO-56 Penman-Monteith reference evapotranspiration ET₀ (mm/day).

    ET₀ = [0.408·Δ·(Rn−G) + γ·(900/(T+273))·u2·(es−ea)] /
           [Δ + γ·(1 + 0.34·u2)]

    Returns ET₀ in mm/day.
    """
    n = len(T_mean_C)
    if doy is None:
        doy = np.arange(1, n + 1) % 365 + 1

    # Saturation vapour pressure (kPa)
    es = 0.6108 * np.exp(17.27 * T_mean_C / (T_mean_C + 237.3))
    ea = es * (RH_pct / 100.0)

    # Slope of saturation vapour pressure curve Δ (kPa/°C)
    Delta = 4098 * es / (T_mean_C + 237.3) ** 2

    # Psychrometric constant γ (kPa/°C) at ~100 kPa
    gamma = 0.0665

    # Extraterrestrial radiation Ra (MJ/m²/day) — FAO-56 Eq. 21
    phi   = np.deg2rad(lat_deg)
    delta = 0.409 * np.sin(2 * np.pi / 365 * doy - 1.39)
    dr    = 1 + 0.033 * np.cos(2 * np.pi / 365 * doy)
    ws    = np.arccos(-np.tan(phi) * np.tan(delta))
    Ra    = (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(delta)
        + np.cos(phi) * np.cos(delta) * np.sin(ws)
    )

    # Net radiation Rn (MJ/m²/day) — simplified
    Rns  = (1 - 0.23) * Rs_MJm2                  # net shortwave
    Rnl  = 4.903e-9 * (T_mean_C + 273.16) ** 4 * (
        0.34 - 0.14 * np.sqrt(ea)
    ) * (1.35 * Rs_MJm2 / (0.75 * Ra + 1e-6) - 0.35)
    Rn   = Rns - Rnl
    G    = 0.0                                     # soil heat flux ≈ 0

    # ET₀ (mm/day)
    ET0 = (
        0.408 * Delta * (Rn - G)
        + gamma * (900 / (T_mean_C + 273)) * u2_ms * (es - ea)
    ) / (Delta + gamma * (1 + 0.34 * u2_ms))

    return np.maximum(ET0, 0.0)


def compute_pm_evap_BCM(
    df:        pd.DataFrame,
    basin:     dict,
    T_C:       float = 28.0,
    RH_pct:    float = 45.0,
    u2_ms:     float = 2.5,
    Rs_MJm2:   float = 22.0,
) -> pd.DataFrame:
    """
    Add Penman-Monteith ET₀ column to df.
    Converts mm/day × surface area (km²) → BCM.
    """
    n     = len(df)
    T_arr = np.full(n, T_C)   + np.random.default_rng(7).normal(0, 2, n)
    RH    = np.full(n, RH_pct)+ np.random.default_rng(8).normal(0, 5, n)
    u2    = np.full(n, u2_ms) + np.random.default_rng(9).normal(0, 0.3, n)
    Rs    = np.full(n, Rs_MJm2)+np.random.default_rng(10).normal(0, 3, n)
    doy   = pd.to_datetime(df["Date"]).dt.dayofyear.values

    ET0_mm = penman_monteith(
        T_arr, np.clip(RH, 10, 100), np.clip(u2, 0.1, 10),
        np.clip(Rs, 1, 40),
        lat_deg=basin.get("lat", 15.0),
        doy=doy,
    )

    area_km2 = df.get("Effective_Area",
                      pd.Series(np.full(n, basin.get("area_max",1000)*0.7)))
    # ET₀ (mm/day) × Area (km²) → BCM
    # 1 mm × 1 km² = 10^3 m³ = 10^-6 BCM  →  × 1e-6 × 1e3 = 1e-3
    df["ET0_mm_day"]  = ET0_mm
    df["Evap_PM_BCM"] = ET0_mm * area_km2.values * 1e-3

    return df


# ══════════════════════════════════════════════════════════════════════════════
# 3. POWER GENERATION  —  P = ρ·g·Q·H·η
# ══════════════════════════════════════════════════════════════════════════════

RHO_WATER = 1000.0   # kg/m³
G_ACC     = 9.81     # m/s²
BCM_TO_M3S = 1e9 / 86400  # BCM/day → m³/s


def compute_power_MW(
    Q_BCM_day: np.ndarray,
    H_m:       float,
    eta:       float = 0.88,
) -> np.ndarray:
    """
    Hydropower output in MW.
    P = ρ · g · Q · H · η  [W] → [MW]

    Q_BCM_day : daily discharge (BCM)
    H_m       : effective head (m)
    eta       : plant efficiency (default 0.88)
    """
    Q_m3s = Q_BCM_day * BCM_TO_M3S
    P_W   = RHO_WATER * G_ACC * Q_m3s * H_m * eta
    return P_W / 1e6   # → MW


def add_power_to_df(df: pd.DataFrame, basin: dict,
                    eta: float = 0.88) -> pd.DataFrame:
    """Add Power_MW and Energy_GWh columns to df."""
    H = float(basin.get("head", 100))
    df["Power_MW"]   = compute_power_MW(df["Outflow_BCM"].values, H, eta)
    df["Energy_GWh"] = df["Power_MW"] * 24 / 1000.0   # MW·h/day → GWh/day
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 4. FULL 100% WATER BALANCE
# ══════════════════════════════════════════════════════════════════════════════

def compute_full_balance(df: pd.DataFrame, basin: dict) -> pd.DataFrame:
    """
    ΔV = Q_in − Q_out − E_PM − S_seep − W_power_loss

    Adds: dV_full, MB_full_Error, MB_full_pct, Seepage_BCM (if absent)
    """
    if "Evap_PM_BCM" not in df.columns:
        df = compute_pm_evap_BCM(df, basin)
    if "Power_MW" not in df.columns:
        df = add_power_to_df(df, basin)

    # Derive Seepage_BCM if not produced by the engine
    # v430 engine stores combined evap+seep as "Losses";
    # we approximate seepage as the residual after subtracting PM evaporation.
    if "Seepage_BCM" not in df.columns:
        if "Losses" in df.columns:
            # Losses = Evap_simple + Seepage; use PM evap as the better evap estimate
            df["Seepage_BCM"] = (df["Losses"] - df.get("Evap_PM_BCM",
                pd.Series(0, index=df.index))).clip(lower=0)
        else:
            # Fallback: estimate seepage as 0.45% of volume per day
            df["Seepage_BCM"] = (df["Volume_BCM"] * 0.0045).clip(lower=0)

    # Water consumed for energy generation (tiny but real):
    # ΔH loss due to turbine discharge already in Outflow; no extra term.
    df["dV_full"] = (
        df["Inflow_BCM"]
        - df["Outflow_BCM"]
        - df["Evap_PM_BCM"]
        - df["Seepage_BCM"]
    )
    df["dV_obs_full"]      = df["Volume_BCM"].diff().fillna(0)
    df["MB_full_Error"]    = df["dV_obs_full"] - df["dV_full"]
    df["MB_full_pct"]      = (
        df["MB_full_Error"].abs() / (basin["cap"] + 1e-9) * 100
    )
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 5. MONTE CARLO UNCERTAINTY QUANTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def monte_carlo_balance(
    df:        pd.DataFrame,
    basin:     dict,
    n_sim:     int  = 1000,
    sigma_q:   float = 0.05,   # ±5% inflow uncertainty
    sigma_e:   float = 0.10,   # ±10% evap uncertainty
    sigma_s:   float = 0.15,   # ±15% seepage uncertainty
    seed:      int  = 42,
) -> dict:
    """
    Monte Carlo simulation of water balance uncertainty.
    Returns dict with percentile arrays for Volume, Inflow, Outflow.
    """
    rng  = np.random.default_rng(seed)
    n    = len(df)
    vols = np.zeros((n_sim, n))

    Q_in  = df["Inflow_BCM"].values
    Q_out = df["Outflow_BCM"].values
    E     = df.get("Evap_PM_BCM",
                   df.get("Evap_BCM", df["Volume_BCM"] * 0.001)).values
    # Derive Seepage_BCM if missing (same logic as compute_full_balance)
    if "Seepage_BCM" not in df.columns:
        if "Losses" in df.columns:
            df = df.copy()
            df["Seepage_BCM"] = (df["Losses"] - df.get("Evap_PM_BCM",
                pd.Series(0, index=df.index))).clip(lower=0)
        else:
            df = df.copy()
            df["Seepage_BCM"] = (df["Volume_BCM"] * 0.0045).clip(lower=0)
    S     = df["Seepage_BCM"].values
    V0    = float(df["Volume_BCM"].iloc[0])
    cap   = float(basin["cap"])

    for i in range(n_sim):
        e_q = rng.normal(1.0, sigma_q, n)
        e_e = rng.normal(1.0, sigma_e, n)
        e_s = rng.normal(1.0, sigma_s, n)

        vol = np.zeros(n)
        vol[0] = V0
        for t in range(1, n):
            dV = (Q_in[t] * e_q[t] - Q_out[t]
                  - E[t] * e_e[t] - S[t] * e_s[t])
            vol[t] = np.clip(vol[t-1] + dV, 0, cap)
        vols[i] = vol

    return {
        "p05": np.percentile(vols,  5, axis=0),
        "p25": np.percentile(vols, 25, axis=0),
        "p50": np.percentile(vols, 50, axis=0),
        "p75": np.percentile(vols, 75, axis=0),
        "p95": np.percentile(vols, 95, axis=0),
        "mean": vols.mean(axis=0),
        "std":  vols.std(axis=0),
        "n_sim": n_sim,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI — Scientific Enhancement Page
# ══════════════════════════════════════════════════════════════════════════════

def render_science_page(df: pd.DataFrame, basin: dict) -> None:
    """Full scientific enhancement UI — embed in any HSAE tab or page."""

    st.markdown("""
<style>
.sci-card{background:linear-gradient(135deg,#0d1117,#0c1a2e);
  border:2px solid #0ea5e9;border-radius:16px;padding:1.2rem 1.6rem;
  margin-bottom:1rem;box-shadow:0 8px 32px rgba(14,165,233,.18);}
.sci-card h3{color:#38bdf8;}
</style>""", unsafe_allow_html=True)

    st.markdown("""
<div class="sci-card">
  <h3>🔬 Scientific Enhancement Module</h3>
  <p style="color:#94a3b8;font-size:.85rem;">
    Sentinel-2 Water Mask &bull; Penman-Monteith ET &bull;
    Hydropower Generation &bull; Full Water Balance &bull;
    Monte Carlo Uncertainty
  </p>
</div>""", unsafe_allow_html=True)

    s1, s2, s3, s4 = st.tabs([
        "🛰 S2 Water Mask",
        "💧 Full Water Balance",
        "⚡ Power Generation",
        "🎲 Monte Carlo CI",
    ])

    # ── Tab S1: Sentinel-2 Water Mask ─────────────────────────────────────
    with s1:
        st.subheader("Sentinel-2 NDWI Water Mask — Interactive Map")
        st.info(
            "Water pixels (NDWI > 0.2) are shown as a semi-transparent blue "
            "overlay on the dark basemap. Connect GEE for live S2 imagery."
        )
        ndwi_col = None
        if "S2_NDWI" in df.columns:
            ndwi_col = df["S2_NDWI"]
        render_water_mask_map(basin, ndwi_series=ndwi_col)

        # NDWI time-series
        if "S2_NDWI" in df.columns:
            st.markdown("#### NDWI Time-Series — Surface Water Extent Change")
            fig_n = go.Figure()
            fig_n.add_trace(go.Scatter(
                x=df["Date"], y=df["S2_NDWI"],
                name="NDWI", line=dict(color="#38bdf8", width=2),
                fill="tozeroy", fillcolor="rgba(56,189,248,.12)",
            ))
            fig_n.add_hline(y=0.2, line_dash="dash",
                            line_color="#f59e0b",
                            annotation_text="Water threshold (0.2)")
            fig_n.update_layout(template="plotly_dark", height=350,
                                title="Sentinel-2 NDWI Time-Series")
            st.plotly_chart(fig_n, use_container_width=True)
        st.latex(r"\mathrm{NDWI} = \frac{B_{Green} - B_{NIR}}"
                 r"{B_{Green} + B_{NIR}}")

    # ── Tab S2: Full Water Balance ─────────────────────────────────────────
    with s2:
        st.subheader("Full 100% Water Balance — Penman-Monteith")

        c1, c2, c3, c4 = st.columns(4)
        with c1: T_C  = st.slider("Temp (°C)",  10.0, 45.0, 28.0, 0.5, key="pm_T")
        with c2: RH   = st.slider("RH (%)",     10,   100,  45,   1,   key="pm_RH")
        with c3: u2   = st.slider("Wind (m/s)", 0.5,  8.0,  2.5, 0.1,  key="pm_u2")
        with c4: Rs   = st.slider("Solar (MJ)", 5.0,  35.0, 22.0, 0.5, key="pm_Rs")

        df2 = compute_pm_evap_BCM(df.copy(), basin, T_C, RH, u2, Rs)
        df2 = add_power_to_df(df2, basin)
        df2 = compute_full_balance(df2, basin)

        # KPIs
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Avg ET₀",      f"{df2['ET0_mm_day'].mean():.2f} mm/d")
        k2.metric("Avg Evap",     f"{df2['Evap_PM_BCM'].mean():.4f} BCM")
        k3.metric("Avg Seepage",  f"{df2['Seepage_BCM'].mean():.4f} BCM")
        k4.metric("Avg Power",    f"{df2['Power_MW'].mean():.1f} MW")
        k5.metric("MB Error (PM)",f"{df2['MB_full_pct'].mean():.4f}%")

        # Stacked loss chart
        fig_wb = go.Figure()
        fig_wb.add_trace(go.Bar(x=df2["Date"], y=df2["Inflow_BCM"],
            name="Inflow", marker_color="#10b981"))
        fig_wb.add_trace(go.Bar(x=df2["Date"], y=-df2["Outflow_BCM"],
            name="Outflow", marker_color="#f59e0b"))
        fig_wb.add_trace(go.Bar(x=df2["Date"], y=-df2["Evap_PM_BCM"],
            name="Evap PM", marker_color="#ef4444"))
        fig_wb.add_trace(go.Bar(x=df2["Date"], y=-df2["Seepage_BCM"],
            name="Seepage", marker_color="#8b5cf6"))
        fig_wb.update_layout(
            template="plotly_dark", height=430, barmode="relative",
            title="Full Water Balance — Inflow vs Losses",
        )
        st.plotly_chart(fig_wb, use_container_width=True)

        st.latex(
            r"\Delta V = Q_{in} - Q_{out} - ET_0 \cdot A - S_{seep}"
        )
        st.latex(
            r"ET_0 = \frac{0.408\,\Delta(R_n-G) + \gamma\,\frac{900}{T+273}"
            r"\,u_2\,(e_s-e_a)}{\Delta + \gamma\,(1+0.34\,u_2)}"
        )

        st.download_button(
            "⬇ Download Full Balance CSV",
            df2[["Date","Inflow_BCM","Outflow_BCM",
                 "ET0_mm_day","Evap_PM_BCM","Seepage_BCM",
                 "Power_MW","MB_full_Error","MB_full_pct"]
               ].to_csv(index=False).encode(),
            "HSAE_FullBalance.csv", "text/csv",
            key="dl_full_balance",
        )

    # ── Tab S3: Power Generation ───────────────────────────────────────────
    with s3:
        st.subheader("Hydropower Generation  —  P = ρ·g·Q·H·η")
        eta_s = st.slider("Plant efficiency η", 0.70, 0.95, 0.88, 0.01,
                          key="eta_slider")
        H_s   = st.slider("Effective head H (m)",
                          10, int(max(basin.get("head",100)*1.5, 200)),
                          int(basin.get("head",100)), 1, key="head_slider")

        df3 = df.copy()
        df3["Power_MW"]  = compute_power_MW(df3["Outflow_BCM"].values,
                                             H_s, eta_s)
        df3["Energy_GWh"]= df3["Power_MW"] * 24 / 1000.0

        k1,k2,k3 = st.columns(3)
        k1.metric("Peak Power",   f"{df3['Power_MW'].max():.1f} MW")
        k2.metric("Avg Power",    f"{df3['Power_MW'].mean():.1f} MW")
        k3.metric("Total Energy", f"{df3['Energy_GWh'].sum():.0f} GWh")

        fig_pw = go.Figure()
        fig_pw.add_trace(go.Scatter(
            x=df3["Date"], y=df3["Power_MW"],
            name="Power (MW)", line=dict(color="#f59e0b", width=2.5),
            fill="tozeroy", fillcolor="rgba(245,158,11,.15)",
        ))
        fig_pw.update_layout(
            template="plotly_dark", height=400,
            title=f"Hydropower Output — {basin.get('id','')} "
                  f"(H={H_s}m, η={eta_s:.0%})",
        )
        st.plotly_chart(fig_pw, use_container_width=True)
        st.latex(r"P = \rho \cdot g \cdot Q \cdot H \cdot \eta \quad [W]")
        st.caption(
            f"ρ = {RHO_WATER} kg/m³ | g = {G_ACC} m/s² | "
            f"Q in m³/s | H = {H_s} m | η = {eta_s:.0%}"
        )

    # ── Tab S4: Monte Carlo CI ─────────────────────────────────────────────
    with s4:
        st.subheader("Monte Carlo Uncertainty Quantification")
        st.latex(
            r"\hat{V}_{t+1} = V_t + \tilde{Q}_{in} - Q_{out}"
            r"- \tilde{E} - \tilde{S}"
        )
        st.caption(
            r"Each ~Q, ~E, ~S drawn from N(μ, σ) to propagate input uncertainty."
        )

        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1: n_sim   = st.select_slider("Simulations",
                                [100,500,1000,2000,5000], 1000, key="mc_nsim")
        with mc2: sig_q   = st.slider("σ Inflow",  0.02, 0.20, 0.05, 0.01, key="mc_sq")
        with mc3: sig_e   = st.slider("σ Evap",    0.05, 0.30, 0.10, 0.01, key="mc_se")
        with mc4: sig_s   = st.slider("σ Seepage", 0.05, 0.30, 0.15, 0.01, key="mc_ss")

        with st.spinner(f"Running {n_sim:,} Monte Carlo simulations …"):
            mc = monte_carlo_balance(
                df2 if "Evap_PM_BCM" in df2.columns else df,
                basin, n_sim=n_sim,
                sigma_q=sig_q, sigma_e=sig_e, sigma_s=sig_s,
            )

        fig_mc = go.Figure()
        dates  = df["Date"]

        # 90% CI band
        fig_mc.add_trace(go.Scatter(
            x=dates, y=mc["p95"], name="P95",
            line=dict(color="rgba(56,189,248,0)"),
            showlegend=False,
        ))
        fig_mc.add_trace(go.Scatter(
            x=dates, y=mc["p05"],
            fill="tonexty", fillcolor="rgba(56,189,248,.12)",
            line=dict(color="rgba(56,189,248,0)"),
            name="90% Confidence Band",
        ))
        # 50% CI band
        fig_mc.add_trace(go.Scatter(
            x=dates, y=mc["p75"], name="P75",
            line=dict(color="rgba(99,102,241,0)"),
            showlegend=False,
        ))
        fig_mc.add_trace(go.Scatter(
            x=dates, y=mc["p25"],
            fill="tonexty", fillcolor="rgba(99,102,241,.20)",
            line=dict(color="rgba(99,102,241,0)"),
            name="50% Confidence Band",
        ))
        # Median & observed
        fig_mc.add_trace(go.Scatter(
            x=dates, y=mc["p50"], name="Median (Monte Carlo)",
            line=dict(color="#6366f1", width=2.5),
        ))
        fig_mc.add_trace(go.Scatter(
            x=dates, y=df["Volume_BCM"], name="Observed Volume",
            line=dict(color="#10b981", width=2.5, dash="dot"),
        ))

        fig_mc.update_layout(
            template="plotly_dark", height=460,
            title=f"Monte Carlo Volume Uncertainty (n={n_sim:,})",
            yaxis_title="Volume (BCM)",
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        # Stats
        st.markdown("### Uncertainty Statistics")
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Mean Spread (P5-P95)",
                   f"{(mc['p95']-mc['p05']).mean():.3f} BCM")
        sc2.metric("Mean Std Dev",
                   f"{mc['std'].mean():.4f} BCM")
        sc3.metric("Max Uncertainty",
                   f"{(mc['p95']-mc['p05']).max():.3f} BCM")
