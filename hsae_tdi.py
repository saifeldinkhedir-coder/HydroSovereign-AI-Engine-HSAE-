"""
hsae_tdi.py  ─  HSAE v6.0.0
============================
Single Source of Truth: Alkhedir Transparency Deficit Index (ATDI/TDI)
Author : Seifeldin M.G. Alkhedir — University of Khartoum
ORCID  : 0000-0003-0821-2991

ALL modules must import TDI functions from HERE — never redefine locally.
This eliminates the 3-formula inconsistency found in v5/v6.0.0.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CANONICAL FORMULA (Alkhedir 2026, accepted for RSE-2):

    I_adj  = max(0, I_in − α·(ET_PM + ET_MODIS))        [BCM/day]
    TDI    = max(0, (I_adj − Q_out) / (I_adj + ε))       [0–1]
    ATDI   = TDI × 100                                   [%]
    AFSF   = rolling_k(TDI).max() × 100                  [% peak]
    F_score= TDI × (1 + TDI_trend)                       [legal signal]

    ε     = 0.001  BCM/day  (avoids div-by-zero without biasing high flows)
    α     = 0.30   (ET partitioning coefficient, calibrated on 24 basins)
    k     = 30     (rolling window days for AFSF)

UNITS:  All flow variables in BCM/day unless noted.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
import numpy as np
import pandas as pd

# ── Canonical constants ────────────────────────────────────────────────────────
TDI_EPSILON   = 0.001   # BCM/day — denominator stabiliser
TDI_ALPHA     = 0.30    # ET partitioning coefficient
TDI_ROLL_DAYS = 30      # AFSF rolling window
TDI_ART5_THR  = 0.25    # UN Art.5 equitable utilisation threshold
TDI_ART7_THR  = 0.40    # UN Art.7 no-significant-harm threshold
TDI_ART9_THR  = 0.55    # UN Art.9 data-withholding threshold


# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def compute_i_adj(
    inflow: "pd.Series | np.ndarray",
    et_pm:  "pd.Series | np.ndarray | None" = None,
    et_mod: "pd.Series | np.ndarray | None" = None,
    alpha:  float = TDI_ALPHA,
) -> np.ndarray:
    """
    Compute ET-corrected inflow.

        I_adj = max(0, I_in − α·(ET_PM + ET_MODIS))

    Parameters
    ----------
    inflow : array-like  [BCM/day]
    et_pm  : FAO-56 Penman-Monteith ET₀ [BCM/day], optional
    et_mod : MODIS MOD16A2 actual ET [BCM/day], optional
    alpha  : partitioning coefficient (default 0.30)

    Returns
    -------
    np.ndarray  I_adj [BCM/day], non-negative
    """
    I  = np.asarray(inflow, dtype=float)
    ep = np.asarray(et_pm,  dtype=float) if et_pm  is not None else np.zeros_like(I)
    em = np.asarray(et_mod, dtype=float) if et_mod is not None else np.zeros_like(I)
    return np.clip(I - alpha * (ep + em), 0, None)


def compute_tdi(
    inflow:  "pd.Series | np.ndarray",
    outflow: "pd.Series | np.ndarray",
    et_pm:   "pd.Series | np.ndarray | None" = None,
    et_mod:  "pd.Series | np.ndarray | None" = None,
    alpha:   float = TDI_ALPHA,
    epsilon: float = TDI_EPSILON,
) -> np.ndarray:
    """
    Canonical TDI per time step.

        TDI = max(0, (I_adj − Q_out) / (I_adj + ε))   ∈ [0, 1]

    Parameters
    ----------
    inflow, outflow : array-like [BCM/day]
    et_pm, et_mod   : ET arrays [BCM/day], optional
    alpha           : ET partitioning (default 0.30)
    epsilon         : denominator stabiliser (default 0.001 BCM/day)

    Returns
    -------
    np.ndarray  TDI ∈ [0, 1]
    """
    I_adj = compute_i_adj(inflow, et_pm, et_mod, alpha)
    Q     = np.asarray(outflow, dtype=float)
    return np.clip((I_adj - Q) / (I_adj + epsilon), 0, 1)


def compute_atdi(
    inflow:  "pd.Series | np.ndarray",
    outflow: "pd.Series | np.ndarray",
    et_pm:   "pd.Series | np.ndarray | None" = None,
    et_mod:  "pd.Series | np.ndarray | None" = None,
) -> float:
    """
    Alkhedir Transparency Deficit Index — scalar summary [%].

        ATDI = mean(TDI) × 100
    """
    tdi = compute_tdi(inflow, outflow, et_pm, et_mod)
    return float(np.nanmean(tdi) * 100)


def compute_afsf(
    inflow:  "pd.Series | np.ndarray",
    outflow: "pd.Series | np.ndarray",
    et_pm:   "pd.Series | np.ndarray | None" = None,
    et_mod:  "pd.Series | np.ndarray | None" = None,
    roll:    int = TDI_ROLL_DAYS,
) -> float:
    """
    Alkhedir Forensic Signal Factor — peak rolling TDI [%].

        AFSF = max(rolling_k(TDI)) × 100
    """
    tdi = pd.Series(compute_tdi(inflow, outflow, et_pm, et_mod))
    return float(tdi.rolling(roll, min_periods=1).mean().max() * 100)


def compute_forensic_score(
    inflow:  "pd.Series | np.ndarray",
    outflow: "pd.Series | np.ndarray",
    et_pm:   "pd.Series | np.ndarray | None" = None,
    et_mod:  "pd.Series | np.ndarray | None" = None,
) -> float:
    """
    Trend-amplified legal signal.

        F_score = TDI × (1 + TDI_trend)

    Returns scalar in [0, ~2].
    """
    tdi_arr = pd.Series(compute_tdi(inflow, outflow, et_pm, et_mod))
    trend   = float(tdi_arr.diff().mean())          # daily trend
    base    = float(tdi_arr.mean())
    return float(np.clip(base * (1 + max(0, trend * 365)), 0, 2))


def add_tdi_to_df(
    df:      pd.DataFrame,
    inflow_col:  str = "Inflow_BCM",
    outflow_col: str = "Outflow_BCM",
    et_pm_col:   str = "ET0_mm_day",        # mm/day — converted internally
    et_mod_col:  str = "MODIS_ET_mm",       # mm/8day — converted internally
    area_col:    str = "Effective_Area",    # km²
) -> pd.DataFrame:
    """
    Add TDI columns to a DataFrame in-place.

    Adds: TDI_raw, TDI_adj, ATDI, AFSF, F_score,
          TDI_art5_flag, TDI_art7_flag, TDI_art9_flag

    ET columns are unit-converted using Effective_Area (km²).
    """
    df = df.copy()

    I   = df.get(inflow_col,  pd.Series(0.0, index=df.index)).fillna(0).values
    Q   = df.get(outflow_col, pd.Series(0.0, index=df.index)).fillna(0).values
    A   = df.get(area_col,    pd.Series(500.0, index=df.index)).fillna(500).values  # km²

    # ET_PM: mm/day → BCM/day using area
    et_pm_arr = None
    if et_pm_col in df.columns:
        et_pm_arr = (df[et_pm_col].fillna(0).values / 1000) * A / 1e6  # BCM/day

    # MODIS ET: mm/8day → BCM/day (divide by 8, then convert)
    et_mod_arr = None
    if et_mod_col in df.columns:
        et_mod_arr = (df[et_mod_col].fillna(0).values / 8 / 1000) * A / 1e6

    # Raw TDI (no ET correction)
    df["TDI_raw"] = compute_tdi(I, Q, epsilon=TDI_EPSILON)

    # Adjusted TDI (ET-corrected — RSE-2 canonical)
    df["TDI_adj"] = compute_tdi(I, Q, et_pm_arr, et_mod_arr)

    # TDI % for display
    df["ATDI_pct"] = df["TDI_adj"] * 100

    # Rolling forensic signal
    df["TDI_roll30"] = pd.Series(df["TDI_adj"]).rolling(30, min_periods=1).mean().values

    # Legal threshold flags
    df["TDI_art5_flag"] = (df["TDI_adj"] >= TDI_ART5_THR).astype(int)
    df["TDI_art7_flag"] = (df["TDI_adj"] >= TDI_ART7_THR).astype(int)
    df["TDI_art9_flag"] = (df["TDI_adj"] >= TDI_ART9_THR).astype(int)

    return df


def tdi_legal_status(atdi_pct: float) -> tuple[str, str, str]:
    """
    Map ATDI% to UN 1997 legal status.

    Returns (status_label, color_hex, triggered_articles)
    """
    if atdi_pct >= TDI_ART9_THR * 100:
        return "🔴 Critical — Art. 7 + 9", "#ef4444", "Art. 5, 7, 9, 12"
    elif atdi_pct >= TDI_ART7_THR * 100:
        return "🟠 Significant Harm — Art. 7", "#f97316", "Art. 5, 7"
    elif atdi_pct >= TDI_ART5_THR * 100:
        return "🟡 Equitable Use Risk — Art. 5", "#eab308", "Art. 5"
    else:
        return "🟢 Compliant", "#22c55e", "—"


def tdi_summary(df: pd.DataFrame) -> dict:
    """
    Return a summary dict of all TDI metrics for a given DataFrame.
    """
    if "TDI_adj" not in df.columns:
        return {}
    tdi = df["TDI_adj"].dropna()
    I   = df.get("Inflow_BCM",  pd.Series(dtype=float)).fillna(0)
    Q   = df.get("Outflow_BCM", pd.Series(dtype=float)).fillna(0)
    atdi = float(tdi.mean() * 100)
    afsf = float(tdi.rolling(30, min_periods=1).mean().max() * 100)
    trend= float(tdi.diff().mean() * 365 * 100)   # %/year
    status, color, arts = tdi_legal_status(atdi)
    return {
        "ATDI_pct":       round(atdi, 2),
        "ATDI_max_pct":   round(float(tdi.max() * 100), 2),
        "ATDI_p75_pct":   round(float(tdi.quantile(0.75) * 100), 2),
        "AFSF_pct":       round(afsf, 2),
        "TDI_trend_pct_yr": round(trend, 3),
        "art5_days":      int((tdi >= TDI_ART5_THR).sum()),
        "art7_days":      int((tdi >= TDI_ART7_THR).sum()),
        "art9_days":      int((tdi >= TDI_ART9_THR).sum()),
        "legal_status":   status,
        "legal_color":    color,
        "triggered_arts": arts,
        "n_days":         len(tdi),
    }
