# hsae_groundwater.py  –  HSAE Groundwater & Irrigation Demand Module
# ═══════════════════════════════════════════════════════════════════════════════
# Closes Gap #4: "نمذجة الحوض الكاملة"
#
# Components:
#   1. MODFLOW-inspired conceptual groundwater model (2-zone)
#   2. Irrigation demand (FAO-56 crop water requirement)
#   3. Urban water demand (population × per-capita use)
#   4. Flood routing (Muskingum method)
#   5. Groundwater–surface water interaction
#   6. Integrated demand vs supply dashboard
#   7. Legal output: groundwater depletion as Art. 5/7 evidence
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
# 1. GROUNDWATER MODEL (2-zone conceptual)
# ══════════════════════════════════════════════════════════════════════════════

def run_groundwater_model(
    recharge_mm:    np.ndarray,   # daily recharge from soil zone [mm/day]
    pumping_mm:     np.ndarray,   # daily abstraction [mm/day]
    area_km2:       float,        # aquifer area
    Sy:             float = 0.15, # specific yield (unconfined)
    K_drain:        float = 0.005,# drainage coefficient to river [1/day]
    GW0_mm:         float = 200.0,# initial groundwater storage [mm]
) -> pd.DataFrame:
    """
    2-zone conceptual groundwater model.
    Zone 1: shallow unconfined aquifer (recharge + pumping)
    Zone 2: deep confined aquifer (slow drainage)
    """
    n   = len(recharge_mm)
    mm2BCM = area_km2 * 1e-6

    gw1   = np.zeros(n)   # shallow aquifer storage [mm]
    gw2   = np.zeros(n)   # deep aquifer storage [mm]
    Q_gw  = np.zeros(n)   # groundwater contribution to stream [BCM/day]
    depl  = np.zeros(n)   # cumulative depletion [mm]

    gw1_state = GW0_mm
    gw2_state = GW0_mm * 0.5
    cum_depl  = 0.0

    for t in range(n):
        R = max(recharge_mm[t], 0)
        P = max(pumping_mm[t], 0)

        # Shallow aquifer balance
        gw1_new  = gw1_state + R - P
        # Percolation to deep zone
        perc     = max(0, gw1_new - GW0_mm * 1.5) * 0.1
        gw1_new -= perc
        # Drainage to river
        drain    = K_drain * max(gw1_new, 0)
        gw1_new -= drain
        gw1_new  = max(gw1_new, 0)

        # Deep aquifer
        gw2_state += perc - K_drain * 0.1 * gw2_state

        # Cumulative depletion (when pumping > recharge)
        if P > R:
            cum_depl += (P - R)

        Q_gw[t]     = drain * mm2BCM
        gw1[t]      = gw1_new
        gw2[t]      = gw2_state
        depl[t]     = cum_depl
        gw1_state   = gw1_new

    return pd.DataFrame({
        "GW_shallow_mm":  gw1,
        "GW_deep_mm":     gw2,
        "Q_gw_BCM":       Q_gw,
        "GW_depletion_mm":depl,
    })


# ══════════════════════════════════════════════════════════════════════════════
# 2. FAO-56 IRRIGATION DEMAND
# ══════════════════════════════════════════════════════════════════════════════

# Crop coefficients (Kc) for major crops by growth stage
CROP_KC = {
    "Wheat":   {"initial":0.30,"mid":1.15,"late":0.40,"season_days":150},
    "Cotton":  {"initial":0.35,"mid":1.20,"late":0.50,"season_days":180},
    "Sorghum": {"initial":0.30,"mid":1.00,"late":0.55,"season_days":130},
    "Rice":    {"initial":1.05,"mid":1.20,"late":0.90,"season_days":150},
    "Sugarcane":{"initial":0.40,"mid":1.25,"late":0.75,"season_days":365},
    "Maize":   {"initial":0.30,"mid":1.20,"late":0.50,"season_days":125},
}

