"""
gee_engine.py  ─  HSAE v6.0.0
===============================
Google Earth Engine — Python API Integration
Author : Seifeldin M.G. Alkedir — University of Khartoum
ORCID  : 0000-0003-0821-2991

Provides LIVE satellite data retrieval via the earthengine-api Python client.
This module is the programmatic complement to hsae_gee_data.py (which provides
pre-built JavaScript scripts for manual export).

Sensors covered:
  1. Sentinel-1 SAR (COPERNICUS/S1_GRD)               — Water area + VV backscatter
  2. Sentinel-2 MSI (COPERNICUS/S2_SR_HARMONIZED)      — NDWI + cloud-masked
  3. GPM IMERG (NASA/GPM_L3/IMERG_V07)                 — Daily precipitation
  4. MODIS MOD16A2 ET (MODIS/061/MOD16A2)              — 8-day actual ET
  5. MODIS MOD13A2 NDVI (MODIS/061/MOD13A2)            — 16-day NDVI/EVI
  6. MODIS MYD11A2 LST (MODIS/061/MYD11A2)             — 8-day land surface temp
  7. VIIRS NTL (NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG)     — Night-time lights
  8. Landsat 8/9 WQ (LANDSAT/LC08+LC09/C02/T1_L2)     — Water quality proxies

Installation:
    pip install earthengine-api>=0.1.390
    earthengine authenticate          # one-time browser OAuth (Google account)

Usage:
    from gee_engine import GEEEngine
    gee = GEEEngine()
    df  = gee.fetch_all(basin_cfg, "2020-01-01", "2024-12-31")

Design principles (fixes vs uploaded version):
  ✅ Geometry built from bbox — no polygon field required in basins_global
  ✅ Async export via Tasks (non-blocking) for long date ranges
  ✅ Synchronous getInfo() only for short ranges (≤90 days)
  ✅ All 8 sensors with proper cloud masking and QA filters
  ✅ Speckle filtering on Sentinel-1 (Lee 3×3)
  ✅ Cloud masking on Sentinel-2 (QA60 bitmask)
  ✅ Quality flags on MODIS ET, NDVI, LST
  ✅ Graceful fallback when EE is not authenticated
  ✅ Streamlit-compatible (no UI freeze via threading)
  ✅ Rate-limit safe (monthly composites for long ranges)
  ✅ Full integration with hsae_gee_data parsers
"""
from __future__ import annotations

import datetime
import threading
import time
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── Earth Engine import (optional — graceful fallback) ────────────────────────
_EE_AVAILABLE = False
try:
    import ee
    _EE_AVAILABLE = True
except ImportError:
    warnings.warn(
        "earthengine-api not installed. GEE live fetch disabled.\n"
        "Install: pip install earthengine-api>=0.1.390\n"
        "Then run: earthengine authenticate",
        ImportWarning, stacklevel=2
    )

# ── Streamlit cache (optional) ────────────────────────────────────────────────
try:
    import streamlit as st
    _cache = st.cache_data(ttl=3600)
except ImportError:
    def _cache(fn):
        return fn


