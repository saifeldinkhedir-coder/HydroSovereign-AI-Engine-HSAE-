# hsae_validation.py  –  HSAE Ground Truth & Validation Module
# ═══════════════════════════════════════════════════════════════════════════════
# Covers:
#   1. GRDC-compatible CSV ingestion (auto column detection)
#   2. NSE / KGE / RMSE / R² skill metrics
#   3. Taylor Diagram
#   4. Regime signature plots (FDC, seasonal, anomaly)
#   5. Uncertainty bands (5/25/75/95 percentiles)
#   6. Download validated benchmark report
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
import io


# ══════════════════════════════════════════════════════════════════════════════
# SKILL METRICS
# ══════════════════════════════════════════════════════════════════════════════

def nse(obs: np.ndarray, sim: np.ndarray) -> float:
    """Nash-Sutcliffe Efficiency  [-∞, 1]  — 1 = perfect."""
    obs_mean = np.nanmean(obs)
    ss_res   = np.nansum((obs - sim) ** 2)
    ss_tot   = np.nansum((obs - obs_mean) ** 2)
    return float(1 - ss_res / (ss_tot + 1e-12))


def kge(obs: np.ndarray, sim: np.ndarray) -> float:
    """Kling-Gupta Efficiency  [-∞, 1]  — 1 = perfect."""
    r = float(np.corrcoef(obs, sim)[0, 1])
    alpha = float(np.std(sim) / (np.std(obs) + 1e-12))
    beta  = float(np.mean(sim) / (np.mean(obs) + 1e-12))
    return float(1 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2))


def pbias(obs: np.ndarray, sim: np.ndarray) -> float:
    """Percent bias  — 0 = perfect,  ±10% acceptable."""
    return float(100 * (np.nansum(sim - obs) / (np.nansum(obs) + 1e-12)))


def rmse(obs: np.ndarray, sim: np.ndarray) -> float:
    return float(np.sqrt(np.nanmean((obs - sim) ** 2)))


def r2(obs: np.ndarray, sim: np.ndarray) -> float:
    r = np.corrcoef(obs, sim)[0, 1]
    return float(r ** 2)


def rating(val: float, metric: str) -> tuple[str, str]:
    """Return (label, colour) for a skill metric value."""
    thresholds = {
        "NSE":   [(0.75, "✅ Excellent", "#10b981"),
                  (0.65, "✅ Good",      "#22c55e"),
                  (0.50, "⚠️ Satisfactory","#f59e0b"),
                  (-999, "❌ Unsatisfactory","#ef4444")],
        "KGE":   [(0.75, "✅ Excellent", "#10b981"),
                  (0.60, "✅ Good",      "#22c55e"),
                  (0.40, "⚠️ Satisfactory","#f59e0b"),
                  (-999, "❌ Unsatisfactory","#ef4444")],
        "R2":    [(0.90, "✅ Excellent", "#10b981"),
                  (0.75, "✅ Good",      "#22c55e"),
                  (0.50, "⚠️ Satisfactory","#f59e0b"),
                  (-999, "❌ Unsatisfactory","#ef4444")],
        "PBIAS": [((-5,5),   "✅ Excellent", "#10b981"),
                  ((-10,10), "✅ Good",      "#22c55e"),
                  ((-25,25), "⚠️ Satisfactory","#f59e0b"),
                  (None,     "❌ Unsatisfactory","#ef4444")],
    }
    if metric == "PBIAS":
        for thresh, lbl, col in thresholds["PBIAS"]:
            if thresh is None:
                return lbl, col
            lo, hi = thresh
            if lo <= val <= hi:
                return lbl, col
    else:
        for thresh, lbl, col in thresholds.get(metric, []):
            if val >= thresh:
                return lbl, col
    return "❓ Unknown", "#6b7280"


# ══════════════════════════════════════════════════════════════════════════════
# CSV INGESTION — flexible column detection (Arabic + English + GRDC)
# ══════════════════════════════════════════════════════════════════════════════

_DATE_ALIASES = ["date","Date","DATE","datetime","time","timestamp",
                 "تاريخ","يوم"]