def compute_irrigation_demand(
    et0_mm:      np.ndarray,   # reference ET [mm/day]
    rain_mm:     np.ndarray,   # effective rainfall [mm/day]
    irrigated_ha:float,        # irrigated area [ha]
    crop:        str   = "Wheat",
    efficiency:  float = 0.65,  # irrigation efficiency
) -> np.ndarray:
    """
    FAO-56 crop water requirement → net irrigation demand.
    Returns demand in BCM/day.
    """
    n = len(et0_mm)
    kc_data = CROP_KC.get(crop, CROP_KC["Wheat"])

    season = kc_data["season_days"]
    Kc_arr = np.zeros(n)
    for t in range(n):
        frac = (t % season) / season
        if frac < 0.2:
            Kc_arr[t] = kc_data["initial"]
        elif frac < 0.7:
            Kc_arr[t] = kc_data["mid"]
        else:
            Kc_arr[t] = kc_data["late"]

    ETc = et0_mm * Kc_arr                      # crop ET [mm/day]
    eff_rain = np.minimum(rain_mm * 0.75, ETc)  # effective rainfall
    NIR = np.maximum(0, ETc - eff_rain)         # net irrigation req [mm/day]
    GIR = NIR / efficiency                      # gross irrigation req [mm/day]

    # Convert mm/day × ha → BCM/day  (1 mm × 1 ha = 10 m³ = 1e-8 BCM)
    demand_BCM = GIR * irrigated_ha * 1e-8
    return demand_BCM


# ══════════════════════════════════════════════════════════════════════════════
# 3. URBAN WATER DEMAND
# ══════════════════════════════════════════════════════════════════════════════

def compute_urban_demand(
    population:      float,       # total population
    per_capita_L_day:float = 150, # L/person/day (WHO minimum = 50)
    growth_rate:     float = 0.025,# annual population growth
    n_days:          int   = 365,
) -> np.ndarray:
    """
    Urban water demand [BCM/day] with population growth.
    """
    days_arr = np.arange(n_days)
    pop      = population * (1 + growth_rate) ** (days_arr / 365)
    demand   = pop * per_capita_L_day * 1e-3 / 1e9   # L→m³→BCM
    return demand


# ══════════════════════════════════════════════════════════════════════════════
# 4. MUSKINGUM FLOOD ROUTING
# ══════════════════════════════════════════════════════════════════════════════

def muskingum_routing(
    inflow:  np.ndarray,
    K:       float = 1.0,   # storage time constant [days]
    X:       float = 0.2,   # weighting factor [0–0.5]
    dt:      float = 1.0,   # time step [days]
) -> np.ndarray:
    """
    Muskingum channel routing.
    Translates and attenuates flood wave from upstream to dam inlet.
    """
    C0 = (dt - 2*K*X) / (2*K*(1-X) + dt)
    C1 = (dt + 2*K*X) / (2*K*(1-X) + dt)
    C2 = (2*K*(1-X) - dt) / (2*K*(1-X) + dt)

    # Clip C values to ensure stability
    C0 = max(0, min(1, C0))
    C1 = max(0, min(1, C1))
    C2 = max(0, min(1, C2))

    outflow    = np.zeros_like(inflow)
    outflow[0] = inflow[0]
    for t in range(1, len(inflow)):
        outflow[t] = C0*inflow[t] + C1*inflow[t-1] + C2*outflow[t-1]
    return np.maximum(0, outflow)


# ══════════════════════════════════════════════════════════════════════════════
# 5. FULL DEMAND-SUPPLY BALANCE
# ══════════════════════════════════════════════════════════════════════════════

