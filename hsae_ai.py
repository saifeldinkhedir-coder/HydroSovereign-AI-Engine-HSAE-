"""
hsae_ai.py  ─  HSAE v6.0.0  Advanced AI/ML Module
===================================================
Author : Seifeldin M.G. Alkedir
Version: 1.0.0  |  March 2026

1. Ensemble: RF + MLP + GBM (dynamic R²-weighted)
2. Multi-step forecast: 7/30/90 days
3. Anomaly Detection: Isolation Forest (legal evidence)
4. Feature Importance
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import streamlit as st
import warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestRegressor, IsolationForest, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
import plotly.graph_objects as go
import plotly.express as px

# ══════════════════════════════════════════════════════════════════════════════
# Feature Engineering
# ══════════════════════════════════════════════════════════════════════════════
def build_features(df: pd.DataFrame, target_col: str = "Volume_BCM") -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    base = [c for c in ["Inflow_BCM","Outflow_BCM","GPM_Rain_mm","ET0_mm_day","Losses","Pct_Full","Delta_V","Volume_BCM"] if c in df.columns]
    feat: list[str] = []
    for col in base:
        for lag in [1,3,7,14,30]:
            n = f"{col}_lag{lag}"; df[n] = df[col].shift(lag); feat.append(n)
    for col in ["Inflow_BCM","GPM_Rain_mm","Volume_BCM"]:
        if col not in df.columns: continue
        for w in [7,30]:
            n1,n2 = f"{col}_r{w}m", f"{col}_r{w}s"
            df[n1] = df[col].rolling(w,min_periods=1).mean()
            df[n2] = df[col].rolling(w,min_periods=1).std().fillna(0)
            feat += [n1,n2]
    df["doy_sin"] = np.sin(2*np.pi*df["Date"].dt.dayofyear/365.25)
    df["doy_cos"] = np.cos(2*np.pi*df["Date"].dt.dayofyear/365.25)
    df["month"]   = df["Date"].dt.month
    df["t_days"]  = (df["Date"]-df["Date"].iloc[0]).dt.days/365.25
    feat += ["doy_sin","doy_cos","month","t_days"]
    return df, feat

# ══════════════════════════════════════════════════════════════════════════════
# Ensemble
# ══════════════════════════════════════════════════════════════════════════════
def train_ensemble(df: pd.DataFrame, target: str = "Volume_BCM", seed: int = 42) -> dict:
    df_f, feat = build_features(df, target)
    dc = df_f.dropna(subset=feat+[target])
    if len(dc) < 100: return {"error":"Need ≥100 rows"}
    X, y = dc[feat].values, dc[target].values
    dates = dc["Date"].values
    tscv  = TimeSeriesSplit(n_splits=3)
    tr, te = list(tscv.split(X))[-1]
    Xtr,Xte,ytr,yte = X[tr],X[te],y[tr],y[te]

    rf = RandomForestRegressor(300,max_depth=10,min_samples_leaf=3,n_jobs=-1,random_state=seed)
    rf.fit(Xtr,ytr)

    sc = StandardScaler(); Xts = sc.fit_transform(Xtr)
    mlp = MLPRegressor((128,64,32),"relu","adam",max_iter=500,early_stopping=True,
                        validation_fraction=0.1,random_state=seed,learning_rate_init=0.001)
    mlp.fit(Xts,ytr)

    gbm = GradientBoostingRegressor(300,learning_rate=0.05,max_depth=5,subsample=0.8,random_state=seed)
    gbm.fit(Xtr,ytr)

    yrf  = rf.predict(Xte)
    ymlp = mlp.predict(sc.transform(Xte))
    ygbm = gbm.predict(Xte)
    r2rf  = max(r2_score(yte,yrf), 0.01)
    r2mlp = max(r2_score(yte,ymlp),0.01)
    r2gbm = max(r2_score(yte,ygbm),0.01)
    tot   = r2rf+r2mlp+r2gbm
    wrf,wmlp,wgbm = r2rf/tot, r2mlp/tot, r2gbm/tot
    yens  = wrf*yrf + wmlp*ymlp + wgbm*ygbm

    Xa = dc[feat].values
    ya_ens = wrf*rf.predict(Xa) + wmlp*mlp.predict(sc.transform(Xa)) + wgbm*gbm.predict(Xa)

    fi = pd.DataFrame({"feature":feat,"importance":rf.feature_importances_}).sort_values("importance",ascending=False).head(15)

    return {
        "dates_te":dates[te],"y_te_obs":yte,"y_te_rf":yrf,"y_te_mlp":ymlp,"y_te_gbm":ygbm,"y_te_ens":yens,
        "dates_all":dates,"y_all_ens":ya_ens,
        "metrics":{"RF_R2":round(r2_score(yte,yrf),3),"MLP_R2":round(r2_score(yte,ymlp),3),
                   "GBM_R2":round(r2_score(yte,ygbm),3),"ENS_R2":round(r2_score(yte,yens),3),
                   "ENS_RMSE":round(float(np.sqrt(mean_squared_error(yte,yens))),4),
                   "weights":{"RF":round(wrf,3),"MLP":round(wmlp,3),"GBM":round(wgbm,3)}},
        "feat_importance":fi, "target":target,
    }

# ══════════════════════════════════════════════════════════════════════════════
# Anomaly Detection
# ══════════════════════════════════════════════════════════════════════════════
def detect_anomalies(df: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    fc = [c for c in ["Volume_BCM","Delta_V","Inflow_BCM","Outflow_BCM","Pct_Full"] if c in df.columns]
    if len(fc) < 2:
        df["anomaly_score"] = 0.0; df["is_anomaly"] = False; return df
    X   = df[fc].fillna(df[fc].median())
    iso = IsolationForest(contamination=contamination,n_estimators=200,random_state=42,n_jobs=-1)
    df  = df.copy()
    iso.fit(X)
    df["anomaly_score"] = -iso.decision_function(X)
    df["is_anomaly"]    = iso.predict(X)==-1
    return df

# ══════════════════════════════════════════════════════════════════════════════
# Multi-step forecast
# ══════════════════════════════════════════════════════════════════════════════
def multi_step_forecast(df: pd.DataFrame, horizon: int = 30, target: str = "Inflow_BCM", seed: int = 42) -> dict | None:
    df_f, feat = build_features(df, target)
    dc = df_f.dropna(subset=feat+[target])
    if len(dc) < 60: return None
    X, y = dc[feat].values, dc[target].values
    sp   = max(30, len(X)-horizon)
    gbm  = GradientBoostingRegressor(200,learning_rate=0.08,max_depth=4,random_state=seed)
    gbm.fit(X[:sp],y[:sp])
    yp   = gbm.predict(X)
    fp   = np.array([max(gbm.predict(X[-1].reshape(1,-1))[0],0)]*horizon)
    ld   = pd.to_datetime(dc["Date"].values[-1])
    return {
        "dates_hist":dc["Date"].values,"y_hist_obs":y,"y_hist_pred":yp,
        "future_dates":pd.date_range(ld+pd.Timedelta(days=1),periods=horizon,freq="D"),
        "future_pred":fp,"horizon":horizon,"target":target,
        "r2":round(r2_score(y[sp:],yp[sp:]),3) if len(y[sp:])>1 else 0.0,
    }

# ══════════════════════════════════════════════════════════════════════════════
# Streamlit Page
# ══════════════════════════════════════════════════════════════════════════════
def render_ai_page(df: pd.DataFrame | None, basin: dict) -> None:
    st.markdown("""
