"""
ground_data.py  ─  HSAE v6.0.0  (compatibility shim)
======================================================
This module is kept for backward compatibility only.
All actual logic has been consolidated into hsae_gee_data.py (v6).
New code should import directly from hsae_gee_data.

Author : Seifeldin M.G. Alkhedir
"""
from __future__ import annotations
import warnings
import pandas as pd

from hsae_gee_data import (
    fetch_open_meteo,
    fetch_glofas,
    fetch_usgs,
    fetch_grace,
    parse_grdc_csv,
    render_real_data_panel,
    merge_all_gee_layers,
)
from basins_global import GLOBAL_BASINS

# BASIN_SOURCES is now derived directly from GLOBAL_BASINS
BASIN_SOURCES = {
    name: {
        "glofas_lat": cfg.get("glofas_lat", cfg["lat"]),
        "glofas_lon": cfg.get("glofas_lon", cfg["lon"]),
        "meteo_lat":  cfg.get("meteo_lat",  cfg["lat"]),
        "meteo_lon":  cfg.get("meteo_lon",  cfg["lon"]),
        "usgs_id":    cfg.get("usgs_id"),
        "grdc_id":    cfg.get("grdc_id"),
    }
    for name, cfg in GLOBAL_BASINS.items()
}


def build_real_df(
    basin_name: str,
    start: str = "2020-01-01",
    end: str   = "2024-12-31",
) -> pd.DataFrame | None:
    """
    Fetch real data for a basin using live APIs.
    Wrapper around hsae_gee_data functions.
    Returns merged DataFrame compatible with all HSAE modules.
    """
    cfg = GLOBAL_BASINS.get(basin_name)
    if cfg is None:
        return None

    lat = cfg.get("glofas_lat", cfg["lat"])
    lon = cfg.get("glofas_lon", cfg["lon"])

    meteo = fetch_open_meteo(lat, lon, start, end)
    if meteo is None:
        return None

    usgs_id = cfg.get("usgs_id")
    q_df = fetch_usgs(usgs_id, start, end) if usgs_id else fetch_glofas(lat, lon, start, end)
    grace = fetch_grace(lat, lon)

    df = meteo.rename(columns={"GPM_Rain_mm": "GPM_Rain_mm"}).copy()
    if q_df is not None:
        q_df["Date"] = pd.to_datetime(q_df["Date"]).dt.normalize()
        df = df.merge(q_df[["Date","Q_BCM_day"]], on="Date", how="left")
        df.rename(columns={"Q_BCM_day": "Outflow_BCM"}, inplace=True)
    if grace is not None:
        grace["Date"] = pd.to_datetime(grace["Date"])
        gmap = grace.set_index("Date")["TWS_cm"].to_dict()
        df["_m"] = df["Date"].dt.to_period("M").dt.to_timestamp()
        df["TWS_cm"] = df["_m"].map(gmap)
        df.drop(columns=["_m"], inplace=True)

    return df


def render_ground_data_panel(basin_name: str, basin: dict, **kwargs) -> pd.DataFrame | None:
    """Backward-compat alias → render_real_data_panel."""
    warnings.warn(
        "render_ground_data_panel is deprecated; use render_real_data_panel from hsae_gee_data",
        DeprecationWarning, stacklevel=2
    )
    return render_real_data_panel(basin_name, basin)