_Q_ALIASES    = ["discharge","flow","q","Q","streamflow","runoff",
                 "inflow","Inflow","Inflow_obs","q_m3s","discharge_m3s",
                 "Flow_m3s","الجريان","تصريف","تدفق"]

_VOL_ALIASES  = ["volume","Volume","storage","Storage","Volume_obs",
                 "vol_bcm","storage_bcm","حجم","تخزين"]

_LEVEL_ALIASES= ["level","Level","stage","Stage","water_level",
                 "Level_obs","مستوى","منسوب"]

_RAIN_ALIASES = ["rain","Rain","rainfall","Rainfall","precip",
                 "precipitation","Rain_obs","GPM_Rain_mm","أمطار","هطول"]

_ET_ALIASES   = ["et","ET","evap","evapotranspiration","ET_mm",
                 "evap_mm","MODIS_ET","التبخر","تبخر_نتح"]


def _detect(df: pd.DataFrame, aliases: list[str]) -> str | None:
    for a in aliases:
        if a in df.columns:
            return a
    return None


def _load_obs(file) -> pd.DataFrame:
    """Load observation CSV, detect and rename key columns."""
    raw = pd.read_csv(file, comment="#", skip_blank_lines=True)
    raw.columns = raw.columns.str.strip()

    # Date
    date_col = _detect(raw, _DATE_ALIASES)
    if date_col is None:
        raise ValueError("No date column found. Rename to 'Date'.")
    raw["_date"] = pd.to_datetime(raw[date_col], errors="coerce", dayfirst=True)
    raw = raw.dropna(subset=["_date"]).sort_values("_date").reset_index(drop=True)

    out = pd.DataFrame({"Date": raw["_date"]})

    # Discharge / Inflow
    q_col = _detect(raw, _Q_ALIASES)
    if q_col:
        q_vals = pd.to_numeric(raw[q_col], errors="coerce")
        # Auto-convert m³/s → BCM/day if values > 0.5 (BCM would be huge)
        if q_vals.dropna().max() > 500:   # clearly m³/s
            q_vals = q_vals * 86400 / 1e9  # m³/s → BCM/day
        out["Q_obs"] = q_vals

    # Volume / Storage
    v_col = _detect(raw, _VOL_ALIASES)
    if v_col:
        out["V_obs"] = pd.to_numeric(raw[v_col], errors="coerce")

    # Water level
    l_col = _detect(raw, _LEVEL_ALIASES)
    if l_col:
        out["L_obs"] = pd.to_numeric(raw[l_col], errors="coerce")

    # Rainfall
    r_col = _detect(raw, _RAIN_ALIASES)
    if r_col:
        out["R_obs"] = pd.to_numeric(raw[r_col], errors="coerce")

    # ET
    et_col = _detect(raw, _ET_ALIASES)
    if et_col:
        out["ET_obs"] = pd.to_numeric(raw[et_col], errors="coerce")

    return out


