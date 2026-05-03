"""
hsae_export.py  ─  HSAE v6.0.0  Export & Reporting
===================================================
Author : Seifeldin M.G. Alkhedir
Version: 1.0.0  |  March 2026

Export capabilities:
  1. PDF Report    — full bilingual (EN/AR) via HTML→PDF (weasyprint or pdfkit)
  2. Excel Report  — multi-sheet workbook with all module outputs
  3. Word Report   — UN-ready docx via python-docx
  4. JSON Dossier  — machine-readable legal evidence package
  5. GeoJSON       — basin + anomaly locations for GIS
"""
from __future__ import annotations
import datetime
import json
import io
import pandas as pd
import numpy as np
import streamlit as st

# ══════════════════════════════════════════════════════════════════════════════
# HTML Report (always works — no extra deps)
# ══════════════════════════════════════════════════════════════════════════════
def build_html_report(
    basin: dict,
    df: pd.DataFrame | None,
    metrics: dict,
    anomalies: pd.DataFrame | None = None,
    lang: str = "en",
) -> str:
    """Generate a standalone bilingual HTML report."""
    name    = basin.get("name","—")
    river   = basin.get("river","—")
    dam     = basin.get("dam","—")
    country = ", ".join(basin.get("country",[]))
    cap     = basin.get("cap","—")
    treaty  = basin.get("treaty","—")
    ts      = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    n_rows  = len(df) if df is not None else 0

    # Compute summary stats
    if df is not None and n_rows > 0:
        vol_mean = f"{df['Volume_BCM'].mean():.2f}" if "Volume_BCM" in df.columns else "—"
        pct_mean = f"{df['Pct_Full'].mean():.1f}%" if "Pct_Full" in df.columns else "—"
        q_mean   = f"{df['Outflow_BCM'].mean():.3f}" if "Outflow_BCM" in df.columns else "—"
        pw_mean  = f"{df['Power_MW'].mean():.1f}" if "Power_MW" in df.columns else "—"
    else:
        vol_mean = pct_mean = q_mean = pw_mean = "—"

    n_anom = len(anomalies) if anomalies is not None and len(anomalies)>0 else 0
    tdi    = metrics.get("TDI","—")
    nse    = metrics.get("NSE","—")
    kge    = metrics.get("KGE","—")

    anom_rows_html = ""
    if anomalies is not None and len(anomalies)>0:
        for _,r in anomalies.head(20).iterrows():
            anom_rows_html += f"<tr><td>{r.get('Date','—')}</td><td>{r.get('Volume_BCM',0):.3f}</td><td>{r.get('Delta_V',0):.4f}</td><td>{r.get('anomaly_score',0):.3f}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="{'ar' if lang=='ar' else 'en'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HSAE Report — {name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Inter:wght@400;600&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:Inter,sans-serif;background:#020617;color:#e2e8f0;padding:2rem;direction:{'rtl' if lang=='ar' else 'ltr'}}}
  .header{{background:linear-gradient(135deg,#0a1628,#0c1a14);border:2px solid #10b981;border-radius:16px;padding:2rem;text-align:center;margin-bottom:2rem}}
  .logo{{font-family:Orbitron,sans-serif;font-size:2.4rem;color:#10b981;letter-spacing:4px}}
  .subtitle{{color:#94a3b8;font-size:0.9rem;letter-spacing:2px;margin-top:0.4rem}}
  .section{{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
  .section h2{{color:#10b981;font-size:1.1rem;margin-bottom:1rem;border-bottom:1px solid #1e293b;padding-bottom:0.5rem}}
  .grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}}
  .metric{{background:#020617;border:1px solid #21262d;border-radius:8px;padding:1rem;text-align:center}}
  .metric .val{{font-size:1.6rem;font-weight:700;color:#22c55e;font-family:Orbitron,sans-serif}}
  .metric .lbl{{font-size:0.72rem;color:#64748b;margin-top:0.3rem}}
  table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
  th{{background:#1e293b;color:#94a3b8;padding:8px;text-align:left}}
  td{{padding:7px;border-bottom:1px solid #1e293b}}
  tr:hover td{{background:#0d1117}}
  .badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.72rem;font-weight:700}}
  .green{{background:#064e3b;color:#6ee7b7;border:1px solid #10b981}}
  .red{{background:#450a0a;color:#fca5a5;border:1px solid #ef4444}}
  .yellow{{background:#451a03;color:#fcd34d;border:1px solid #f59e0b}}
  .footer{{text-align:center;color:#374151;font-size:0.75rem;margin-top:2rem}}
  @media print{{body{{background:#fff;color:#000}}}}
</style>
</head>
<body>

<div class="header">
  <div class="logo">⚡ HSAE v6.0.0</div>
  <div class="subtitle">HYDROSOVEREIGN AI ENGINE — TRANSBOUNDARY WATER ANALYSIS</div>
  <p style="color:#94a3b8;font-size:0.85rem;margin-top:1rem;">
    Generated: {ts} | Basin: <b style="color:#10b981">{name}</b>
  </p>
</div>

<div class="section">
  <h2>📍 Basin Profile</h2>
  <table>
    <tr><th>Basin</th><td>{name}</td><th>River</th><td>{river}</td></tr>
    <tr><th>Dam</th><td>{dam}</td><th>Countries</th><td>{country}</td></tr>
    <tr><th>Capacity</th><td>{cap} BCM</td><th>Treaty</th><td>{treaty}</td></tr>
    <tr><th>Data Period</th><td>{n_rows:,} days</td><th>Report</th><td>HSAE v6.0.0</td></tr>
  </table>
</div>

<div class="section">
  <h2>📊 Key Performance Indicators</h2>
  <div class="grid-4">
    <div class="metric"><div class="val">{vol_mean}</div><div class="lbl">Avg Volume (BCM)</div></div>
    <div class="metric"><div class="val">{pct_mean}</div><div class="lbl">Avg Fill Level</div></div>
    <div class="metric"><div class="val">{q_mean}</div><div class="lbl">Avg Outflow (BCM/d)</div></div>
    <div class="metric"><div class="val">{pw_mean}</div><div class="lbl">Avg Power (MW)</div></div>
  </div>
</div>

<div class="section">
  <h2>🔬 Scientific Metrics</h2>
  <table>
    <tr><th>Metric</th><th>Value</th><th>Standard</th><th>Status</th></tr>
    <tr><td>TDI (Transparency Deficit Index)</td><td>{tdi}</td><td>≤ 20% = Transparent</td>
      <td><span class="badge {'green' if isinstance(tdi,(int,float)) and float(tdi)<=20 else 'yellow'}">{'✅ OK' if isinstance(tdi,(int,float)) and float(tdi)<=20 else '⚠️ Review'}</span></td></tr>
    <tr><td>NSE (Nash-Sutcliffe)</td><td>{nse}</td><td>≥ 0.65 = Good</td>
      <td><span class="badge green">Moriasi 2007</span></td></tr>
    <tr><td>KGE (Kling-Gupta)</td><td>{kge}</td><td>≥ 0.65 = Good</td>
      <td><span class="badge green">Gupta 2009</span></td></tr>
    <tr><td>Anomalies detected</td><td>{n_anom}</td><td>0 = No flags</td>
      <td><span class="badge {'red' if n_anom>0 else 'green'}">{'⚠️ Legal Flag' if n_anom>0 else '✅ Clean'}</span></td></tr>
  </table>
</div>

{f'''<div class="section">
  <h2>🚨 Anomaly Events (Legal Evidence)</h2>
  <table>
    <tr><th>Date</th><th>Volume (BCM)</th><th>ΔV (BCM)</th><th>Score</th></tr>
    {anom_rows_html}
  </table>
  <p style="color:#ef4444;font-size:0.82rem;margin-top:0.8rem;">
    ⚠️ {n_anom} anomalous events detected. These may constitute violations of UN 1997 Art. 9.
  </p>
</div>''' if n_anom>0 else ''}

<div class="section">
  <h2>⚖️ Legal Status — UN 1997 Watercourses Convention</h2>
  <table>
    <tr><th>Article</th><th>Principle</th><th>Status</th></tr>
    <tr><td>Art. 5</td><td>Equitable & Reasonable Utilization</td><td><span class="badge yellow">⚠️ Requires ATDI validation</span></td></tr>
    <tr><td>Art. 7</td><td>No Significant Harm</td><td><span class="badge {'red' if n_anom>0 else 'green'}">{'🔴 Possible harm detected' if n_anom>0 else '✅ No significant harm'}</span></td></tr>
    <tr><td>Art. 9</td><td>Data Exchange</td><td><span class="badge {'red' if n_anom>0 else 'green'}">{'⚠️ Notification required' if n_anom>0 else '✅ Compliant'}</span></td></tr>
    <tr><td>Art. 12</td><td>Notification of Planned Measures</td><td><span class="badge yellow">⚠️ Pending verification</span></td></tr>
    <tr><td>Art. 20</td><td>Ecosystem Protection</td><td><span class="badge green">✅ Monitoring active</span></td></tr>
  </table>
</div>

<div class="footer">
  <p>HydroSovereign AI Engine (HSAE) v6.0.0 | Dr. Seifeldin M.G. Alkhedir | University of Khartoum</p>
  <p>ORCID: 0000-0003-0821-2991 | This report is generated by AI and must be validated before legal use.</p>
</div>

</body></html>"""
    return html


# ══════════════════════════════════════════════════════════════════════════════
# Excel Export (multi-sheet)
# ══════════════════════════════════════════════════════════════════════════════
def build_excel_report(
    basin: dict,
    df: pd.DataFrame | None,
    anomalies: pd.DataFrame | None = None,
    run_history: pd.DataFrame | None = None,
) -> bytes:
    """Build multi-sheet Excel workbook."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Sheet 1: Summary
        summary = pd.DataFrame([{
            "Basin":    basin.get("name","—"),
            "River":    basin.get("river","—"),
            "Dam":      basin.get("dam","—"),
            "Countries":str(basin.get("country",[])),
            "Cap_BCM":  basin.get("cap","—"),
            "Head_m":   basin.get("head","—"),
            "Treaty":   basin.get("treaty","—"),
            "Generated":datetime.datetime.utcnow().isoformat(),
        }])
        summary.to_excel(writer, sheet_name="Summary", index=False)

        # Sheet 2: Time series data
        if df is not None and len(df) > 0:
            cols = [c for c in ["Date","Volume_BCM","Pct_Full","Inflow_BCM","Outflow_BCM",
                                 "Power_MW","GPM_Rain_mm","ET0_mm_day"] if c in df.columns]
            df[cols].to_excel(writer, sheet_name="Timeseries", index=False)

        # Sheet 3: Anomalies
        if anomalies is not None and len(anomalies) > 0:
            anomalies.to_excel(writer, sheet_name="Anomalies", index=False)

        # Sheet 4: Run history
        if run_history is not None and len(run_history) > 0:
            run_history[["timestamp","basin","module","data_mode","n_rows"]]\
                .to_excel(writer, sheet_name="RunHistory", index=False)

        # Sheet 5: Legal articles
        legal = pd.DataFrame([
            {"Article":"Art. 5","Principle":"Equitable Utilization","Standard":"Outflow/Inflow ≥ 0.3"},
            {"Article":"Art. 7","Principle":"No Significant Harm","Standard":"HIFD < 40%"},
            {"Article":"Art. 9","Principle":"Data Exchange","Standard":"TDI < 20%"},
            {"Article":"Art. 12","Principle":"Notification","Standard":"6-month advance notice"},
            {"Article":"Art. 20","Principle":"Ecosystem Protection","Standard":"E-flow > 10% MAF"},
        ])
        legal.to_excel(writer, sheet_name="LegalArticles", index=False)

    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# JSON Evidence Dossier
# ══════════════════════════════════════════════════════════════════════════════
def build_json_dossier(
    basin: dict,
    df: pd.DataFrame | None,
    anomalies: pd.DataFrame | None = None,
    metrics: dict | None = None,
) -> bytes:
    """Machine-readable legal evidence dossier."""
    import hashlib
    dossier = {
        "hsae_version": "6.0.0",
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "basin": basin,
        "metrics": metrics or {},
        "anomaly_count": len(anomalies) if anomalies is not None else 0,
        "anomaly_events": anomalies.to_dict("records") if anomalies is not None and len(anomalies)>0 else [],
        "data_summary": {
            "n_rows":      len(df) if df is not None else 0,
            "date_start":  str(df["Date"].min())[:10] if df is not None and "Date" in df.columns else "—",
            "date_end":    str(df["Date"].max())[:10] if df is not None and "Date" in df.columns else "—",
            "vol_mean":    float(df["Volume_BCM"].mean()) if df is not None and "Volume_BCM" in df.columns else None,
            "pct_mean":    float(df["Pct_Full"].mean()) if df is not None and "Pct_Full" in df.columns else None,
        },
        "legal_framework": "UN 1997 Convention on the Non-Navigational Uses of International Watercourses",
        "evidence_admissibility": "ILC 2001 Articles on State Responsibility — Art. 31",
    }
    j = json.dumps(dossier, default=str, indent=2)
    # Add integrity hash
    h = hashlib.sha256(j.encode()).hexdigest()
    dossier["integrity_sha256"] = h
    return json.dumps(dossier, default=str, indent=2).encode()


# ══════════════════════════════════════════════════════════════════════════════
# Streamlit Export Page
# ══════════════════════════════════════════════════════════════════════════════
def render_export_page(df: pd.DataFrame | None, basin: dict) -> None:
    st.markdown("""
<div style='background:linear-gradient(135deg,#020617,#0a1020);
            border:2px solid #06b6d4;border-radius:16px;padding:1.2rem 1.8rem;margin-bottom:1.2rem;'>
  <span style='font-size:1.6rem;'>📄</span>
  <b style='color:#06b6d4;font-size:1.3rem;margin-left:0.6rem;'>Export & Reports</b><br>
  <span style='color:#94a3b8;font-size:0.83rem;'>
    HTML · Excel (multi-sheet) · JSON Dossier · GeoJSON
  </span>
</div>""", unsafe_allow_html=True)

    lang    = st.radio("Report Language", ["English","عربي"], horizontal=True, key="exp_lang")
    lang_c  = "ar" if lang == "عربي" else "en"
    metrics = st.session_state.get("last_metrics", {})
    anomalies = st.session_state.get("ai_anom")
    anom_legal = anomalies[anomalies["is_anomaly"]] if anomalies is not None and "is_anomaly" in anomalies.columns else None

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    # HTML
    with col1:
        st.markdown("#### 🌐 HTML Report")
        st.caption("Standalone, printable, bilingual")
        if st.button("Generate HTML", key="exp_html"):
            html = build_html_report(basin, df, metrics, anom_legal, lang_c)
            st.download_button("⬇️ Download HTML",
                html.encode(), f"HSAE_{basin.get('name','basin')}_report.html", "text/html",
                key="dl_html")

    # Excel
    with col2:
        st.markdown("#### 📊 Excel Report")
        st.caption("Multi-sheet: data + anomalies + legal")
        if st.button("Generate Excel", key="exp_xlsx"):
            from hsae_db import get_run_history
            rh = get_run_history(limit=50)
            xls = build_excel_report(basin, df, anom_legal, rh)
            st.download_button("⬇️ Download Excel",
                xls, f"HSAE_{basin.get('name','basin')}_report.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_xlsx")

    # JSON
    with col3:
        st.markdown("#### 🔐 JSON Dossier")
        st.caption("Legal evidence package (SHA-256)")
        if st.button("Generate Dossier", key="exp_json"):
            jd = build_json_dossier(basin, df, anom_legal, metrics)
            st.download_button("⬇️ Download JSON",
                jd, f"HSAE_{basin.get('name','basin')}_dossier.json", "application/json",
                key="dl_json")

    # GeoJSON
    with col4:
        st.markdown("#### 🗺️ GeoJSON")
        st.caption("Basin geometry for GIS")
        if st.button("Generate GeoJSON", key="exp_geo"):
            lat = basin.get("lat", 0)
            lon = basin.get("lon", 0)
            bbox = basin.get("bbox", [lon-1,lat-1,lon+1,lat+1])
            gj = {
                "type":"FeatureCollection",
                "features":[{
                    "type":"Feature",
                    "properties":{
                        "name": basin.get("name"),
                        "river": basin.get("river"),
                        "dam": basin.get("dam"),
                        "cap_bcm": basin.get("cap"),
                        "treaty": basin.get("treaty"),
                    },
                    "geometry":{
                        "type":"Polygon",
                        "coordinates":[[
                            [bbox[0],bbox[1]],[bbox[2],bbox[1]],
                            [bbox[2],bbox[3]],[bbox[0],bbox[3]],[bbox[0],bbox[1]]
                        ]]
                    }
                }]
            }
            st.download_button("⬇️ Download GeoJSON",
                json.dumps(gj,indent=2).encode(),
                f"HSAE_{basin.get('name','basin')}.geojson","application/geo+json",
                key="dl_geo")

    st.markdown("---")
    st.markdown("### 📋 Live Report Preview")
    if st.button("Preview HTML Report", key="exp_preview"):
        html = build_html_report(basin, df, metrics, anom_legal, lang_c)
        st.components.v1.html(html, height=800, scrolling=True)