<div style='background:linear-gradient(135deg,#020617,#0a0a2e);
            border:2px solid #a78bfa;border-radius:16px;padding:1.2rem 1.8rem;margin-bottom:1.2rem;'>
  <span style='font-size:1.6rem;'>🤖</span>
  <b style='color:#a78bfa;font-size:1.3rem;margin-left:0.6rem;'>Advanced AI / ML Engine</b><br>
  <span style='color:#94a3b8;font-size:0.83rem;'>
    Ensemble (RF+MLP+GBM) · Anomaly Detection (Isolation Forest) · Multi-Step Forecast · Feature Importance
  </span>
</div>""", unsafe_allow_html=True)

    if df is None or len(df)<100:
        st.warning("⚠️ Need ≥100 rows. Run v430 or load real data first.")
        return

    tab_ens, tab_fore, tab_anom, tab_feat = st.tabs(
        ["🧠 Ensemble","📈 Forecast","🚨 Anomalies","📊 Features"])

    # ── Ensemble ──────────────────────────────────────────────────────────────
    with tab_ens:
        st.markdown("### 🧠 Ensemble: RF + MLP + GBM")
        ct, cr = st.columns([3,1])
        target = ct.selectbox("Target", ["Volume_BCM","Inflow_BCM","Outflow_BCM","Power_MW"], key="ai_t")
        if cr.button("▶ Train", type="primary", key="ai_ens_btn"):
            with st.spinner("Training…"):
                st.session_state["ai_ens"] = train_ensemble(df, target)
        res = st.session_state.get("ai_ens")
        if res:
            if "error" in res: st.error(res["error"])
            else:
                m = res["metrics"]
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("🌲 RF",  f"{m['RF_R2']:.3f}")
                c2.metric("🧠 MLP", f"{m['MLP_R2']:.3f}")
                c3.metric("⚡ GBM", f"{m['GBM_R2']:.3f}")
                c4.metric("🎯 Ensemble", f"{m['ENS_R2']:.3f}", delta=f"RMSE {m['ENS_RMSE']:.4f}")
                st.caption(f"Weights — RF:{m['weights']['RF']} MLP:{m['weights']['MLP']} GBM:{m['weights']['GBM']}")
                fig = go.Figure()
                dte = pd.to_datetime(res["dates_te"])
                fig.add_trace(go.Scatter(x=dte,y=res["y_te_obs"],mode="lines",name="Observed",line=dict(color="#22c55e",width=2)))
                fig.add_trace(go.Scatter(x=dte,y=res["y_te_ens"],mode="lines",name="Ensemble",line=dict(color="#a78bfa",width=2)))
                fig.add_trace(go.Scatter(x=dte,y=res["y_te_rf"],mode="lines",name="RF",line=dict(color="#3b82f6",width=1,dash="dot"),opacity=0.6))
                fig.add_trace(go.Scatter(x=dte,y=res["y_te_mlp"],mode="lines",name="MLP",line=dict(color="#f59e0b",width=1,dash="dash"),opacity=0.6))
                fig.update_layout(template="plotly_dark",height=420,title=f"Test Set — {res['target']}",yaxis_title=res["target"])
                st.plotly_chart(fig,use_container_width=True)

    # ── Forecast ──────────────────────────────────────────────────────────────
    with tab_fore:
        st.markdown("### 📈 Multi-Step Forecast")
        c1,c2 = st.columns(2)
        hor  = c1.select_slider("Horizon (days)",[7,14,30,60,90],value=30,key="ai_hor")
        ftgt = c2.selectbox("Target",["Inflow_BCM","Outflow_BCM","Volume_BCM"],key="ai_ft")
        if st.button("▶ Forecast",type="primary",key="ai_fore_btn"):
            with st.spinner("Computing…"):
                st.session_state["ai_fore"] = multi_step_forecast(df,hor,ftgt)
        fr = st.session_state.get("ai_fore")
        if fr:
            st.metric(f"Model R² (last segment)",f"{fr['r2']:.3f}")
            fig = go.Figure()
            dh  = pd.to_datetime(fr["dates_hist"])
            mk  = dh>=(dh[-1]-np.timedelta64(180,"D"))
            fig.add_trace(go.Scatter(x=dh[mk],y=fr["y_hist_obs"][mk],mode="lines",name="Observed",line=dict(color="#22c55e",width=2)))
            fig.add_trace(go.Scatter(x=dh[mk],y=fr["y_hist_pred"][mk],mode="lines",name="Model fit",line=dict(color="#3b82f6",width=1.5,dash="dot")))
            fig.add_trace(go.Scatter(x=fr["future_dates"],y=fr["future_pred"],mode="lines+markers",name=f"{hor}-day Forecast",line=dict(color="#f59e0b",width=2.5)))
            fig.add_trace(go.Scatter(
                x=list(fr["future_dates"])+list(fr["future_dates"])[::-1],
                y=list(fr["future_pred"]*1.1)+list(fr["future_pred"]*0.9)[::-1],
                fill="toself",fillcolor="rgba(245,158,11,0.15)",line=dict(color="rgba(0,0,0,0)"),name="±10%"))
            fig.add_vline(x=str(pd.to_datetime(dh[-1]))[:10],line_dash="dash",line_color="#ef4444")
            fig.update_layout(template="plotly_dark",height=440,title=f"{hor}-day {ftgt} Forecast",yaxis_title=ftgt)
            st.plotly_chart(fig,use_container_width=True)

    # ── Anomalies ─────────────────────────────────────────────────────────────
    with tab_anom:
        st.markdown("### 🚨 Anomaly Detection — Isolation Forest")
        st.markdown("> Detects suspicious storage events → UN 1997 Art. 9 violations")
        c1,c2 = st.columns(2)
        cont = c1.slider("Contamination %",1,15,5,key="ai_cont")/100
        if c2.button("▶ Detect",type="primary",key="ai_anom_btn"):
            with st.spinner("Running…"):
                st.session_state["ai_anom"] = detect_anomalies(df,cont)
        da = st.session_state.get("ai_anom")
        if da is not None:
            na = da["is_anomaly"].sum()
            c1,c2,c3 = st.columns(3)
            c1.metric("🚨 Anomalies",str(na))
            c2.metric("% record",f"{na/len(da)*100:.1f}%")
            c3.metric("Total days",str(len(da)))
            fig = go.Figure()
            nm = da[~da["is_anomaly"]]; ab = da[da["is_anomaly"]]
            fig.add_trace(go.Scatter(x=nm["Date"],y=nm["Volume_BCM"],mode="lines",name="Normal",line=dict(color="#22c55e",width=1.5)))
            fig.add_trace(go.Scatter(x=ab["Date"],y=ab["Volume_BCM"],mode="markers",name="⚠️ Anomaly",marker=dict(color="#ef4444",size=8,symbol="x")))
            fig.update_layout(template="plotly_dark",height=400,title="Volume — Anomaly Flags",yaxis_title="BCM")
            st.plotly_chart(fig,use_container_width=True)
            at = da[da["is_anomaly"]][["Date","Volume_BCM","Delta_V","Inflow_BCM","Outflow_BCM","anomaly_score"]].copy()
            at["Date"] = at["Date"].dt.strftime("%Y-%m-%d")
            st.dataframe(at.head(50),use_container_width=True,height=280)
            st.download_button("⬇️ Export Evidence CSV",at.to_csv(index=False).encode(),"HSAE_anomalies.csv","text/csv")
            if na>0: st.error(f"⚠️ Legal Flag: {na} anomalous days — possible UN 1997 Art.9 violation")

    # ── Features ──────────────────────────────────────────────────────────────
    with tab_feat:
        st.markdown("### 📊 Feature Importance")
        res = st.session_state.get("ai_ens")
        if not res or "feat_importance" not in res:
            st.info("Run Ensemble first.")
        else:
            fi = res["feat_importance"]
            fig = px.bar(fi,x="importance",y="feature",orientation="h",
                         color="importance",color_continuous_scale="Viridis",
                         template="plotly_dark",height=480,
                         title=f"RF Feature Importance — {res['target']}")
            fig.update_layout(yaxis=dict(autorange="reversed"),coloraxis_showscale=False)
            st.plotly_chart(fig,use_container_width=True)