def compute_full_demand(
    basin:     dict,
    df_sim:    pd.DataFrame,
    irr_ha:    float,
    population:float,
    crop:      str,
    irr_eff:   float,
) -> pd.DataFrame:
    """
    Integrate all demand components with groundwater and flood routing.
    """
    n    = len(df_sim)
    seed = abs(hash(basin.get("id","X"))) % (2**31) + 5
    rng  = np.random.default_rng(seed)

    # ET0 proxy
    lat_rad = abs(basin.get("lat",15)) * np.pi / 180
    doy = np.array([d.timetuple().tm_yday
                    for d in pd.to_datetime(df_sim["Date"])])
    T_arr  = 25 + 5*np.sin(2*np.pi*doy/365)
    Rn_prx = 15 + 8*np.cos(2*np.pi*(doy-172)/365)
    et0_mm = np.clip(0.0023*(T_arr+17.8)*np.sqrt(max(1,T_arr.std()+4))*Rn_prx, 0, 14)

    rain_mm = df_sim["GPM_Rain_mm"].values if "GPM_Rain_mm" in df_sim else rng.gamma(1.5,4,n)

    # Irrigation demand
    irr_dem = compute_irrigation_demand(et0_mm, rain_mm, irr_ha, crop, irr_eff)

    # Urban demand
    urb_dem = compute_urban_demand(population, n_days=n)
    urb_dem = urb_dem[:n]

    # Environmental flow (minimum 10% of mean inflow — Art. 20)
    inflow   = df_sim["Inflow_BCM"].values if "Inflow_BCM" in df_sim else rng.gamma(1,0.1,n)
    env_flow = np.full(n, inflow.mean() * 0.10)

    # Total demand
    total_demand = irr_dem + urb_dem + env_flow

    # Supply available (outflow)
    supply = df_sim["Outflow_BCM"].values if "Outflow_BCM" in df_sim else inflow*0.8

    # Deficit
    deficit = np.maximum(0, total_demand - supply)
    surplus = np.maximum(0, supply - total_demand)

    # Groundwater model
    recharge = rain_mm * basin.get("eff_cat_km2",100000) * 0.05 * 1e6/1e9 * 1000  # mm proxy
    pumping  = irr_dem * 1e9 / (basin.get("eff_cat_km2",100000)*1e6) * 1000       # mm proxy
    recharge = np.minimum(recharge, 20)
    pumping  = np.minimum(pumping,  15)

    gw_df = run_groundwater_model(recharge, pumping, basin.get("eff_cat_km2",100000))

    # Muskingum flood routing (K=2 days typical for large basins)
    routed_inflow = muskingum_routing(inflow, K=2.0, X=0.2)

    result = pd.DataFrame({
        "Date":            pd.to_datetime(df_sim["Date"]),
        "ET0_mm":          et0_mm,
        "Irr_Demand_BCM":  irr_dem,
        "Urban_Demand_BCM":urb_dem,
        "EnvFlow_BCM":     env_flow,
        "Total_Demand_BCM":total_demand,
        "Supply_BCM":      supply,
        "Deficit_BCM":     deficit,
        "Surplus_BCM":     surplus,
        "Deficit_pct":     deficit / (total_demand + 1e-9) * 100,
        "Routed_Inflow_BCM":routed_inflow,
    })

    # Merge groundwater
    for col in gw_df.columns:
        result[col] = gw_df[col].values[:n]

    return result


# ══════════════════════════════════════════════════════════════════════════════
# 6. STREAMLIT PAGE
# ══════════════════════════════════════════════════════════════════════════════