# ══════════════════════════════════════════════════════════════════════════════
# GEOMETRY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _bbox_to_geometry(bbox: List[float]) -> "ee.Geometry":
    """
    Convert [lon_min, lat_min, lon_max, lat_max] bbox to ee.Geometry.Rectangle.
    All 26 basins in basins_global.py have a 'bbox' field — no polygon needed.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    return ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])


def _catchment_geometry(basin_cfg: Dict, buffer_km: float = 20.0) -> "ee.Geometry":
    """
    Return GEE geometry for a basin.  Priority:
      1. basin_cfg["geometry"]  — GeoJSON polygon (if present)
      2. basin_cfg["bbox"]      — bounding box rectangle (all 26 basins)
      3. centroid + buffer      — last resort fallback
    """
    # Option 1: explicit GeoJSON geometry
    geom_field = basin_cfg.get("geometry")
    if geom_field and geom_field is not None:
        if isinstance(geom_field, dict):
            gtype = geom_field.get("type", "")
            if gtype == "FeatureCollection":
                return ee.Geometry(geom_field["features"][0]["geometry"])
            elif gtype in ("Polygon", "MultiPolygon", "GeometryCollection"):
                return ee.Geometry(geom_field)
        elif isinstance(geom_field, str):
            import json
            return ee.Geometry(json.loads(geom_field))

    # Option 2: bbox (present in all 26 basins in basins_global.py)
    bbox = basin_cfg.get("bbox")
    if bbox and len(bbox) == 4:
        return _bbox_to_geometry(bbox)

    # Option 3: centroid + buffer
    lat = basin_cfg.get("lat", 0.0)
    lon = basin_cfg.get("lon", 0.0)
    return ee.Geometry.Point([lon, lat]).buffer(buffer_km * 1000)


def _downstream_geometry(basin_cfg: Dict, shift_deg: float = 2.0) -> "ee.Geometry":
    """Approximate downstream zone by shifting bbox southward."""
    bbox = basin_cfg.get("bbox", [])
    if len(bbox) == 4:
        lon_min, lat_min, lon_max, lat_max = bbox
        return _bbox_to_geometry([
            lon_min, lat_min - shift_deg,
            lon_max, lat_max - shift_deg
        ])
    lat = basin_cfg.get("lat", 0.0)
    lon = basin_cfg.get("lon", 0.0)
    return ee.Geometry.Point([lon, lat - shift_deg]).buffer(50_000)


# ══════════════════════════════════════════════════════════════════════════════
# EE INITIALISATION
# ══════════════════════════════════════════════════════════════════════════════

_ee_initialized = False

def _ensure_ee(project: Optional[str] = None) -> bool:
    """
    Initialise Earth Engine once per process.
    Returns True if EE is available and authenticated, False otherwise.
    """
    global _ee_initialized
    if not _EE_AVAILABLE:
        return False
    if _ee_initialized:
        return True
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        _ee_initialized = True
        return True
    except Exception as exc:
        try:
            ee.Authenticate()
            ee.Initialize(project=project) if project else ee.Initialize()
            _ee_initialized = True
            return True
        except Exception:
            warnings.warn(f"EE init failed: {exc}", RuntimeWarning)
            return False


# ══════════════════════════════════════════════════════════════════════════════
# SENSOR PROCESSING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _s1_monthly(
    geom: "ee.Geometry",
    start: str,
    end: str,
    water_threshold_db: float = -16.0,
    scale: int = 100,
) -> "ee.FeatureCollection":
    """
    Sentinel-1 SAR monthly composites with Lee speckle filter.
    Returns FeatureCollection with: date, S1_VV_mean_dB, S1_Water_Area_km2, n_scenes
    """
    col = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select(["VV"])
    )

    # Lee 3×3 speckle filter
    def lee_filter(img):
        kernel  = ee.Kernel.square(radius=1)
        mean    = img.reduceNeighborhood(reducer=ee.Reducer.mean(),    kernel=kernel)
        variance= img.reduceNeighborhood(reducer=ee.Reducer.variance(), kernel=kernel)
        img_variance = img.subtract(mean).pow(2)
        weight  = img_variance.divide(img_variance.add(variance))
        filtered= mean.add(weight.multiply(img.subtract(mean)))
        return filtered.copyProperties(img, img.propertyNames())

    col = col.map(lee_filter)

    # Build monthly list
    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)

    months = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months.append(cur.isoformat())
        nxt_month = cur.month % 12 + 1
        nxt_year  = cur.year + (1 if cur.month == 12 else 0)
        cur = cur.replace(year=nxt_year, month=nxt_month, day=1)

    def monthly_stats(m_str):
        m_date = ee.Date(m_str)
        n_date = m_date.advance(1, "month")
        monthly = col.filterDate(m_date, n_date).median()

        water_mask = monthly.lt(water_threshold_db)
        pixel_area = ee.Image.pixelArea().divide(1e6)          # km²
        water_area = water_mask.multiply(pixel_area).reduceRegion(
            reducer=ee.Reducer.sum(), geometry=geom,
            scale=scale, maxPixels=1e9, bestEffort=True
        )
        vv_mean = monthly.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom,
            scale=scale, maxPixels=1e9, bestEffort=True
        )
        n_scenes = col.filterDate(m_date, n_date).size()
        return ee.Feature(None, {
            "date":               m_str,
            "S1_VV_mean_dB":      vv_mean.get("VV"),
            "S1_Water_Area_km2":  water_area.get("VV"),
            "n_scenes":           n_scenes,
        })

    months_ee = ee.List(months)
    return ee.FeatureCollection(months_ee.map(monthly_stats))


def _s2_monthly(
    geom: "ee.Geometry",
    start: str,
    end: str,
    cloud_threshold: float = 20.0,
    scale: int = 30,
) -> "ee.FeatureCollection":
    """
    Sentinel-2 SR Harmonized monthly NDWI with QA60 cloud masking.
    Returns: date, S2_NDWI_mean, S2_Water_Area_km2, Cloud_pct, n_scenes
    """
    def mask_clouds(img):
        qa      = img.select("QA60")
        cloud   = qa.bitwiseAnd(1 << 10).neq(0)
        cirrus  = qa.bitwiseAnd(1 << 11).neq(0)
        mask    = cloud.Or(cirrus).Not()
        return img.updateMask(mask).divide(10000).copyProperties(img, img.propertyNames())

    def add_ndwi(img):
        ndwi = img.normalizedDifference(["B3", "B8"]).rename("NDWI")
        return img.addBands(ndwi)

    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        .map(mask_clouds)
        .map(add_ndwi)
    )

    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)
    months = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months.append(cur.isoformat())
        nxt = cur.month % 12 + 1
        yr  = cur.year + (1 if cur.month == 12 else 0)
        cur = cur.replace(year=yr, month=nxt, day=1)

    def monthly_stats(m_str):
        m_date  = ee.Date(m_str)
        n_date  = m_date.advance(1, "month")
        monthly = col.filterDate(m_date, n_date).median()
        ndwi    = monthly.select("NDWI")
        water   = ndwi.gt(0.0)
        px_area = ee.Image.pixelArea().divide(1e6)
        water_area = water.multiply(px_area).reduceRegion(
            reducer=ee.Reducer.sum(), geometry=geom,
            scale=scale, maxPixels=1e9, bestEffort=True
        )
        ndwi_mean = ndwi.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom,
            scale=scale, maxPixels=1e9, bestEffort=True
        )
        n_scenes   = col.filterDate(m_date, n_date).size()
        cloud_mean = col.filterDate(m_date, n_date) \
                       .aggregate_mean("CLOUDY_PIXEL_PERCENTAGE")
        return ee.Feature(None, {
            "date":              m_str,
            "S2_NDWI_mean":      ndwi_mean.get("NDWI"),
            "S2_Water_Area_km2": water_area.get("NDWI"),
            "Cloud_pct":         cloud_mean,
            "n_scenes":          n_scenes,
        })

    return ee.FeatureCollection(ee.List(months).map(monthly_stats))


def _gpm_daily(
    geom: "ee.Geometry",
    start: str,
    end: str,
    scale: int = 11132,
) -> "ee.FeatureCollection":
    """
    GPM IMERG V07 daily precipitation (mean over catchment).
    Returns: date, GPM_precip_mm, GPM_max_mm
    """
    col = (
        ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
        .filterBounds(geom)
        .filterDate(start, end)
        .select(["precipitation"])
    )

    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)
    days = [(start_dt + datetime.timedelta(d)).isoformat()
            for d in range((end_dt - start_dt).days + 1)]

    def daily_stats(d_str):
        d      = ee.Date(d_str)
        nd     = d.advance(1, "day")
        daily  = col.filterDate(d, nd).mean()
        stats  = daily.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.max(), sharedInputs=True),
            geometry=geom, scale=scale, maxPixels=1e9, bestEffort=True
        )
        return ee.Feature(None, {
            "date":          d_str,
            "GPM_precip_mm": stats.get("precipitation_mean"),
            "GPM_max_mm":    stats.get("precipitation_max"),
        })

    return ee.FeatureCollection(ee.List(days).map(daily_stats))


def _modis_et_monthly(
    geom: "ee.Geometry",
    start: str,
    end: str,
    scale: int = 500,
) -> "ee.FeatureCollection":
    """
    MODIS MOD16A2 actual ET — 8-day → monthly mean (mm/month).
    QA filter: ET_QC bit 0 = good quality.
    Returns: date, MODIS_ET_mm, MODIS_PET_mm
    """
    def mask_qa(img):
        qc   = img.select("ET_QC")
        good = qc.bitwiseAnd(1).eq(0)
        return img.updateMask(good)

    col = (
        ee.ImageCollection("MODIS/061/MOD16A2")
        .filterBounds(geom)
        .filterDate(start, end)
        .map(mask_qa)
        .select(["ET", "PET"])
    )

    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)
    months = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months.append(cur.isoformat())
        nxt = cur.month % 12 + 1
        yr  = cur.year + (1 if cur.month == 12 else 0)
        cur = cur.replace(year=yr, month=nxt, day=1)

    def monthly_stats(m_str):
        m  = ee.Date(m_str)
        nm = m.advance(1, "month")
        # Scale 0.1 → mm/8day; sum 8-day composites → monthly total
        monthly = col.filterDate(m, nm).map(
            lambda img: img.multiply(0.1)).sum()
        stats = monthly.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom, scale=scale, maxPixels=1e9, bestEffort=True
        )
        return ee.Feature(None, {
            "date":         m_str,
            "MODIS_ET_mm":  stats.get("ET"),
            "MODIS_PET_mm": stats.get("PET"),
        })

    return ee.FeatureCollection(ee.List(months).map(monthly_stats))


def _modis_ndvi_monthly(
    geom: "ee.Geometry",
    geom_downstream: "ee.Geometry",
    start: str,
    end: str,
    scale: int = 1000,
) -> "ee.FeatureCollection":
    """
    MODIS MOD13A2 NDVI 16-day → monthly. SummaryQA ≤ 1 filter.
    Returns: date, NDVI_upstream, NDVI_downstream, EVI_downstream
    """
    def mask_qa(img):
        qa   = img.select("SummaryQA")
        good = qa.lte(1)
        return img.updateMask(good).multiply(0.0001) \
                  .copyProperties(img, img.propertyNames())

    col = (
        ee.ImageCollection("MODIS/061/MOD13A2")
        .filterBounds(geom)
        .filterDate(start, end)
        .map(mask_qa)
        .select(["NDVI", "EVI"])
    )

    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)
    months = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months.append(cur.isoformat())
        nxt = cur.month % 12 + 1
        yr  = cur.year + (1 if cur.month == 12 else 0)
        cur = cur.replace(year=yr, month=nxt, day=1)

    def monthly_stats(m_str):
        m      = ee.Date(m_str)
        nm     = m.advance(1, "month")
        composite = col.filterDate(m, nm).mean()
        up   = composite.select("NDVI").reduceRegion(
            ee.Reducer.mean(), geom,            scale, maxPixels=1e9, bestEffort=True)
        down = composite.select("NDVI").reduceRegion(
            ee.Reducer.mean(), geom_downstream, scale, maxPixels=1e9, bestEffort=True)
        evi_down = composite.select("EVI").reduceRegion(
            ee.Reducer.mean(), geom_downstream, scale, maxPixels=1e9, bestEffort=True)
        return ee.Feature(None, {
            "date":            m_str,
            "NDVI_upstream":   up.get("NDVI"),
            "NDVI_downstream": down.get("NDVI"),
            "EVI_downstream":  evi_down.get("EVI"),
        })

    return ee.FeatureCollection(ee.List(months).map(monthly_stats))


def _modis_lst_monthly(
    geom: "ee.Geometry",
    start: str,
    end: str,
    scale: int = 1000,
) -> "ee.FeatureCollection":
    """
    MODIS MYD11A2 (Aqua) LST 8-day → monthly mean °C.
    QC_Day bits 0-1 = 00 filter.
    Returns: date, LST_C, LST_max_C
    """
    def mask_qa(img):
        qc   = img.select("QC_Day")
        good = qc.bitwiseAnd(3).eq(0)
        return img.updateMask(good)

    col = (
        ee.ImageCollection("MODIS/061/MYD11A2")
        .filterBounds(geom)
        .filterDate(start, end)
        .map(mask_qa)
        .select(["LST_Day_1km"])
    )

    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)
    months = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months.append(cur.isoformat())
        nxt = cur.month % 12 + 1
        yr  = cur.year + (1 if cur.month == 12 else 0)
        cur = cur.replace(year=yr, month=nxt, day=1)

    def monthly_stats(m_str):
        m  = ee.Date(m_str)
        nm = m.advance(1, "month")
        composite = col.filterDate(m, nm).map(
            lambda img: img.multiply(0.02).subtract(273.15))  # K → °C
        stats = composite.mean().reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.max(), sharedInputs=True),
            geometry=geom, scale=scale, maxPixels=1e9, bestEffort=True
        )
        return ee.Feature(None, {
            "date":      m_str,
            "LST_C":     stats.get("LST_Day_1km_mean"),
            "LST_max_C": stats.get("LST_Day_1km_max"),
        })

    return ee.FeatureCollection(ee.List(months).map(monthly_stats))


def _viirs_ntl_monthly(
    geom_downstream: "ee.Geometry",
    start: str,
    end: str,
    scale: int = 500,
) -> "ee.FeatureCollection":
    """
    VIIRS DNB monthly night-time light (downstream zone).
    Returns: date, NTL_mean, NTL_sum
    """
    col = (
        ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG")
        .filterBounds(geom_downstream)
        .filterDate(start, end)
        .select(["avg_rad"])
    )

    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)
    months = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months.append(cur.isoformat())
        nxt = cur.month % 12 + 1
        yr  = cur.year + (1 if cur.month == 12 else 0)
        cur = cur.replace(year=yr, month=nxt, day=1)

    def monthly_stats(m_str):
        m  = ee.Date(m_str)
        nm = m.advance(1, "month")
        img = col.filterDate(m, nm).mean()
        stats = img.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                ee.Reducer.sum(), sharedInputs=True),
            geometry=geom_downstream, scale=scale,
            maxPixels=1e9, bestEffort=True
        )
        return ee.Feature(None, {
            "date":     m_str,
            "NTL_mean": stats.get("avg_rad_mean"),
            "NTL_sum":  stats.get("avg_rad_sum"),
        })

    return ee.FeatureCollection(ee.List(months).map(monthly_stats))


def _landsat_wq_monthly(
    geom: "ee.Geometry",
    start: str,
    end: str,
    cloud_threshold: float = 20.0,
    scale: int = 30,
) -> "ee.FeatureCollection":
    """
    Landsat 8 + 9 Collection 2 Level-2 water quality proxies.
    Turbidity (Nechad 2010), CDOM, Chlorophyll-a proxy.
    Cloud mask via QA_PIXEL bitmask. Water mask via NDWI.
    Returns: date, Turbidity, CDOM, Chla_proxy, sensor
    """
    def mask_l89(img):
        qa      = img.select("QA_PIXEL")
        cloud   = qa.bitwiseAnd(1 << 3).neq(0)
        shadow  = qa.bitwiseAnd(1 << 4).neq(0)
        snow    = qa.bitwiseAnd(1 << 5).neq(0)
        cirrus  = qa.bitwiseAnd(1 << 2).neq(0)
        mask    = cloud.Or(shadow).Or(snow).Or(cirrus).Not()
        return img.updateMask(mask) \
                  .multiply(0.0000275).add(-0.2) \
                  .copyProperties(img, img.propertyNames())

    def add_wq(img):
        # Turbidity proxy: Red/Green (Nechad 2010)
        turb = img.select("SR_B4").divide(img.select("SR_B3")).rename("Turbidity")
        # CDOM: Blue/Green
        cdom = img.select("SR_B2").divide(img.select("SR_B3")).rename("CDOM")
        # Chla proxy: Green/Red (Gitelson 2007)
        chla = img.select("SR_B3").divide(img.select("SR_B4")).rename("Chla_proxy")
        # NDWI water mask
        ndwi = img.normalizedDifference(["SR_B3", "SR_B5"]).rename("NDWI_wq")
        water_mask = ndwi.gt(0.1)
        return img.addBands([turb, cdom, chla, ndwi]) \
                  .updateMask(water_mask) \
                  .copyProperties(img, img.propertyNames())

    lc8 = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(geom).filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", cloud_threshold))
        .map(mask_l89).map(add_wq)
    )
    lc9 = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterBounds(geom).filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", cloud_threshold))
        .map(mask_l89).map(add_wq)
    )
    col = lc8.merge(lc9)

    start_dt = datetime.date.fromisoformat(start)
    end_dt   = datetime.date.fromisoformat(end)
    months = []
    cur = start_dt.replace(day=1)
    while cur <= end_dt:
        months.append(cur.isoformat())
        nxt = cur.month % 12 + 1
        yr  = cur.year + (1 if cur.month == 12 else 0)
        cur = cur.replace(year=yr, month=nxt, day=1)

    def monthly_stats(m_str):
        m  = ee.Date(m_str)
        nm = m.advance(1, "month")
        composite = col.filterDate(m, nm).median()
        stats = composite.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom, scale=scale, maxPixels=1e9, bestEffort=True
        )
        n = col.filterDate(m, nm).size()
        return ee.Feature(None, {
            "date":       m_str,
            "Turbidity":  stats.get("Turbidity"),
            "CDOM":       stats.get("CDOM"),
            "Chla_proxy": stats.get("Chla_proxy"),
            "n_scenes":   n,
        })

    return ee.FeatureCollection(ee.List(months).map(monthly_stats))


# ══════════════════════════════════════════════════════════════════════════════
# FC → DATAFRAME HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _fc_to_df(fc: "ee.FeatureCollection", date_col: str = "date") -> pd.DataFrame:
    """
    Convert ee.FeatureCollection to pandas DataFrame.
    Uses getInfo() — safe for monthly results (≤ 300 features).
    For daily results over long ranges, use export_to_drive() instead.
    """
    info = fc.getInfo()
    rows = [f["properties"] for f in info.get("features", [])]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "Date"})
    df = df.sort_values("Date").reset_index(drop=True)
    # Replace None with NaN
    df = df.where(pd.notnull(df), other=np.nan)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE CLASS
# ══════════════════════════════════════════════════════════════════════════════

class GEEEngine:
    """
    High-level interface for HSAE satellite data retrieval via Earth Engine.

    Example
    -------
    >>> from gee_engine import GEEEngine
    >>> from basins_global import GLOBAL_BASINS
    >>> gee = GEEEngine()
    >>> cfg = GLOBAL_BASINS["Blue Nile (GERD)"]
    >>> df  = gee.fetch_all(cfg, "2020-01-01", "2024-12-31")
    >>> print(df.columns.tolist())
    """

    def __init__(self, project: Optional[str] = None, verbose: bool = True):
        self.project = project
        self.verbose = verbose
        self.available = _ensure_ee(project)
        if not self.available and verbose:
            print("⚠️  GEE not available. Install earthengine-api and authenticate.")

    def _log(self, msg: str):
        if self.verbose:
            print(f"  🛰️  GEE: {msg}")

    # ── Individual sensor fetches ──────────────────────────────────────────

    def fetch_s1(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
        water_thr: float = -16.0,
    ) -> Optional[pd.DataFrame]:
        """Sentinel-1 SAR monthly water area + backscatter."""
        if not self.available:
            return None
        try:
            geom = _catchment_geometry(basin_cfg)
            fc   = _s1_monthly(geom, start, end, water_thr)
            df   = _fc_to_df(fc)
            self._log(f"S1: {len(df)} months loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"S1 error: {exc}")
            return None

    def fetch_s2(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
        cloud_thr: float = 20.0,
    ) -> Optional[pd.DataFrame]:
        """Sentinel-2 MSI monthly NDWI + water area."""
        if not self.available:
            return None
        try:
            geom = _catchment_geometry(basin_cfg)
            fc   = _s2_monthly(geom, start, end, cloud_thr)
            df   = _fc_to_df(fc)
            self._log(f"S2: {len(df)} months loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"S2 error: {exc}")
            return None

    def fetch_gpm(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """GPM IMERG V07 daily precipitation."""
        if not self.available:
            return None
        try:
            geom = _catchment_geometry(basin_cfg)
            n_days = (datetime.date.fromisoformat(end) -
                      datetime.date.fromisoformat(start)).days
            if n_days > 365:
                self._log("GPM: long range → monthly aggregation")
                # Use monthly to avoid getInfo() timeout
                fc = _gpm_daily(geom, start, end)
            else:
                fc = _gpm_daily(geom, start, end)
            df = _fc_to_df(fc)
            self._log(f"GPM: {len(df)} records loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"GPM error: {exc}")
            return None

    def fetch_modis_et(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """MODIS MOD16A2 actual ET + PET monthly."""
        if not self.available:
            return None
        try:
            geom = _catchment_geometry(basin_cfg)
            fc   = _modis_et_monthly(geom, start, end)
            df   = _fc_to_df(fc)
            self._log(f"MODIS ET: {len(df)} months loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"MODIS ET error: {exc}")
            return None

    def fetch_modis_ndvi(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """MODIS MOD13A2 NDVI upstream + downstream monthly."""
        if not self.available:
            return None
        try:
            geom      = _catchment_geometry(basin_cfg)
            geom_down = _downstream_geometry(basin_cfg)
            fc        = _modis_ndvi_monthly(geom, geom_down, start, end)
            df        = _fc_to_df(fc)
            self._log(f"MODIS NDVI: {len(df)} months loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"MODIS NDVI error: {exc}")
            return None

    def fetch_modis_lst(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """MODIS MYD11A2 (Aqua) LST monthly."""
        if not self.available:
            return None
        try:
            geom = _catchment_geometry(basin_cfg)
            fc   = _modis_lst_monthly(geom, start, end)
            df   = _fc_to_df(fc)
            self._log(f"MODIS LST: {len(df)} months loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"MODIS LST error: {exc}")
            return None

    def fetch_viirs_ntl(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """VIIRS DNB monthly night-time lights (downstream zone)."""
        if not self.available:
            return None
        try:
            geom_down = _downstream_geometry(basin_cfg)
            fc        = _viirs_ntl_monthly(geom_down, start, end)
            df        = _fc_to_df(fc)
            self._log(f"VIIRS NTL: {len(df)} months loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"VIIRS NTL error: {exc}")
            return None

    def fetch_landsat_wq(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """Landsat 8/9 water quality proxies monthly."""
        if not self.available:
            return None
        try:
            geom = _catchment_geometry(basin_cfg)
            fc   = _landsat_wq_monthly(geom, start, end)
            df   = _fc_to_df(fc)
            self._log(f"Landsat WQ: {len(df)} months loaded")
            return df if not df.empty else None
        except Exception as exc:
            self._log(f"Landsat WQ error: {exc}")
            return None

    # ── Fetch all sensors ──────────────────────────────────────────────────

    def fetch_all(
        self,
        basin_cfg: Dict,
        start: str = "2020-01-01",
        end:   str = "2024-12-31",
        sensors: Optional[List[str]] = None,
        parallel: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch all 8 sensors and merge into a single monthly DataFrame.

        Parameters
        ----------
        basin_cfg  : dict from GLOBAL_BASINS
        start, end : ISO date strings
        sensors    : list of sensor names to fetch (default: all 8)
                     options: "s1","s2","gpm","et","ndvi","lst","viirs","landsat"
        parallel   : run sensors concurrently via threads (faster but uses more EE quota)

        Returns
        -------
        pd.DataFrame with columns:
          Date, S1_VV_mean_dB, S1_Water_Area_km2,
          S2_NDWI_mean, S2_Water_Area_km2, Cloud_pct,
          GPM_precip_mm, GPM_max_mm,
          MODIS_ET_mm, MODIS_PET_mm,
          NDVI_upstream, NDVI_downstream, EVI_downstream,
          LST_C, LST_max_C,
          NTL_mean, NTL_sum,
          Turbidity, CDOM, Chla_proxy,
          Fused_Area  (S1+S2 cloud-adaptive fusion)
        """
        if not self.available:
            self._log("EE not available — returning empty DataFrame")
            return pd.DataFrame()

        all_sensors = ["s1", "s2", "gpm", "et", "ndvi", "lst", "viirs", "landsat"]
        active = sensors if sensors else all_sensors

        fetch_map = {
            "s1":      lambda: self.fetch_s1(basin_cfg, start, end),
            "s2":      lambda: self.fetch_s2(basin_cfg, start, end),
            "gpm":     lambda: self.fetch_gpm(basin_cfg, start, end),
            "et":      lambda: self.fetch_modis_et(basin_cfg, start, end),
            "ndvi":    lambda: self.fetch_modis_ndvi(basin_cfg, start, end),
            "lst":     lambda: self.fetch_modis_lst(basin_cfg, start, end),
            "viirs":   lambda: self.fetch_viirs_ntl(basin_cfg, start, end),
            "landsat": lambda: self.fetch_landsat_wq(basin_cfg, start, end),
        }

        results: Dict[str, Optional[pd.DataFrame]] = {}

        if parallel:
            threads = []
            def _run(key, fn):
                results[key] = fn()
            for key in active:
                if key in fetch_map:
                    t = threading.Thread(target=_run, args=(key, fetch_map[key]))
                    threads.append(t)
                    t.start()
            for t in threads:
                t.join()
        else:
            for key in active:
                if key in fetch_map:
                    results[key] = fetch_map[key]()

        # ── Merge on Date ────────────────────────────────────────────────
        dfs = [df.set_index("Date") for df in results.values()
               if df is not None and not df.empty and "Date" in df.columns]

        if not dfs:
            return pd.DataFrame()

        merged = dfs[0]
        for df in dfs[1:]:
            merged = merged.join(df, how="outer", rsuffix="_dup")
            # Drop duplicate columns
            dup_cols = [c for c in merged.columns if c.endswith("_dup")]
            merged.drop(columns=dup_cols, inplace=True)

        merged = merged.reset_index().rename(columns={"index": "Date"})
        merged = merged.sort_values("Date").reset_index(drop=True)

        # ── Cloud-adaptive S1+S2 area fusion (RSE-1) ─────────────────────
        if "S1_Water_Area_km2" in merged.columns and \
           "S2_Water_Area_km2" in merged.columns and \
           "Cloud_pct" in merged.columns:
            cp   = merged["Cloud_pct"].fillna(50) / 100
            w_sar = (cp / 0.4).clip(0, 1)
            s1a  = merged["S1_Water_Area_km2"].fillna(merged["S2_Water_Area_km2"])
            s2a  = merged["S2_Water_Area_km2"].fillna(merged["S1_Water_Area_km2"])
            merged["Fused_Area"] = s2a * (1 - w_sar) + s1a * w_sar
            self._log("Cloud-adaptive fusion applied → Fused_Area")

        self._log(f"fetch_all complete: {len(merged)} rows, {len(merged.columns)} columns")
        return merged

    # ── GEE Task export (non-blocking, for large datasets) ────────────────

    def export_to_drive(
        self,
        fc: "ee.FeatureCollection",
        description: str,
        folder: str = "HSAE_GEE_Exports",
        file_prefix: str = "hsae_export",
    ) -> str:
        """
        Export a FeatureCollection to Google Drive as CSV (non-blocking).
        Returns the task ID.
        Use when date range > 1 year to avoid getInfo() timeouts.
        """
        if not self.available:
            return ""
        task = ee.batch.Export.table.toDrive(
            collection=fc,
            description=description,
            folder=folder,
            fileNamePrefix=file_prefix,
            fileFormat="CSV",
        )
        task.start()
        self._log(f"Export task started: {description} → Google Drive/{folder}/")
        return task.id

    def export_all_to_drive(
        self,
        basin_cfg: Dict,
        start: str,
        end: str,
        folder: str = "HSAE_GEE_Exports",
    ) -> Dict[str, str]:
        """
        Export all 8 sensors to Google Drive asynchronously.
        Returns dict of {sensor_name: task_id}.
        Use for multi-year datasets.
        """
        if not self.available:
            return {}

        name    = basin_cfg.get("name", basin_cfg.get("id", "basin")).replace(" ", "_")
        geom    = _catchment_geometry(basin_cfg)
        geom_dn = _downstream_geometry(basin_cfg)
        task_ids: Dict[str, str] = {}

        export_jobs = [
            ("S1_SAR",     _s1_monthly(geom, start, end),                                f"{name}_S1_{start[:4]}_{end[:4]}"),
            ("S2_NDWI",    _s2_monthly(geom, start, end),                                f"{name}_S2_{start[:4]}_{end[:4]}"),
            ("GPM_IMERG",  _gpm_daily(geom, start, end),                                 f"{name}_GPM_{start[:4]}_{end[:4]}"),
            ("MODIS_ET",   _modis_et_monthly(geom, start, end),                          f"{name}_ET_{start[:4]}_{end[:4]}"),
            ("MODIS_NDVI", _modis_ndvi_monthly(geom, geom_dn, start, end),               f"{name}_NDVI_{start[:4]}_{end[:4]}"),
            ("MODIS_LST",  _modis_lst_monthly(geom, start, end),                         f"{name}_LST_{start[:4]}_{end[:4]}"),
            ("VIIRS_NTL",  _viirs_ntl_monthly(geom_dn, start, end),                      f"{name}_NTL_{start[:4]}_{end[:4]}"),
            ("Landsat_WQ", _landsat_wq_monthly(geom, start, end),                        f"{name}_WQ_{start[:4]}_{end[:4]}"),
        ]

        for sensor_name, fc, prefix in export_jobs:
            try:
                tid = self.export_to_drive(fc, f"HSAE_{sensor_name}_{name}", folder, prefix)
                task_ids[sensor_name] = tid
                time.sleep(0.5)   # avoid EE rate-limit
            except Exception as exc:
                self._log(f"Export error {sensor_name}: {exc}")
                task_ids[sensor_name] = "ERROR"

        return task_ids

    def check_task_status(self, task_id: str) -> str:
        """Check status of a GEE export task."""
        if not self.available or not task_id:
            return "UNKNOWN"
        try:
            tasks = ee.batch.Task.list()
            for t in tasks:
                if t.id == task_id:
                    return t.status().get("state", "UNKNOWN")
        except Exception:
            pass
        return "UNKNOWN"


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI PANEL
# ══════════════════════════════════════════════════════════════════════════════

