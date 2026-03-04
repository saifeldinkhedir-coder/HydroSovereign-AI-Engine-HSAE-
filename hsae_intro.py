# hsae_intro.py  –  HSAE v500 Complete  Introduction & Architecture Page
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st


def intro_page():

    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');

.hero {
    background: linear-gradient(135deg,#020617 0%,#0a1628 40%,#0c1a14 100%);
    border: 3px solid #10b981;
    border-radius: 24px; padding: 3rem 2.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 30px 80px rgba(16,185,129,0.35), 0 0 120px rgba(59,130,246,0.1);
    position:relative; overflow:hidden; text-align:center;
}
.hero::before {
    content:''; position:absolute; top:0; left:0; right:0; height:4px;
    background:linear-gradient(90deg,#10b981,#3b82f6,#f59e0b,#ef4444,#10b981);
}
.hero-title {
    font-family:'Orbitron',sans-serif; font-size:2.8rem; color:#10b981;
    font-weight:900; letter-spacing:4px; margin:0;
}
.hero-sub {
    font-family:'Orbitron',sans-serif; font-size:0.9rem; color:#94a3b8;
    letter-spacing:3px; margin:0.5rem 0 0;
}
.hero-badge {
    display:inline-block; background:#064e3b; border:1px solid #10b981;
    border-radius:20px; padding:4px 16px; font-size:0.75rem;
    color:#6ee7b7; margin:0.4rem 4px;
}
.mod-card {
    background:linear-gradient(135deg,#0f172a,#0a1a10);
    border:1px solid; border-radius:14px; padding:1rem 1.2rem;
    height:100%; transition: transform 0.2s, box-shadow 0.2s;
}
.mod-card:hover { transform:translateY(-3px); }
.phase-block {
    background:#0f172a; border-radius:12px;
    border-left:4px solid; padding:1rem 1.5rem; margin:0.6rem 0;
}
.stat-box {
    background:linear-gradient(135deg,#0f172a,#0a1628);
    border-radius:10px; border:1px solid #1e293b;
    padding:0.9rem; text-align:center;
}
</style>
""", unsafe_allow_html=True)

    # ── HERO ─────────────────────────────────────────────────────────────────
    st.markdown("""
<div class='hero'>
  <div style='margin-bottom:0.8rem;'>
    <span class='hero-badge'>v5.0.0 Phase III Complete</span>
    <span class='hero-badge'>25 Global Basins</span>
    <span class='hero-badge'>13 Modules</span>
    <span class='hero-badge'>UN 1997 Art. 5–21</span>
    <span class='hero-badge'>Bergström HBV</span>
  </div>
  <div class='hero-title'>⚡ HydroSovereign AI Engine</div>
  <div style='font-family:Orbitron;font-size:1.1rem;color:#34d399;margin:0.5rem 0;'>HSAE</div>
  <div class='hero-sub'>TRANSBOUNDARY WATER SOVEREIGNTY · AI-POWERED · LEGALLY GROUNDED</div>
  <hr style='border-color:#10b981;margin:1rem auto;width:60%;opacity:0.4;'>
  <p style='color:#cbd5e1;font-size:1rem;margin:0;max-width:800px;margin:0 auto;'>
    The world's first open-source AI system combining satellite hydrology,
    conceptual rainfall-runoff modelling, and international water law automation
    into a single sovereign intelligence platform.
  </p>
  <p style='color:#94a3b8;font-size:0.85rem;margin:0.8rem 0 0;font-style:italic;'>
    Seifeldin M. G. Alkedir · M.Sc. Environmental Sciences · Institute of Environmental Studies · University of Khartoum
  </p>
  <p style='margin:0.6rem 0 0;font-size:0.78rem;'>
    <span style='color:#64748b;font-style:italic;'>Independent Researcher · </span>
    <a href='https://www.findaphd.com/phds/?Keywords=hydrology+environmental+engineering+data+science+water+policy'
       target='_blank'
       style='color:#10b981;text-decoration:none;font-style:italic;
              border-bottom:1px dashed #10b98188;padding-bottom:1px;'>
      Seeking PhD Scholarship or Position in Hydrology · Environmental Engineering · Data Science · Water Policy
    </a>
  </p>
</div>
""", unsafe_allow_html=True)

    # ── STAT ROW ─────────────────────────────────────────────────────────────
    stats = [
        ("7,517+", "Lines of Code",      "#10b981"),
        ("13",     "Functional Modules",  "#3b82f6"),
        ("25",     "Global Basins",       "#f59e0b"),
        ("12",     "UN 1997 Articles",    "#ef4444"),
        ("6",      "Data Sources",        "#a78bfa"),
        ("5",      "RBAC Roles",          "#06b6d4"),
    ]
    cols = st.columns(6)
    for col, (val, lbl, color) in zip(cols, stats):
        col.markdown(
            f"<div class='stat-box' style='border-color:{color}22;'>"
            f"<div style='color:{color};font-size:2rem;font-weight:900;"
            f"font-family:Orbitron;'>{val}</div>"
            f"<div style='color:#94a3b8;font-size:0.72rem;margin:0.2rem 0;'>{lbl}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── MODULE GRID ───────────────────────────────────────────────────────────
    st.markdown("## 🗂️ Module Architecture")

    modules = [
        # (emoji, name, description, color, phase)
        ("🌐","v430 · Hybrid DSS",
         "Sentinel-1 SAR + Sentinel-2 NDWI + GPM IMERG · AI forecast (Random Forest) · "
         "Penman evaporation · Forensics · Cloud masking · Global benchmark",
         "#10b981","I"),
        ("⚖️","v990 · Legal Nexus",
         "UN 1997 Art. 5–21 live indicators · MODIS ET enrichment · TDI forensic index · "
         "Sediment & water quality proxies · Art. 20/21 compliance · Nexus: Water–Food–Climate",
         "#3b82f6","I"),
        ("🔬","Science · Water Balance",
         "Penman-Monteith PET · Monte Carlo uncertainty · Power generation · "
         "Hydrological lag analysis · Penman open-water · Mass balance closure",
         "#06b6d4","I"),
        ("📜","Legal · Treaty Engine",
         "ICJ/PCA/ITLOS precedents database · Treaty compliance checker · "
         "Auto-protest generator · Bilingual legal reports (EN/AR) · Art. 9 data exchange",
         "#f59e0b","I"),
        ("🛠️","DevOps · CI/CD",
         "PostgreSQL+PostGIS schema · FastAPI REST router · Docker Compose · "
         "GitHub Actions CI/CD · PyPI auto-publish · requirements.txt",
         "#8b5cf6","I"),
        ("📊","Validation · GRDC",
         "GRDC-compatible CSV ingestion · NSE / KGE / RMSE / R² / PBIAS · "
         "Taylor Diagram · Flow Duration Curve · Seasonal anomaly · Moriasi 2007",
         "#22c55e","II"),
        ("🚨","Alerts · Telegram",
         "Multi-level alerts: INFO/WARNING/CRITICAL/LEGAL · Telegram Bot dispatch · "
         "Auto-Protest Art. 12 (bilingual) · Scheduler simulation · Config export",
         "#ef4444","II"),
        ("🌊","HBV · Catchment Model",
         "Bergström 1992 HBV: Snow + Soil + Groundwater + Routing · "
         "Natural Flow Baseline · HIFD legal metric · Monte Carlo 200 runs · "
         "Latin Hypercube calibration (300 trials)",
         "#10b981","III"),
        ("🏛️","Operations Room",
         "Live global dispute map (25 basins) · Multi-role views · Scenario War Room · "
         "Risk Matrix · Sovereign Intelligence SITREP (EN/AR) · Sovereignty Index",
         "#dc2626","III"),
        ("💧","Groundwater & Irrigation",
         "MODFLOW-inspired 2-zone GW model · FAO-56 crop water demand · "
         "Urban water demand · Muskingum flood routing · GW–surface water interaction",
         "#06b6d4","III"),
        ("🧪","Water Quality",
         "EC/TDS · BOD/DO · pH · Turbidity · Nitrates · Heavy metals proxy · "
         "WHO 2017 & FAO standards · Art. 20/21 compliance dashboard",
         "#f97316","III"),
        ("🗂️","Audit Trail",
         "SHA-256 immutable event log · 5-role RBAC · Evidence chain builder · "
         "ICJ admissibility checklist · SemVer docs · pytest suite · MkDocs config",
         "#f59e0b","III"),
    ]

    # Show in 3 columns
    for i in range(0, len(modules), 3):
        row_mods = modules[i:i+3]
        cols_m   = st.columns(3)
        for col_m, (emoji, name, desc, color, phase) in zip(cols_m, row_mods):
            phase_color = {"I":"#10b981","II":"#3b82f6","III":"#ef4444"}[phase]
            col_m.markdown(
                f"<div class='mod-card' style='border-color:{color};'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"margin-bottom:0.4rem;'>"
                f"<span style='font-size:1.5rem;'>{emoji}</span>"
                f"<span style='background:{phase_color}22;color:{phase_color};"
                f"border-radius:12px;padding:2px 10px;font-size:0.7rem;"
                f"font-weight:700;'>Phase {phase}</span></div>"
                f"<div style='color:{color};font-weight:700;font-size:0.95rem;"
                f"margin-bottom:0.4rem;'>{name}</div>"
                f"<div style='color:#94a3b8;font-size:0.77rem;line-height:1.5;'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.markdown("")

    st.markdown("---")

    # ── PHASES ────────────────────────────────────────────────────────────────
    st.markdown("## 📅 Development Roadmap")

    phases = [
        ("#10b981", "Phase I — Foundation", "v430 · v990 · Science · Legal · DevOps",
         "Core hybrid DSS, legal automation, Penman physics, ICJ precedents. "
         "Single source of truth (basins_global.py) with 26 global basins."),
        ("#3b82f6", "Phase II — Validation & Alerts", "Validation · Alerts",
         "GRDC ground-truth validation (NSE/KGE/Taylor), Telegram real-time dispatch, "
         "Auto-Protest Article 12, multi-level legal alert engine."),
        ("#ef4444", "Phase III — Sovereign Intelligence", "HBV · OpsRoom · GW · Quality · Audit",
         "Full catchment modelling (Bergström HBV), Live Operations Room with SITREP, "
         "groundwater + irrigation demand, water quality (WHO/FAO), legal audit trail with RBAC."),
    ]

    for color, title, modules_str, desc in phases:
        st.markdown(
            f"<div class='phase-block' style='border-color:{color};'>"
            f"<div style='color:{color};font-weight:700;font-size:1.05rem;'>{title}</div>"
            f"<div style='color:#cbd5e1;font-size:0.82rem;margin:0.2rem 0;'>"
            f"<i>{modules_str}</i></div>"
            f"<div style='color:#94a3b8;font-size:0.85rem;'>{desc}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── SCIENCE FOUNDATION ────────────────────────────────────────────────────
    st.markdown("## 🔬 Scientific Foundation")

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown("""
**Hydrological Models**
- HBV (Bergström 1992) — Snow + Soil + GW + Routing
- Penman-Monteith (FAO-56) — Reference ET
- Hargreaves — ET₀ from temperature
- Muskingum — Channel flood routing
- MODFLOW-inspired — 2-zone groundwater

**Remote Sensing Inputs**
- Sentinel-1 SAR — Surface area (all weather)
- Sentinel-2 NDWI — Optical water extent
- GPM IMERG — Precipitation (30-min)
- MODIS ET — Evapotranspiration proxy
- GRDC — River discharge observations
""")

    with col_s2:
        st.markdown("""
**AI & Statistics**
- Random Forest — Storage & inflow forecast
- Monte Carlo — Parameter uncertainty (200 runs)
- Latin Hypercube — HBV calibration (300 trials)
- NSE / KGE / PBIAS — Model performance

**Legal Framework**
- UN 1997 Watercourses Convention (12 articles)
- ICJ/PCA/ITLOS precedents (Gabčíkovo, Pulp Mills…)
- WHO 2017 Water Quality Guidelines
- FAO-56 Irrigation Standards
- ILC 2001 Evidence Admissibility

**Validation Metrics**
- Nash-Sutcliffe Efficiency (NSE)
- Kling-Gupta Efficiency (KGE)
- Percent Bias (PBIAS)
- Taylor Diagram (r, σ, RMSE)
""")

    st.markdown("---")

    # ── LEGAL MAP ─────────────────────────────────────────────────────────────
    st.markdown("## ⚖️ UN 1997 Article Coverage")

    articles = [
        ("Art. 5", "Equitable Utilization", "Equity Index — outflow/inflow ratio",   "v430, v990, HBV"),
        ("Art. 7", "No Significant Harm",   "HIFD threshold > 40%",                  "HBV, Alerts"),
        ("Art. 9", "Data Exchange",         "Digital Transparency Index (TDI)",       "v990, Audit"),
        ("Art. 12","Notification",          "Auto-Protest generator (AI-triggered)",  "Alerts"),
        ("Art. 20","Ecosystem Protection",  "NDVI + DO + Sediment load proxies",      "v990, Quality"),
        ("Art. 21","Prevention of Pollution","EC/TDS/BOD/pH/Nitrates dashboard",      "Quality"),
        ("Annex 6","Fact-finding",          "SHA-256 evidence chain, audit log",      "Audit"),
        ("Annex 11","Counter-claims",       "Historical archive + dossier builder",   "Audit"),
        ("Annex 14","Binding Awards",       "Reproducible model → binding decisions", "All"),
    ]

    df_arts = pd.DataFrame(articles, columns=["Article","Principle","HSAE Metric","Module"])
    st.dataframe(df_arts, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── QUICK START ───────────────────────────────────────────────────────────
    st.markdown("## 🚀 Quick Start")

    qs_col1, qs_col2 = st.columns(2)

    with qs_col1:
        st.markdown("""
**Installation**
```bash
git clone https://github.com/your-org/hsae.git
cd hsae
pip install -r requirements.txt
streamlit run app.py
```

**Docker (recommended)**
```bash
docker compose up -d
# Open: http://localhost:8501
```
""")

    with qs_col2:
        st.markdown("""
**Typical Workflow**
1. Select basin in sidebar (search by river/country/Arabic)
2. 🌐 **v430** — Run hybrid engine (Simulation mode)
3. ⚖️ **v990** — Review legal & MODIS ET analysis
4. 🌊 **HBV** — Run natural flow baseline
5. 📊 **Validation** — Upload GRDC CSV for NSE/KGE
6. 🚨 **Alerts** — Configure Telegram + check Art. 12
7. 🏛️ **OpsRoom** — Global map + SITREP export
8. 🗂️ **Audit** — Generate evidence dossier
""")

    st.markdown("---")

    # ── CITATION ─────────────────────────────────────────────────────────────
    st.markdown("## 📄 Citation")
    st.code("""@software{alkedir_hsae_2026,
  author    = {Alkedir, Seifeldin M. G.},
  title     = {HydroSovereign AI Engine (HSAE): An Open-Source Platform for
               Transboundary Water Sovereignty Analysis},
  year      = {2026},
  version   = {5.0.0},
  url       = {https://github.com/your-org/hsae},
  note      = {Institute of Environmental Studies, University of Khartoum}
}""", language="bibtex")

    st.markdown("""
> *"The first open-source system to quantify the gap between what a dam
> should release by the laws of physics and what it declares — and
> translate that gap into legally actionable evidence."*
""")


# ── pandas import needed for article table
import pandas as pd