def render_groundwater_page(df_sim: pd.DataFrame | None, basin: dict) -> None:

    st.markdown("""
<style>
.gw-card {
    background:linear-gradient(135deg,#0f172a,#0a1628);
    border:2px solid #6366f1;border-radius:16px;
    padding:1.2rem;box-shadow:0 10px 40px rgba(99,102,241,0.2);
}
</style>
""", unsafe_allow_html=True)

    basin_id = basin.get("id","—")
    st.markdown(f"""
<div class='gw-card'>
  <h1 style='color:#818cf8;font-family:Orbitron;text-align:center;font-size:1.9rem;margin:0;'>
    💧 Groundwater, Irrigation & Flood Routing
  </h1>
  <p style='text-align:center;color:#94a3b8;font-family:Orbitron;font-size:0.75rem;
            letter-spacing:2px;margin:0.4rem 0 0;'>
    FAO-56  ·  MODFLOW CONCEPTUAL  ·  MUSKINGUM ROUTING  ·  ART. 20 ENV. FLOW
  </p>
  <hr style='border-color:#6366f1;margin:0.6rem 0;'>
  <p style='text-align:center;color:#e2e8f0;margin:0;'>
    🎯 <b style='color:#a5b4fc;'>{basin_id}</b>  ·  {basin.get("river","—")}
    &nbsp;|&nbsp; Catchment: <b>{basin.get("eff_cat_km2",0):,.0f} km²</b>
  </p>
</div>
""", unsafe_allow_html=True)

    if df_sim is None:
        st.warning("⚠️ Run the **v430 engine** first to generate simulation data.")
        return

    # ── Sidebar controls ─────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 💧 Demand Parameters")
        irr_ha    = st.number_input("Irrigated Area (ha)",     0, 5_000_000, 500_000, 10_000, key="gw_ha")
        population= st.number_input("Downstream Population",   0, 200_000_000, 10_000_000, 100_000, key="gw_pop")
        crop      = st.selectbox("Primary Crop", list(CROP_KC.keys()), key="gw_crop")
        irr_eff   = st.slider("Irrigation Efficiency", 0.3, 0.95, 0.65, 0.05, key="gw_eff")
        st.markdown("### 🌊 Groundwater")
        Sy        = st.slider("Specific Yield (Sy)", 0.05, 0.35, 0.15, 0.01, key="gw_Sy")
        K_drain   = st.slider("Drainage Coefficient", 0.001, 0.05, 0.005, 0.001, key="gw_Kd")
        st.markdown("### 🌊 Muskingum Routing")
        musk_K    = st.slider("K (travel time, days)", 0.5, 5.0, 2.0, 0.5, key="gw_K")
        musk_X    = st.slider("X (attenuation)",       0.0, 0.5, 0.2, 0.05, key="gw_X")

    with st.spinner("Computing demand-supply balance…"):
        df_gw = compute_full_demand(basin, df_sim, irr_ha, population, crop, irr_eff)

    tabs = st.tabs([
        "💧 Demand vs Supply",
        "🌱 Irrigation Demand",
        "🌍 Groundwater",
        "🌊 Flood Routing",
        "⚖️ Legal: Art. 20",
        "📥 Export",
    ])

    # ── Tab 1: Demand vs Supply ───────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Total Demand vs Available Supply")

        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Avg Irrigation Demand",f"{df_gw['Irr_Demand_BCM'].mean()*1000:.3f} MCM/d")
        k2.metric("Avg Urban Demand",     f"{df_gw['Urban_Demand_BCM'].mean()*1000:.3f} MCM/d")
        k3.metric("Avg Env. Flow Req.",   f"{df_gw['EnvFlow_BCM'].mean()*1000:.3f} MCM/d")
        k4.metric("Avg Total Demand",     f"{df_gw['Total_Demand_BCM'].mean()*1000:.3f} MCM/d")
        k5.metric("Deficit Days",         f"{int((df_gw['Deficit_BCM']>0).sum()):,}")

        fig_ds = go.Figure()
        fig_ds.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["Supply_BCM"]*1000,
            name="Available Supply (MCM/d)", fill="tozeroy",
            line=dict(color="#10b981",width=2),
            fillcolor="rgba(16,185,129,0.12)"
        ))
        fig_ds.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["Total_Demand_BCM"]*1000,
            name="Total Demand (MCM/d)",
            line=dict(color="#ef4444",width=2.5)
        ))
        fig_ds.add_trace(go.Bar(
            x=df_gw["Date"], y=df_gw["Deficit_BCM"]*1000,
            name="Deficit (MCM/d)", marker_color="rgba(239,68,68,0.4)"
        ))
        fig_ds.update_layout(
            template="plotly_dark", height=460,
            title=f"Demand–Supply Balance — {basin_id}",
            yaxis_title="MCM/day"
        )
        st.plotly_chart(fig_ds, use_container_width=True)

        # Annual summary
        df_gw["Year"] = pd.to_datetime(df_gw["Date"]).dt.year
        annual = df_gw.groupby("Year").agg(
            Supply_BCM  =("Supply_BCM","sum"),
            Demand_BCM  =("Total_Demand_BCM","sum"),
            Deficit_BCM =("Deficit_BCM","sum"),
        ).reset_index()
        fig_ann = go.Figure()
        fig_ann.add_trace(go.Bar(x=annual["Year"], y=annual["Supply_BCM"],  name="Supply",  marker_color="#10b981"))
        fig_ann.add_trace(go.Bar(x=annual["Year"], y=annual["Demand_BCM"],  name="Demand",  marker_color="#f59e0b"))
        fig_ann.add_trace(go.Bar(x=annual["Year"], y=annual["Deficit_BCM"], name="Deficit", marker_color="#ef4444"))
        fig_ann.update_layout(template="plotly_dark",height=320,barmode="group",
                               title="Annual Water Balance",yaxis_title="BCM/year")
        st.plotly_chart(fig_ann, use_container_width=True)

    # ── Tab 2: Irrigation ────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader(f"FAO-56 Irrigation Demand — {crop}")

        fig_irr = make_subplots(rows=2,cols=1,shared_xaxes=True,
                                subplot_titles=["ET₀ (mm/day)","Irrigation Demand (MCM/day)"])
        fig_irr.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["ET0_mm"],
            name="ET₀",line=dict(color="#f59e0b")), row=1,col=1)
        fig_irr.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["Irr_Demand_BCM"]*1000,
            name="Irr. Demand",line=dict(color="#3b82f6"),
            fill="tozeroy",fillcolor="rgba(59,130,246,0.12)"), row=2,col=1)
        fig_irr.update_layout(template="plotly_dark",height=500)
        st.plotly_chart(fig_irr, use_container_width=True)

        # Crop Kc reference
        st.markdown("#### 🌾 Crop Coefficients Reference")
        kc_data = pd.DataFrame([
            {"Crop":c,"Kc_initial":v["initial"],"Kc_mid":v["mid"],
             "Kc_late":v["late"],"Season_days":v["season_days"]}
            for c,v in CROP_KC.items()
        ])
        st.dataframe(kc_data, use_container_width=True, hide_index=True)
        st.caption("Source: FAO Irrigation and Drainage Paper No. 56 (Allen et al., 1998)")

    # ── Tab 3: Groundwater ────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Conceptual Groundwater Model")

        fig_gw = make_subplots(rows=3,cols=1,shared_xaxes=True,
                               subplot_titles=["Shallow Aquifer (mm)",
                                               "Groundwater → Stream (BCM/day)",
                                               "Cumulative Depletion (mm)"])
        fig_gw.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["GW_shallow_mm"],
            name="Shallow GW",line=dict(color="#6366f1",width=2),
            fill="tozeroy",fillcolor="rgba(99,102,241,0.12)"), row=1,col=1)
        fig_gw.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["Q_gw_BCM"]*1000,
            name="GW→Stream",line=dict(color="#22d3ee")), row=2,col=1)
        fig_gw.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["GW_depletion_mm"],
            name="Cumul. Depletion",line=dict(color="#f97316"),
            fill="tozeroy",fillcolor="rgba(249,115,22,0.12)"), row=3,col=1)
        fig_gw.update_layout(template="plotly_dark",height=600,
                              title=f"Groundwater Dynamics — {basin_id}")
        st.plotly_chart(fig_gw, use_container_width=True)

        depl_total = float(df_gw["GW_depletion_mm"].iloc[-1])
        gw_contrib = float(df_gw["Q_gw_BCM"].sum())
        c1,c2 = st.columns(2)
        c1.metric("Total Groundwater Depletion",f"{depl_total:.1f} mm",
                  "⚠️ Overuse" if depl_total > 100 else "✅ Sustainable")
        c2.metric("Total GW contribution to stream",f"{gw_contrib:.3f} BCM")

    # ── Tab 4: Flood Routing ─────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Muskingum Flood Routing")
        st.info(
            "Muskingum routing translates the upstream flood wave to the dam inlet, "
            "accounting for travel time (K) and attenuation (X). "
            "This is critical for **early warning** — the routed flood peak arrives "
            f"approximately {musk_K:.1f} days after the upstream rainfall event."
        )

        fig_rout = go.Figure()
        fig_rout.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_sim["Inflow_BCM"].values,
            name="Raw Inflow (at source)",
            line=dict(color="#3b82f6",width=2)
        ))
        fig_rout.add_trace(go.Scatter(
            x=df_gw["Date"], y=df_gw["Routed_Inflow_BCM"],
            name=f"Routed Inflow (K={musk_K}d)",
            line=dict(color="#f59e0b",width=2.5,dash="dot")
        ))
        fig_rout.update_layout(
            template="plotly_dark",height=400,
            title=f"Muskingum Flood Routing — K={musk_K}d, X={musk_X}",
            yaxis_title="Inflow (BCM/day)"
        )
        st.plotly_chart(fig_rout, use_container_width=True)

        peak_raw   = float(df_sim["Inflow_BCM"].max())
        peak_rout  = float(df_gw["Routed_Inflow_BCM"].max())
        attenuation = (peak_raw - peak_rout) / (peak_raw + 1e-9) * 100
        c1,c2,c3 = st.columns(3)
        c1.metric("Peak Raw Inflow",   f"{peak_raw:.4f} BCM/d")
        c2.metric("Peak Routed",       f"{peak_rout:.4f} BCM/d")
        c3.metric("Peak Attenuation",  f"{attenuation:.1f}%")

    # ── Tab 5: Legal Art. 20 ─────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("⚖️ Legal: Article 20 — Ecosystem Protection")
        st.markdown("""
**Article 20** of the UN 1997 Watercourses Convention requires watercourse states to
protect and preserve the ecosystems of international watercourses.

This module quantifies three key environmental obligations:
- **Minimum Environmental Flow** (10% of mean annual flow — Brisbane Declaration)
- **Groundwater depletion** (irreversible ecosystem damage)
- **Demand-supply deficit** (downstream communities deprived of water)
""")

        env_compliance = float((df_gw["Supply_BCM"] >= df_gw["EnvFlow_BCM"]).mean() * 100)
        gw_depl_final  = float(df_gw["GW_depletion_mm"].iloc[-1])
        deficit_days   = int((df_gw["Deficit_BCM"] > 0).sum())
        total_days     = len(df_gw)

        # Art 20 compliance dashboard
        a1,a2,a3 = st.columns(3)
        a1.markdown(
            f"<div style='background:#0f172a;border:2px solid "
            f"{'#10b981' if env_compliance>80 else '#dc2626'};border-radius:12px;"
            f"padding:1rem;text-align:center;'>"
            f"<b style='color:#94a3b8;'>Environmental Flow Compliance</b>"
            f"<div style='font-size:2rem;font-weight:900;"
            f"color:{'#10b981' if env_compliance>80 else '#dc2626'};'>"
            f"{env_compliance:.1f}%</div>"
            f"<small style='color:#64748b;'>Art. 20 — Brisbane Declaration</small>"
            f"</div>", unsafe_allow_html=True
        )
        a2.markdown(
            f"<div style='background:#0f172a;border:2px solid "
            f"{'#10b981' if gw_depl_final<50 else '#dc2626'};border-radius:12px;"
            f"padding:1rem;text-align:center;'>"
            f"<b style='color:#94a3b8;'>Groundwater Depletion</b>"
            f"<div style='font-size:2rem;font-weight:900;"
            f"color:{'#10b981' if gw_depl_final<50 else '#f97316'};'>"
            f"{gw_depl_final:.1f} mm</div>"
            f"<small style='color:#64748b;'>Cumulative overuse</small>"
            f"</div>", unsafe_allow_html=True
        )
        a3.markdown(
            f"<div style='background:#0f172a;border:2px solid "
            f"{'#10b981' if deficit_days<30 else '#dc2626'};border-radius:12px;"
            f"padding:1rem;text-align:center;'>"
            f"<b style='color:#94a3b8;'>Deficit Days (of {total_days})</b>"
            f"<div style='font-size:2rem;font-weight:900;"
            f"color:{'#10b981' if deficit_days<30 else '#dc2626'};'>"
            f"{deficit_days:,}</div>"
            f"<small style='color:#64748b;'>Art. 5 / Art. 20 concern</small>"
            f"</div>", unsafe_allow_html=True
        )

        st.markdown("---")
        # Legal assessment
        issues = []
        if env_compliance < 80:
            issues.append(
                f"🚨 **Art. 20 Violation**: Environmental flow compliance {env_compliance:.1f}% "
                f"< 80% requirement. Minimum flow not maintained for {int(total_days*(1-env_compliance/100)):,} days."
            )
        if gw_depl_final > 100:
            issues.append(
                f"🚨 **Art. 20 Violation**: Groundwater depletion {gw_depl_final:.1f} mm "
                "indicates irreversible aquifer damage — ecosystem harm under Art. 20."
            )
        if deficit_days > 90:
            issues.append(
                f"⚠️ **Art. 5 Concern**: Water demand deficit on {deficit_days:,} days "
                "indicates downstream communities deprived of equitable share."
            )
        if not issues:
            st.success("✅ All Art. 20 ecosystem protection indicators within acceptable range.")
        else:
            for issue in issues:
                st.error(issue)

    # ── Tab 6: Export ────────────────────────────────────────────────────────
    with tabs[5]:
        c1,c2 = st.columns(2)
        c1.download_button(
            "📊 Demand-Supply CSV",
            df_gw.to_csv(index=False).encode("utf-8"),
            file_name=f"HSAE_GW_{basin_id}.csv",
            mime="text/csv",
        )
        # Build Art.20 report
        report = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>HSAE Art. 20 Groundwater Report — {basin_id}</title>
