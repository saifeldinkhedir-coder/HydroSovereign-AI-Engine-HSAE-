"""
hsae_db.py  ─  HSAE v6.0.0  Persistent Database (SQLite)
=========================================================
Author : Seifeldin M.G. Alkhedir
Version: 1.0.0  |  March 2026

Zero-config SQLite database for:
  1. Run history  — every model run saved with timestamp + metrics
  2. Basin cache  — real data cached to avoid re-fetching
  3. Audit log    — persistent across sessions (replaces in-memory log)
  4. Reports      — saved HTML/JSON reports

All data survives app restart. No PostgreSQL required for local use.
"""
from __future__ import annotations
import sqlite3
import json
import datetime
import hashlib
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path

# ── Database path ─────────────────────────────────────────────────────────────
DB_PATH = Path("hsae_data.db")

# ══════════════════════════════════════════════════════════════════════════════
# DB Connection & Schema
# ══════════════════════════════════════════════════════════════════════════════
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_conn()
    c    = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS run_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            basin       TEXT NOT NULL,
            module      TEXT NOT NULL,
            data_mode   TEXT,
            n_rows      INTEGER,
            metrics     TEXT,    -- JSON
            sha256      TEXT
        );

        CREATE TABLE IF NOT EXISTS basin_cache (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            basin       TEXT NOT NULL,
            start_date  TEXT,
            end_date    TEXT,
            source      TEXT,
            fetched_at  TEXT,
            n_rows      INTEGER,
            df_json     TEXT     -- DataFrame as JSON
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            user_role   TEXT,
            action      TEXT NOT NULL,
            basin       TEXT,
            details     TEXT,
            sha256      TEXT
        );

        CREATE TABLE IF NOT EXISTS reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            basin       TEXT,
            report_type TEXT,
            title       TEXT,
            content     TEXT
        );

        CREATE TABLE IF NOT EXISTS anomaly_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            basin       TEXT NOT NULL,
            event_date  TEXT NOT NULL,
            volume_bcm  REAL,
            delta_v     REAL,
            score       REAL,
            legal_flag  INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()

def _sha(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]

# ══════════════════════════════════════════════════════════════════════════════
# Run History
# ══════════════════════════════════════════════════════════════════════════════
def save_run(basin: str, module: str, data_mode: str, n_rows: int, metrics: dict) -> None:
    ts   = datetime.datetime.utcnow().isoformat()
    mj   = json.dumps(metrics)
    sha  = _sha(f"{ts}{basin}{module}{mj}")
    conn = get_conn()
    conn.execute(
        "INSERT INTO run_history (timestamp,basin,module,data_mode,n_rows,metrics,sha256) VALUES (?,?,?,?,?,?,?)",
        (ts, basin, module, data_mode, n_rows, mj, sha)
    )
    conn.commit(); conn.close()