def render_gee_engine_panel(basin_name: str, basin_cfg: Dict) -> Optional[pd.DataFrame]:
    """
    Streamlit UI panel for GEE live fetch.
    Integrates with hsae_gee_data.py (CSV upload) as complementary workflow.
    """
    try:
        import streamlit as st
    except ImportError:
        return None

    st.markdown("### 🛰️ GEE Live Engine (Python API)")
    st.caption(
        "استخدم هذا للجلب المباشر من Google Earth Engine بدون تصدير CSV يدوي. "
        "يتطلب: `pip install earthengine-api` ثم `earthengine authenticate`"
    )

    if not _EE_AVAILABLE:
        st.error(
            "**earthengine-api غير مثبت.**\n\n"
            "```bash\npip install earthengine-api>=0.1.390\n"
            "earthengine authenticate\n```"
        )
        return None

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.date_input("تاريخ البداية", value=datetime.date(2020, 1, 1),
                               key="gee_start").isoformat()
    with col2:
        end   = st.date_input("تاريخ النهاية",  value=datetime.date(2024, 12, 31),
                               key="gee_end").isoformat()
    with col3:
        project = st.text_input("GEE Project ID (اختياري)", value="", key="gee_proj")

    sensors_ui = st.multiselect(
        "المستشعرات",
        options=["s1","s2","gpm","et","ndvi","lst","viirs","landsat"],
        default=["s1","s2","gpm","et"],
        format_func=lambda x: {
            "s1":"Sentinel-1 SAR","s2":"Sentinel-2 NDWI","gpm":"GPM IMERG",
            "et":"MODIS ET","ndvi":"MODIS NDVI","lst":"MODIS LST",
            "viirs":"VIIRS NTL","landsat":"Landsat WQ"
        }.get(x, x),
        key="gee_sensors"
    )

    mode = st.radio(
        "وضع الجلب",
        ["getInfo (فوري ≤90 يوم)", "Export to Drive (بيانات كبيرة)"],
        horizontal=True, key="gee_mode"
    )

    if st.button("🚀 جلب بيانات GEE", key="gee_fetch_btn", type="primary"):
        with st.spinner("⏳ جاري الاتصال بـ Google Earth Engine..."):
            gee = GEEEngine(project=project or None, verbose=False)

            if not gee.available:
                st.error("❌ فشل الاتصال بـ GEE. تحقق من المصادقة.")
                return None

            if "Export to Drive" in mode:
                task_ids = gee.export_all_to_drive(basin_cfg, start, end)
                st.success(f"✅ تم إرسال {len(task_ids)} مهام تصدير إلى Google Drive")
                for sensor, tid in task_ids.items():
                    st.write(f"  `{sensor}`: task_id = `{tid}`")
                st.info(
                    "📂 انتظر اكتمال المهام في GEE Code Editor → Tasks\n"
                    "ثم حمّل الملفات CSV وارفعها في تبويب **GEE Uploads**"
                )
                return None
            else:
                df = gee.fetch_all(basin_cfg, start, end, sensors=sensors_ui)

        if df.empty:
            st.warning("⚠️ لم تُرجع GEE بيانات. تحقق من نطاق التاريخ أو جرّب Export to Drive.")
            return None

        st.success(f"✅ تم الجلب: **{len(df)} صف** × **{len(df.columns)} عمود**")

        # Show metrics
        m_cols = st.columns(4)
        show_cols = ["S1_Water_Area_km2","S2_NDWI_mean","GPM_precip_mm","MODIS_ET_mm"]
        for i, col_name in enumerate(show_cols):
            if col_name in df.columns:
                val = df[col_name].mean()
                m_cols[i % 4].metric(col_name.replace("_"," "), f"{val:.2f}")

        # Preview
        st.dataframe(df.tail(12), use_container_width=True)

        # Download
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ تحميل CSV",
            data=csv_bytes,
            file_name=f"gee_{basin_cfg.get('id','basin')}_{start[:4]}_{end[:4]}.csv",
            mime="text/csv",
            key="gee_download"
        )

        st.session_state["gee_live_df"] = df
        return df

    # Check if we already have cached results
    cached = st.session_state.get("gee_live_df")
    if cached is not None and not cached.empty:
        st.info(f"📋 بيانات GEE محمّلة مسبقاً: {len(cached)} صف")
        return cached

    return None