<style>body{{font-family:Arial;margin:30px;}} h1{{color:#0f766e;}}
table{{border-collapse:collapse;width:70%;}} th,td{{border:1px solid #cbd5e1;padding:8px;}}
th{{background:#1e3a5f;color:#fff;}}</style>
</head><body>
<h1>Groundwater & Environmental Flow Report</h1>
<p><b>Basin:</b> {basin_id} — {basin.get("river","—")}<br>
   <b>Period:</b> {df_gw["Date"].iloc[0].date()} → {df_gw["Date"].iloc[-1].date()}<br>
   <b>Irrigated Area:</b> {irr_ha:,.0f} ha  |  <b>Population:</b> {population:,.0f}<br>
   <b>Primary Crop:</b> {crop}  |  <b>Irrigation Efficiency:</b> {irr_eff:.0%}</p>
<h2>Key Indicators</h2>
<table>
<tr><th>Indicator</th><th>Value</th><th>Threshold</th><th>Art.</th><th>Status</th></tr>
<tr><td>Env. Flow Compliance</td><td>{env_compliance:.1f}%</td><td>80%</td>
    <td>Art. 20</td><td>{"✅" if env_compliance>=80 else "🚨"}</td></tr>
<tr><td>GW Depletion</td><td>{gw_depl_final:.1f} mm</td><td>&lt;100 mm</td>
    <td>Art. 20</td><td>{"✅" if gw_depl_final<100 else "🚨"}</td></tr>
<tr><td>Deficit Days</td><td>{deficit_days}</td><td>&lt;30 days/yr</td>
    <td>Art. 5</td><td>{"✅" if deficit_days<30 else "⚠️"}</td></tr>
</table>
<p>Report generated: {datetime.utcnow().strftime("%d %B %Y %H:%M UTC")}</p>
</body></html>"""
        c2.download_button(
            "📄 Art. 20 HTML Report",
            report.encode("utf-8"),
            file_name=f"HSAE_Art20_{basin_id}.html",
            mime="text/html",
        )