def get_run_history(basin: str | None = None, limit: int = 100) -> pd.DataFrame:
    conn = get_conn()
    if basin:
        rows = conn.execute(
            "SELECT * FROM run_history WHERE basin=? ORDER BY id DESC LIMIT ?",
            (basin, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM run_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    if not rows: return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["metrics_parsed"] = df["metrics"].apply(lambda x: json.loads(x) if x else {})
    return df

# ══════════════════════════════════════════════════════════════════════════════
# Basin Data Cache
# ══════════════════════════════════════════════════════════════════════════════
def cache_basin_data(basin: str, start: str, end: str, source: str, df_data: pd.DataFrame) -> None:
    """Cache fetched real data to avoid repeated API calls."""
    ts   = datetime.datetime.utcnow().isoformat()
    try:
        dj   = df_data.to_json(date_format="iso", orient="records")
        conn = get_conn()
        # Delete old cache for same basin+dates
        conn.execute("DELETE FROM basin_cache WHERE basin=? AND start_date=? AND end_date=?",
                     (basin, start, end))
        conn.execute(
            "INSERT INTO basin_cache (basin,start_date,end_date,source,fetched_at,n_rows,df_json) VALUES (?,?,?,?,?,?,?)",
            (basin, start, end, source, ts, len(df_data), dj)
        )
        conn.commit(); conn.close()
    except Exception:
        pass

def load_basin_cache(basin: str, start: str, end: str) -> pd.DataFrame | None:
    """Load cached data if available and < 24h old."""
    try:
        conn  = get_conn()
        row   = conn.execute(
            "SELECT * FROM basin_cache WHERE basin=? AND start_date=? AND end_date=? ORDER BY id DESC LIMIT 1",
            (basin, start, end)
        ).fetchone()
        conn.close()
        if not row: return None
        fetched = datetime.datetime.fromisoformat(row["fetched_at"])
        age_h   = (datetime.datetime.utcnow() - fetched).total_seconds() / 3600
        if age_h > 24: return None   # expired
        df = pd.read_json(row["df_json"], orient="records")
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        return df
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════
# Audit Log (persistent)
# ══════════════════════════════════════════════════════════════════════════════
def log_action(action: str, basin: str = "—", details: str = "", role: str = "Guest") -> None:
    ts   = datetime.datetime.utcnow().isoformat()
    sha  = _sha(f"{ts}{action}{basin}{details}")
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log (timestamp,user_role,action,basin,details,sha256) VALUES (?,?,?,?,?,?)",
        (ts, role, action, basin, details, sha)
    )
    conn.commit(); conn.close()

def get_audit_log(limit: int = 500) -> pd.DataFrame:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

# ══════════════════════════════════════════════════════════════════════════════
# Anomaly Events
# ══════════════════════════════════════════════════════════════════════════════
def save_anomalies(basin: str, df_anom: pd.DataFrame) -> int:
    """Save detected anomalies to DB. Returns count saved."""
    if df_anom is None or len(df_anom) == 0: return 0
    anom = df_anom[df_anom["is_anomaly"]].copy() if "is_anomaly" in df_anom.columns else pd.DataFrame()
    if len(anom) == 0: return 0
    ts   = datetime.datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute("DELETE FROM anomaly_events WHERE basin=?", (basin,))
    for _, row in anom.iterrows():
        conn.execute(
            "INSERT INTO anomaly_events (timestamp,basin,event_date,volume_bcm,delta_v,score,legal_flag) VALUES (?,?,?,?,?,?,?)",
            (ts, basin, str(row.get("Date",""))[:10],
             float(row.get("Volume_BCM",0)), float(row.get("Delta_V",0)),
             float(row.get("anomaly_score",0)), 1)
        )
    conn.commit(); conn.close()
    return len(anom)

def get_anomaly_events(basin: str | None = None) -> pd.DataFrame:
    conn = get_conn()
    if basin:
        rows = conn.execute("SELECT * FROM anomaly_events WHERE basin=? ORDER BY event_date DESC", (basin,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM anomaly_events ORDER BY event_date DESC").fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

# ══════════════════════════════════════════════════════════════════════════════
# Streamlit DB Management Page
# ══════════════════════════════════════════════════════════════════════════════
def render_db_page() -> None:
    init_db()
    st.markdown("""
<div style='background:linear-gradient(135deg,#020617,#0a1020);
            border:2px solid #06b6d4;border-radius:16px;padding:1.2rem 1.8rem;margin-bottom:1.2rem;'>
  <span style='font-size:1.6rem;'>🗄️</span>
  <b style='color:#06b6d4;font-size:1.3rem;margin-left:0.6rem;'>Persistent Database</b><br>
  <span style='color:#94a3b8;font-size:0.83rem;'>
    SQLite · Run History · Data Cache · Audit Log · Anomaly Events
  </span>
</div>""", unsafe_allow_html=True)

    tab_hist, tab_cache, tab_audit, tab_anom = st.tabs(
        ["📜 Run History","💾 Data Cache","🔐 Audit Log","🚨 Anomaly Events"])

    with tab_hist:
        st.markdown("### 📜 Model Run History")
        df_h = get_run_history(limit=200)
        if df_h.empty:
            st.info("No runs recorded yet. Run any module to start logging.")
        else:
            st.metric("Total runs", len(df_h))
            st.dataframe(df_h[["timestamp","basin","module","data_mode","n_rows","sha256"]],
                         use_container_width=True, height=400)
            st.download_button("⬇️ Export Run History",
                df_h.to_csv(index=False).encode(),"hsae_run_history.csv","text/csv")

    with tab_cache:
        st.markdown("### 💾 Cached Real Data")
        conn = get_conn()
        rows = conn.execute("SELECT id,basin,start_date,end_date,source,fetched_at,n_rows FROM basin_cache ORDER BY id DESC").fetchall()
        conn.close()
        if not rows:
            st.info("No cached data yet.")
        else:
            df_c = pd.DataFrame([dict(r) for r in rows])
            st.metric("Cached datasets", len(df_c))
            st.dataframe(df_c, use_container_width=True, height=300)
            if st.button("🗑️ Clear All Cache", key="db_clear_cache"):
                conn = get_conn(); conn.execute("DELETE FROM basin_cache"); conn.commit(); conn.close()
                st.success("Cache cleared."); st.rerun()

    with tab_audit:
        st.markdown("### 🔐 Persistent Audit Log")
        df_a = get_audit_log(500)
        if df_a.empty:
            st.info("No audit events yet.")
        else:
            st.metric("Total events", len(df_a))
            st.dataframe(df_a, use_container_width=True, height=400)
            st.download_button("⬇️ Export Audit Log",
                df_a.to_csv(index=False).encode(),"hsae_audit_persistent.csv","text/csv")

    with tab_anom:
        st.markdown("### 🚨 Persistent Anomaly Events")
        df_an = get_anomaly_events()
        if df_an.empty:
            st.info("No anomalies saved yet. Run AI Anomaly Detection to populate.")
        else:
            n_lf = df_an["legal_flag"].sum() if "legal_flag" in df_an.columns else 0
            c1,c2 = st.columns(2)
            c1.metric("Total anomalies", len(df_an))
            c2.metric("Legal flags", int(n_lf))
            st.dataframe(df_an, use_container_width=True, height=400)
            st.download_button("⬇️ Export for Legal Dossier",
                df_an.to_csv(index=False).encode(),"hsae_anomalies_legal.csv","text/csv")

    # DB stats
    st.markdown("---")
    st.markdown("### 📊 Database Statistics")
    conn = get_conn()
    tables = ["run_history","basin_cache","audit_log","reports","anomaly_events"]
    cols_s = st.columns(len(tables))
    for col_s, t in zip(cols_s, tables):
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            n = 0
        col_s.metric(t, n)
    conn.close()

    db_size = DB_PATH.stat().st_size / 1024 if DB_PATH.exists() else 0
    st.caption(f"Database: `{DB_PATH}` — {db_size:.1f} KB")