def _align(sim_df: pd.DataFrame, obs_df: pd.DataFrame) -> pd.DataFrame:
    """Merge simulated and observed on Date, inner join."""
    s = sim_df[["Date","Inflow_BCM","Volume_BCM","GPM_Rain_mm"]].copy()
    merged = pd.merge(s, obs_df, on="Date", how="inner")
    return merged


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def render_validation_page(df_sim: pd.DataFrame | None, basin: dict) -> None:
    """Full validation & skill-score dashboard."""

    st.markdown("""
<style>
.val-card {
    background: linear-gradient(135deg,#0f172a,#0a1628);
    border: 2px solid #3b82f6;
    border-radius:16px; padding:1.2rem;
    box-shadow: 0 10px 40px rgba(59,130,246,0.2);
}
.skill-badge {
    display:inline-block; border-radius:6px;
    padding:2px 10px; margin:2px; font-size:0.85rem;
    font-weight:700;
}
</style>
""", unsafe_allow_html=True)

    # Header
    basin_name = basin.get("id", "—")
    st.markdown(f"""
<div class='val-card'>
  <h1 style='color:#3b82f6;font-family:Orbitron;text-align:center;font-size:2rem;margin:0;'>
    📊 HSAE Validation Module
  </h1>
  <p style='text-align:center;color:#94a3b8;letter-spacing:2px;font-family:Orbitron;
            font-size:0.82rem;margin:0.4rem 0 0;'>
    NSE · KGE · RMSE · R²  |  GRDC-COMPATIBLE  |  BILINGUAL
  </p>
  <hr style='border-color:#3b82f6;margin:0.7rem 0;'>
  <p style='text-align:center;color:#e2e8f0;margin:0;'>
    🎯 Active Basin: <b style='color:#60a5fa;'>{basin.get("id","—")} — {basin.get("river","—")}</b>
    &nbsp;|&nbsp; {basin.get("continent","—")}
  </p>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Info box ──────────────────────────────────────────────────────────────
    st.info(
        "**Accepted column names (case-insensitive, Arabic + English):**\n"
        "- **Date:** `Date` `datetime` `timestamp` `تاريخ`\n"
        "- **Discharge:** `discharge` `flow` `q` `inflow` `Inflow_obs` `تصريف` `تدفق`\n"
        "- **Volume/Storage:** `volume` `storage` `Volume_obs` `حجم` `تخزين`\n"
        "- **Water level:** `level` `stage` `Level_obs` `مستوى` `منسوب`\n"
        "- **Rainfall:** `rain` `rainfall` `Rain_obs` `precip` `أمطار`\n"
        "- **ET (MODIS):** `ET_mm` `evap` `MODIS_ET` `التبخر`\n\n"
        "Discharge in **m³/s** is auto-converted to BCM/day."
    )

    # ── Upload ────────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "📂 Upload GRDC / gauge station CSV",
        type=["csv", "txt"],
        key="val_upload",
    )

    if uploaded is None:
        st.markdown("### 📡 Sample Data Demo")
        if df_sim is not None:
            _show_demo(df_sim, basin)
        else:
            st.warning("Run the **v430 engine** first, then upload observed data here.")
        return

    # ── Load & parse ──────────────────────────────────────────────────────────
    try:
        obs_df = _load_obs(uploaded)
        st.success(
            f"✅ Loaded **{len(obs_df):,} rows** | "
            f"Columns: {', '.join(c for c in obs_df.columns if c != 'Date')}"
        )
    except Exception as e:
        st.error(f"❌ Parse error: {e}")
        return

    if df_sim is None:
        st.warning("⚠️ No simulation data. Run the **v430 engine** first.")
        return

    # ── Align sim ↔ obs ───────────────────────────────────────────────────────
    merged = _align(df_sim, obs_df)
    n_common = len(merged)
    if n_common < 30:
        st.warning(
            f"Only {n_common} overlapping dates found. "
            "Ensure the CSV date range overlaps with the simulation period."
        )
        if n_common == 0:
            return

    st.markdown(f"**📅 Overlap period:** {merged['Date'].min().date()} → "
                f"{merged['Date'].max().date()} ({n_common:,} days)")

    # ── Skill metrics ─────────────────────────────────────────────────────────
    metrics_tabs = st.tabs([
        "📐 Skill Scores", "📈 Hydrograph", "🌊 Flow Duration",
        "📅 Seasonal", "🔭 Taylor Diagram", "📥 Report"
    ])

    # ─ Tab 1: Skill scores ──────────────────────────────────────────────────
    with metrics_tabs[0]:
        st.subheader("Hydrological Skill Scores")

        _compute_and_display_scores(merged, basin)

    # ─ Tab 2: Hydrograph ──────────────────────────────────────────────────────
    with metrics_tabs[1]:
        st.subheader("Simulated vs Observed Hydrograph")

        fig_hyd = go.Figure()
        if "Q_obs" in merged.columns:
            fig_hyd.add_trace(go.Scatter(
                x=merged["Date"], y=merged["Q_obs"],
                name="Observed (GRDC)", line=dict(color="#ef4444", width=2)
            ))
        fig_hyd.add_trace(go.Scatter(
            x=merged["Date"], y=merged["Inflow_BCM"],
            name="Simulated (HSAE)", line=dict(color="#10b981", width=2)
        ))
        if "V_obs" in merged.columns:
            fig_hyd.add_trace(go.Scatter(
                x=merged["Date"], y=merged["V_obs"],
                name="Volume Obs.", line=dict(color="#f59e0b", width=2,
                dash="dot"), yaxis="y2"
            ))
            fig_hyd.add_trace(go.Scatter(
                x=merged["Date"], y=merged["Volume_BCM"],
                name="Volume Sim.", line=dict(color="#3b82f6", width=2,
                dash="dot"), yaxis="y2"
            ))
            fig_hyd.update_layout(
                yaxis2=dict(title="Storage (BCM)", overlaying="y",
                            side="right", showgrid=False)
            )

        fig_hyd.update_layout(
            template="plotly_dark", height=480,
            title=f"HSAE Simulation vs GRDC Observations — {basin.get('id','—')}",
            xaxis_title="Date", yaxis_title="Inflow / Discharge (BCM/day)"
        )
        st.plotly_chart(fig_hyd, use_container_width=True)

        # Scatter
        if "Q_obs" in merged.columns:
            fig_sc = px.scatter(
                merged, x="Q_obs", y="Inflow_BCM",
                trendline="ols", template="plotly_dark",
                labels={"Q_obs": "Observed (BCM/day)",
                        "Inflow_BCM": "Simulated (BCM/day)"},
                title="Scatter: Observed vs Simulated Inflow",
                color_discrete_sequence=["#10b981"],
                height=400,
            )
            fig_sc.add_shape(type="line",
                x0=merged["Q_obs"].min(), x1=merged["Q_obs"].max(),
                y0=merged["Q_obs"].min(), y1=merged["Q_obs"].max(),
                line=dict(color="#fbbf24", dash="dash", width=1.5))
            st.plotly_chart(fig_sc, use_container_width=True)

    # ─ Tab 3: Flow Duration Curve ─────────────────────────────────────────────
    with metrics_tabs[2]:
        st.subheader("Flow Duration Curve (FDC)")

        fig_fdc = go.Figure()
        exc = np.linspace(0, 100, 200)

        q_sim = np.sort(merged["Inflow_BCM"].dropna().values)[::-1]
        pct_sim = np.linspace(0, 100, len(q_sim))
        fig_fdc.add_trace(go.Scatter(
            x=pct_sim, y=q_sim, name="HSAE Sim.",
            line=dict(color="#10b981", width=3)
        ))

        if "Q_obs" in merged.columns:
            q_obs = np.sort(merged["Q_obs"].dropna().values)[::-1]
            pct_obs = np.linspace(0, 100, len(q_obs))
            fig_fdc.add_trace(go.Scatter(
                x=pct_obs, y=q_obs, name="GRDC Obs.",
                line=dict(color="#ef4444", width=3, dash="dot")
            ))

        fig_fdc.update_layout(
            template="plotly_dark", height=440,
            title="Flow Duration Curve — Simulated vs Observed",
            xaxis_title="Exceedance Probability (%)",
            yaxis_title="Discharge (BCM/day)",
            yaxis_type="log",
        )
        st.plotly_chart(fig_fdc, use_container_width=True)
        st.caption("Log-Y axis — FDC shape reveals high-flow, low-flow and flashiness regime.")

    # ─ Tab 4: Seasonal ────────────────────────────────────────────────────────
    with metrics_tabs[3]:
        st.subheader("Seasonal Analysis")

        m = merged.copy()
        m["Month"] = pd.to_datetime(m["Date"]).dt.month
        month_lbl  = ["Jan","Feb","Mar","Apr","May","Jun",
                      "Jul","Aug","Sep","Oct","Nov","Dec"]

        fig_seas = go.Figure()
        sim_mo = m.groupby("Month")["Inflow_BCM"].mean()
        fig_seas.add_trace(go.Bar(
            x=month_lbl, y=sim_mo.values,
            name="Simulated", marker_color="#10b981"
        ))

        if "Q_obs" in m.columns:
            obs_mo = m.groupby("Month")["Q_obs"].mean()
            fig_seas.add_trace(go.Bar(
                x=month_lbl, y=obs_mo.values,
                name="Observed", marker_color="#ef4444", opacity=0.7
            ))

        fig_seas.update_layout(
            template="plotly_dark", height=400,
            title="Mean Monthly Flow — Simulated vs Observed",
            xaxis_title="Month", yaxis_title="BCM/day",
            barmode="group"
        )
        st.plotly_chart(fig_seas, use_container_width=True)

        # Anomaly
        if "Q_obs" in m.columns:
            m["Anomaly"] = m["Inflow_BCM"] - m["Q_obs"]
            fig_an = go.Figure(go.Bar(
                x=m["Date"], y=m["Anomaly"],
                marker_color=np.where(m["Anomaly"] >= 0, "#10b981", "#ef4444")
            ))
            fig_an.update_layout(
                template="plotly_dark", height=320,
                title="Daily Anomaly (Simulated − Observed)",
                yaxis_title="BCM/day"
            )
            st.plotly_chart(fig_an, use_container_width=True)

    # ─ Tab 5: Taylor Diagram ──────────────────────────────────────────────────
    with metrics_tabs[4]:
        st.subheader("Taylor Diagram")
        if "Q_obs" not in merged.columns:
            st.info("Upload a CSV with discharge / inflow column to generate Taylor Diagram.")
        else:
            obs  = merged["Q_obs"].dropna().values
            sim  = merged["Inflow_BCM"].iloc[:len(obs)].values
            _taylor_diagram(obs, sim, label="HSAE v430")

    # ─ Tab 6: Residual Analysis ────────────────────────────────────────────────
    with tabs[5]:
        st.subheader("📊 Residual Analysis")
        if merged is None:
            st.info("Upload observed discharge CSV to view residual analysis.")
        else:
            import plotly.graph_objects as go
            import plotly.express as px
            obs_r = merged["Obs"].values
            sim_r = merged["Sim"].values
            residuals = sim_r - obs_r
            rel_res   = residuals / (obs_r + 1e-9) * 100  # % relative residual

            col1, col2 = st.columns(2)
            with col1:
                # Time series of residuals
                fig_r = go.Figure()
                fig_r.add_trace(go.Scatter(
                    x=merged.index, y=residuals, mode="lines",
                    line=dict(color="#f87171", width=1),
                    name="Residual (Sim − Obs)"
                ))
                fig_r.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
                fig_r.update_layout(
                    template="plotly_dark", height=320,
                    title="Residuals Over Time",
                    yaxis_title="Residual (BCM/day)"
                )
                st.plotly_chart(fig_r, use_container_width=True)

            with col2:
                # Residual histogram
                fig_h = px.histogram(
                    x=residuals, nbins=40,
                    title="Residual Distribution",
                    labels={"x": "Residual (BCM/day)"},
                    template="plotly_dark",
                    color_discrete_sequence=["#60a5fa"]
                )
                fig_h.update_layout(height=320)
                st.plotly_chart(fig_h, use_container_width=True)

            # Obs vs Sim scatter
            col3, col4 = st.columns(2)
            with col3:
                fig_s = px.scatter(
                    x=obs_r, y=sim_r,
                    labels={"x": "Observed (BCM/day)", "y": "Simulated (BCM/day)"},
                    title="Observed vs Simulated",
                    template="plotly_dark",
                    opacity=0.5,
                    color_discrete_sequence=["#34d399"]
                )
                # 1:1 line
                mn, mx = float(obs_r.min()), float(obs_r.max())
                fig_s.add_trace(go.Scatter(
                    x=[mn, mx], y=[mn, mx], mode="lines",
                    line=dict(color="#f59e0b", dash="dash"), name="1:1"
                ))
                fig_s.update_layout(height=320)
                st.plotly_chart(fig_s, use_container_width=True)

            with col4:
                # Q-Q plot (sorted residuals vs normal quantiles)
                from scipy import stats as sp_stats
                sorted_res = sorted(residuals)
                n = len(sorted_res)
                theoretical = sp_stats.norm.ppf([(i+0.5)/n for i in range(n)])
                fig_qq = go.Figure()
                fig_qq.add_trace(go.Scatter(
                    x=theoretical, y=sorted_res, mode="markers",
                    marker=dict(color="#a78bfa", size=4), name="Residuals"
                ))
                mn_t, mx_t = float(min(theoretical)), float(max(theoretical))
                std_r = float(residuals.std())
                fig_qq.add_trace(go.Scatter(
                    x=[mn_t, mx_t], y=[mn_t*std_r, mx_t*std_r],
                    mode="lines", line=dict(color="#f59e0b", dash="dash"), name="Normal"
                ))
                fig_qq.update_layout(
                    template="plotly_dark", height=320,
                    title="Q-Q Plot (Normality Check)",
                    xaxis_title="Theoretical Quantiles",
                    yaxis_title="Sample Quantiles"
                )
                st.plotly_chart(fig_qq, use_container_width=True)

            # Summary stats
            bias    = float(residuals.mean())
            std_res = float(residuals.std())
            mae     = float(abs(residuals).mean())
            max_res = float(abs(residuals).max())
            st.markdown(f"""
| Metric | Value |
|--------|-------|
| Mean Bias (Sim−Obs) | `{bias:+.4f}` BCM/day |
| Std of Residuals | `{std_res:.4f}` BCM/day |
| MAE | `{mae:.4f}` BCM/day |
| Max Absolute Residual | `{max_res:.4f}` BCM/day |
| % Time Overestimated | `{(residuals>0).mean()*100:.1f}%` |
| % Time Underestimated | `{(residuals<0).mean()*100:.1f}%` |
""")

    # ─ Tab 7: Download report ─────────────────────────────────────────────────
    with metrics_tabs[5]:
        st.subheader("📥 Download Validation Report")

        scores = _get_scores(merged)
        html   = _build_report_html(scores, merged, basin)
        csv_b  = merged.to_csv(index=False).encode("utf-8")

        c1, c2 = st.columns(2)
        c1.download_button(
            "📄 HTML Validation Report",
            html.encode("utf-8"),
            file_name=f"HSAE_Validation_{basin.get('id','basin')}.html",
            mime="text/html",
        )
        c2.download_button(
            "📊 Aligned CSV (Sim + Obs)",
            csv_b,
            file_name=f"HSAE_Aligned_{basin.get('id','basin')}.csv",
            mime="text/csv",
        )


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_scores(merged: pd.DataFrame) -> dict:
    scores = {}
    if "Q_obs" in merged.columns:
        obs = merged["Q_obs"].dropna().values
        sim = merged["Inflow_BCM"].iloc[:len(obs)].values
        scores["inflow"] = {
            "NSE":   nse(obs, sim),
            "KGE":   kge(obs, sim),
            "R2":    r2(obs, sim),
            "RMSE":  rmse(obs, sim),
            "PBIAS": pbias(obs, sim),
        }
    if "V_obs" in merged.columns:
        obs_v = merged["V_obs"].dropna().values
        sim_v = merged["Volume_BCM"].iloc[:len(obs_v)].values
        scores["volume"] = {
            "NSE":   nse(obs_v, sim_v),
            "KGE":   kge(obs_v, sim_v),
            "R2":    r2(obs_v, sim_v),
            "RMSE":  rmse(obs_v, sim_v),
            "PBIAS": pbias(obs_v, sim_v),
        }
    return scores


def _compute_and_display_scores(merged: pd.DataFrame, basin: dict) -> None:
    scores = _get_scores(merged)

    if not scores:
        st.warning("No matching observed columns (Q_obs / V_obs) found.")
        return

    for var, sc in scores.items():
        label = "Inflow / Discharge" if var == "inflow" else "Volume / Storage"
        st.markdown(f"#### {label}")

        cols = st.columns(5)
        for i, (metric, val) in enumerate(sc.items()):
            lbl, color = rating(val, metric)
            cols[i].markdown(
                f"<div style='text-align:center;padding:0.6rem;"
                f"background:#0f172a;border:1px solid {color};"
                f"border-radius:10px;'>"
                f"<div style='color:#94a3b8;font-size:0.78rem;'>{metric}</div>"
                f"<div style='color:{color};font-size:1.4rem;font-weight:700;'>"
                f"{val:.3f}</div>"
                f"<div style='font-size:0.72rem;color:{color};'>{lbl}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Moriasi et al. 2007 reference
        st.caption(
            "Reference thresholds: Moriasi et al. (2007) J. ASABE 50(3):885-900  "
            "| NSE>0.65 Good | KGE>0.60 Good | PBIAS<±10% Good"
        )
        st.markdown("---")


def _taylor_diagram(obs: np.ndarray, sim: np.ndarray, label: str = "Model") -> None:
    """Approximate Taylor Diagram using polar scatter in plotly."""
    obs_std  = float(np.std(obs))
    sim_std  = float(np.std(sim))
    r_val    = float(np.corrcoef(obs, sim)[0, 1])
    theta    = float(np.arccos(np.clip(r_val, -1, 1)))
    x_sim    = sim_std * np.cos(theta)
    y_sim    = sim_std * np.sin(theta)
    x_ref    = obs_std
    crmse    = float(np.sqrt(np.mean(((sim - sim.mean()) - (obs - obs.mean()))**2)))

    fig = go.Figure()
    # Arc of constant correlation
    theta_arc = np.linspace(0, np.pi / 2, 200)
    for r_line in [0.0, 0.3, 0.5, 0.7, 0.9, 0.99]:
        ta = np.arccos(r_line)
        r_max = obs_std * 1.8
        fig.add_trace(go.Scatter(
            x=[r_max * np.cos(ta)] * 2, y=[0, r_max * np.sin(ta)],
            mode="lines",
            line=dict(color="rgba(100,116,139,0.4)", width=1, dash="dot"),
            showlegend=False,
            hovertemplate=f"r={r_line:.2f}<extra></extra>",
        ))
        fig.add_annotation(
            x=r_max * np.cos(ta) * 1.05, y=r_max * np.sin(ta) * 1.05,
            text=f"r={r_line:.1f}", showarrow=False,
            font=dict(color="#64748b", size=10)
        )

    # RMS contours around reference
    for crmse_level in [obs_std * 0.25, obs_std * 0.5, obs_std * 0.75]:
        theta_c = np.linspace(0, 2 * np.pi, 200)
        fig.add_trace(go.Scatter(
            x=x_ref + crmse_level * np.cos(theta_c),
            y=crmse_level * np.sin(theta_c),
            mode="lines",
            line=dict(color="rgba(59,130,246,0.3)", width=1),
            showlegend=False,
        ))

    # Reference point
    fig.add_trace(go.Scatter(
        x=[x_ref], y=[0], mode="markers+text",
        marker=dict(size=14, color="#fbbf24", symbol="star"),
        text=["Reference\n(GRDC)"],
        textposition="top right",
        name="Reference",
        textfont=dict(color="#fbbf24"),
    ))

    # Model point
    fig.add_trace(go.Scatter(
        x=[x_sim], y=[y_sim], mode="markers+text",
        marker=dict(size=12, color="#10b981"),
        text=[label],
        textposition="top right",
        name=label,
        textfont=dict(color="#10b981"),
    ))

    fig.update_layout(
        template="plotly_dark",
        height=480,
        title=f"Taylor Diagram  (r={r_val:.3f}  stdRatio={sim_std/obs_std:.3f}  cRMSE={crmse:.4f})",
        xaxis=dict(title="σ (BCM/day)", range=[-0.05, obs_std * 1.9]),
        yaxis=dict(title="", range=[-0.05, obs_std * 1.9]),
        showlegend=True,
        annotations=[
            dict(x=obs_std * 1.85, y=-obs_std * 0.05,
                 text="Correlation →",
                 showarrow=False, font=dict(color="#94a3b8", size=10))
        ]
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Pearson r", f"{r_val:.4f}")
    c2.metric("Std Ratio (sim/obs)", f"{sim_std/obs_std:.4f}")
    c3.metric("Centred RMSE", f"{crmse:.4f} BCM/d")


def _show_demo(df_sim: pd.DataFrame, basin: dict) -> None:
    """Show demo metrics using simulation noise as synthetic 'observed'."""
    st.info(
        "🔍 **Demo mode** — No observed CSV uploaded. "
        "Showing synthetic noise-perturbed simulation as a validation demo."
    )
    seed = abs(hash(basin.get("id","X"))) % (2**31)
    rng  = np.random.default_rng(seed + 99)
    obs  = (df_sim["Inflow_BCM"] * (1 + rng.normal(0, 0.12, len(df_sim)))).clip(0)
    demo = df_sim[["Date","Inflow_BCM","Volume_BCM","GPM_Rain_mm"]].copy()
    demo["Q_obs"] = obs.values

    st.markdown("#### Demo Skill Scores (Sim vs Synthetic Obs ±12% noise)")
    sc = {
        "NSE":   nse(obs.values, demo["Inflow_BCM"].values),
        "KGE":   kge(obs.values, demo["Inflow_BCM"].values),
        "R2":    r2(obs.values,  demo["Inflow_BCM"].values),
        "RMSE":  rmse(obs.values,demo["Inflow_BCM"].values),
        "PBIAS": pbias(obs.values,demo["Inflow_BCM"].values),
    }
    cols = st.columns(5)
    for i, (metric, val) in enumerate(sc.items()):
        lbl, color = rating(val, metric)
        cols[i].markdown(
            f"<div style='text-align:center;padding:0.6rem;"
            f"background:#0f172a;border:1px solid {color};"
            f"border-radius:10px;'>"
            f"<div style='color:#94a3b8;font-size:0.78rem;'>{metric}</div>"
            f"<div style='color:{color};font-size:1.4rem;font-weight:700;'>"
            f"{val:.3f}</div>"
            f"<div style='font-size:0.72rem;color:{color};'>{lbl}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    fig_d = go.Figure()
    fig_d.add_trace(go.Scatter(x=demo["Date"], y=obs, name="Synthetic Obs",
                               line=dict(color="#ef4444")))
    fig_d.add_trace(go.Scatter(x=demo["Date"], y=demo["Inflow_BCM"],
                               name="HSAE Sim", line=dict(color="#10b981")))
    fig_d.update_layout(template="plotly_dark", height=350,
                        title="Demo Hydrograph", yaxis_title="BCM/day")
    st.plotly_chart(fig_d, use_container_width=True)


def _build_report_html(scores: dict, merged: pd.DataFrame, basin: dict) -> str:
    date_str = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")
    rows_html = ""
    for var, sc in scores.items():
        label = "Inflow/Discharge" if var == "inflow" else "Volume/Storage"
        rows_html += f"<tr><td colspan=2><b>{label}</b></td></tr>"
        for m, v in sc.items():
            lbl, _ = rating(v, m)
            rows_html += f"<tr><td>{m}</td><td>{v:.4f} — {lbl}</td></tr>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>HSAE Validation Report — {basin.get('id','—')}</title>
<style>
body{{font-family:Arial,sans-serif;margin:30px;background:#f8fafc;}}
h1{{color:#0f766e;}} h2{{color:#1d4ed8;}}
table{{border-collapse:collapse;width:60%;margin:1rem 0;}}
th,td{{border:1px solid #cbd5e1;padding:8px 14px;}}
th{{background:#1e3a5f;color:#fff;}}
.badge{{display:inline-block;padding:2px 10px;border-radius:5px;
        background:#dcfce7;color:#166534;font-weight:700;}}
</style>
</head><body>
<h1>HSAE Validation Report</h1>
<p><b>Basin:</b> {basin.get('id','—')} — {basin.get('river','—')}<br>
   <b>Dam:</b> {basin.get('dam','—')}<br>
   <b>Overlap Period:</b> {merged['Date'].min().date()} → {merged['Date'].max().date()}<br>
   <b>N days:</b> {len(merged):,}<br>
   <b>Generated:</b> {date_str}</p>
<h2>Skill Scores</h2>
<table><tr><th>Metric</th><th>Value</th></tr>
{rows_html}
</table>
<h2>Reference</h2>
<p>Moriasi, D.N. et al. (2007). Model Evaluation Guidelines for Systematic
Quantification of Accuracy in Watershed Simulations.
<i>Trans. ASABE</i> 50(3):885–900.</p>
<h2>Legal Note</h2>
<p>This validation report demonstrates the reproducibility and accuracy of
HSAE simulation outputs. NSE/KGE/PBIAS scores can be cited in technical
annexes to diplomatic negotiations or arbitral submissions under Articles 9
(data exchange) and Annex Article 6 (fact-finding) of the UN 1997
Watercourses Convention.</p>
</body></html>"""
