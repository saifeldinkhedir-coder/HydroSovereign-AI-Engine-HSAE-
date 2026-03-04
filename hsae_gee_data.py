"""
hsae_gee_data.py  ─  HSAE v6.0.0
=================================
Complete Satellite + Ground Data Integration
Author : Seifeldin M.G. Alkedir — University of Khartoum
ORCID  : 0000-0003-0821-2991
Version: 3.0.0  |  March 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SATELLITE DATA SOURCES (all via Google Earth Engine CSV export):
  1. Sentinel-1 SAR (COPERNICUS/S1_GRD)
       - VV backscatter (dB), water extent area (km²)
       - All-weather, cloud-penetrating C-band SAR
       - 6-10 day revisit, 10m resolution
       - Period: 2014-present (26 global basins)

  2. Sentinel-2 MSI (COPERNICUS/S2_SR_HARMONIZED)
       - NDWI = (B3-B8)/(B3+B8) — McFeeters 1996
       - Water surface area from NDWI > 0.2 threshold
       - 5-day revisit, 10m resolution
       - Cloud-filtered (QA60 bitmask)
       - Period: 2017-present

  3. GPM IMERG (NASA/GPM/3IMERGDL)
       - Daily precipitation (mm/day), 0.1° grid
       - Global coverage, 2014-present
       - Catchment-mean using basin polygon

  4. MODIS MOD16A2 ET (MODIS/061/MOD16A2)
       - Actual evapotranspiration (kg/m²/8-day)
       - MODIS Terra, 500m resolution
       - Used for TDI ET-correction
       - Period: 2000-present

  5. MODIS MOD13A2 NDVI (MODIS/061/MOD13A2)
       - 16-day composite NDVI, 1km
       - Downstream vegetation stress detection
       - Period: 2000-present

  6. MODIS MYD11A2 LST (MODIS/061/MYD11A2)
       - Land Surface Temperature, 8-day, 1km
       - DO proxy for water quality module

  7. VIIRS NTL (NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG)
       - Monthly night-time light radiance
       - Socioeconomic impact proxy (downstream NW-2)

  8. Landsat-8/9 OLI (LANDSAT/LC09/C02/T1_L2)
       - Multi-band optical backup
       - Turbidity, CDOM, water clarity indices

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GROUND DATA APIs (live, no GEE required):
  9.  Open-Meteo ERA5 — Precipitation, T, ET₀, Rn, Wind
  10. GloFAS Flood API — River discharge (m³/s), all basins
  11. USGS NWIS — US streamflow (ft³/s → m³/s)
  12. GRACE-FO JPL RL06 — TWS anomaly (cm EWH)
  13. GRDC Manual CSV — Upload + parse

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GEE WORKFLOW:
  User runs GEE scripts → exports CSV to Google Drive
  → uploads CSV to HSAE → this module parses + merges
  → feeds all downstream modules (Science, Legal, AI, HBV)

GEE SCRIPT COLLECTION: See hsae_gee_scripts/ folder or
  generate via "GEE Scripts" tab in this module.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
try:
    from gee_engine import GEEEngine, render_gee_engine_panel as _render_gee_live
    _GEE_ENGINE_OK = True
except ImportError:
    _GEE_ENGINE_OK = False
from hsae_tdi import add_tdi_to_df, TDI_EPSILON, TDI_ALPHA

import io
import json
import textwrap
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st

# ── Constants ─────────────────────────────────────────────────────────────────
_FT3S_TO_M3S    = 0.028316846592
_M3S_TO_BCM_DAY = 86400 / 1e9
_FLOOD_API       = "https://flood-api.open-meteo.com/v1/flood"
_WEATHER_API     = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_API    = "https://api.open-meteo.com/v1/forecast"
_USGS_API        = "https://waterservices.usgs.gov/nwis/dv/"
_GRACE_API       = "https://grace.jpl.nasa.gov/api/v1/lwe_thickness"

# ══════════════════════════════════════════════════════════════════════════════
# ── SECTION 1: GEE SCRIPT GENERATOR ──────────────────────────────────────────
# Generates ready-to-run JavaScript for Google Earth Engine
# ══════════════════════════════════════════════════════════════════════════════

def generate_s1_sar_script(basin: dict) -> str:
    """
    Generate GEE JavaScript for Sentinel-1 SAR water area extraction.
    Product: COPERNICUS/S1_GRD
    Output columns: date, S1_VV_mean_dB, S1_Water_Area_km2, cloud_coverage
    """
    lat    = basin.get("lat", 11.2)
    lon    = basin.get("lon", 35.1)
    name   = basin.get("name", "Basin").replace(" ","_")
    bbox   = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — Sentinel-1 SAR Water Area Extractor
    // Basin  : {basin.get('name', 'Basin')}
    // Product: COPERNICUS/S1_GRD (IW, VV, Ascending)
    // Output : date, S1_VV_mean_dB, S1_Water_Area_km2
    // Author : Seifeldin M.G. Alkedir — ORCID 0000-0003-0821-2991
    // ═══════════════════════════════════════════════════════════════

    var basin = ee.Geometry.Rectangle([{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]);
    var START = '2015-01-01';
    var END   = '2025-12-31';

    // Load Sentinel-1 IW, VV polarization, ascending pass
    var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
      .filterBounds(basin)
      .filterDate(START, END)
      .filter(ee.Filter.eq('instrumentMode', 'IW'))
      .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
      .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
      .select('VV');

    // Water detection threshold (calibrated per basin)
    var WATER_THRESH = -16;  // dB — adjust if needed (-14 to -18)

    // Monthly composites
    var months = ee.List.sequence(0, ee.Date(END).difference(ee.Date(START), 'month').subtract(1));

    var monthly = months.map(function(m) {{
      var start = ee.Date(START).advance(m, 'month');
      var end   = start.advance(1, 'month');
      var col   = s1.filterDate(start, end);
      var count = col.size();
      var img   = col.mean();

      var water_mask = img.lt(WATER_THRESH);
      var water_area = water_mask.multiply(ee.Image.pixelArea())
                        .reduceRegion({{
                          reducer:   ee.Reducer.sum(),
                          geometry:  basin,
                          scale:     10,
                          maxPixels: 1e13
                        }}).get('VV');

      var vv_mean = img.reduceRegion({{
        reducer:  ee.Reducer.mean(),
        geometry: basin,
        scale:    10,
        maxPixels: 1e13
      }}).get('VV');

      return ee.Feature(null, {{
        'date':               start.format('YYYY-MM-dd'),
        'S1_VV_mean_dB':      vv_mean,
        'S1_Water_Area_km2':  ee.Number(water_area).divide(1e6),
        'n_scenes':           count,
        'basin':              '{name}'
      }});
    }});

    // Export to Google Drive
    Export.table.toDrive({{
      collection: ee.FeatureCollection(monthly),
      description: 'HSAE_{name}_S1_SAR',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','S1_VV_mean_dB','S1_Water_Area_km2','n_scenes','basin']
    }});

    print('S1 SAR collection size:', s1.size());
    Map.centerObject(basin, 8);
    Map.addLayer(s1.mean().clip(basin), {{min:-25, max:0}}, 'S1 VV Mean');
    """)


def generate_s2_ndwi_script(basin: dict) -> str:
    """
    Generate GEE JavaScript for Sentinel-2 NDWI water area extraction.
    Product: COPERNICUS/S2_SR_HARMONIZED
    Output columns: date, S2_NDWI_mean, S2_Water_Area_km2, cloud_pct
    """
    lat  = basin.get("lat", 11.2)
    lon  = basin.get("lon", 35.1)
    name = basin.get("name","Basin").replace(" ","_")
    bbox = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — Sentinel-2 NDWI Water Area Extractor
    // Basin  : {basin.get('name','Basin')}
    // Product: COPERNICUS/S2_SR_HARMONIZED
    // NDWI   : (B3 - B8) / (B3 + B8)  [McFeeters 1996]
    // Output : date, S2_NDWI_mean, S2_Water_Area_km2, cloud_pct
    // ═══════════════════════════════════════════════════════════════

    var basin = ee.Geometry.Rectangle([{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]);
    var START = '2017-01-01';
    var END   = '2025-12-31';
    var CLOUD_THRESH = 20;    // % — reject scenes with >20% cloud cover
    var NDWI_THRESH  = 0.2;   // water/non-water boundary

    // Cloud masking function (Sentinel-2 QA60 bitmask)
    function maskS2clouds(image) {{
      var qa = image.select('QA60');
      var cloudBitMask = 1 << 10;
      var cirrusBitMask = 1 << 11;
      var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
                   .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
      return image.updateMask(mask)
                  .divide(10000)
                  .copyProperties(image, image.propertyNames());
    }}

    // NDWI computation (B3=Green, B8=NIR)
    function addNDWI(image) {{
      var ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI');
      return image.addBands(ndwi);
    }}

    var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(basin)
      .filterDate(START, END)
      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CLOUD_THRESH))
      .map(maskS2clouds)
      .map(addNDWI);

    // 16-day composites (Sentinel-2 repeat cycle)
    var startDate = ee.Date(START);
    var endDate   = ee.Date(END);
    var nPeriods  = endDate.difference(startDate, 'day').divide(16).floor();
    var periods   = ee.List.sequence(0, nPeriods.subtract(1));

    var composites = periods.map(function(p) {{
      var t0  = startDate.advance(ee.Number(p).multiply(16), 'day');
      var t1  = t0.advance(16, 'day');
      var col = s2.filterDate(t0, t1);
      var img = col.median();

      var ndwi_mean = img.select('NDWI').reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: basin,
        scale: 10, maxPixels: 1e13
      }}).get('NDWI');

      var water_mask = img.select('NDWI').gt(NDWI_THRESH);
      var water_area = water_mask.multiply(ee.Image.pixelArea())
                        .reduceRegion({{
                          reducer: ee.Reducer.sum(), geometry: basin,
                          scale: 10, maxPixels: 1e13
                        }}).get('NDWI');

      var cloud_pct = col.aggregate_mean('CLOUDY_PIXEL_PERCENTAGE');

      return ee.Feature(null, {{
        'date':              t0.format('YYYY-MM-dd'),
        'S2_NDWI_mean':      ndwi_mean,
        'S2_Water_Area_km2': ee.Number(water_area).divide(1e6),
        'cloud_pct':         cloud_pct,
        'n_scenes':          col.size(),
        'basin':             '{name}'
      }});
    }});

    Export.table.toDrive({{
      collection: ee.FeatureCollection(composites),
      description: 'HSAE_{name}_S2_NDWI',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','S2_NDWI_mean','S2_Water_Area_km2','cloud_pct','n_scenes','basin']
    }});

    print('S2 collection size:', s2.size());
    Map.centerObject(basin, 8);
    Map.addLayer(s2.median().clip(basin),
      {{bands:['B4','B3','B2'], min:0, max:0.3}}, 'S2 True Color');
    """)


def generate_gpm_script(basin: dict) -> str:
    """
    Generate GEE JavaScript for GPM IMERG daily precipitation extraction.
    Product: NASA/GPM/3IMERGDL
    Output: date, GPM_precip_mm, GPM_catchment_mean_mm
    """
    lat  = basin.get("lat", 11.2)
    lon  = basin.get("lon", 35.1)
    name = basin.get("name","Basin").replace(" ","_")
    bbox = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])
    # Larger catchment for GPM
    cbbox = [bbox[0]-2, bbox[1]-2, bbox[2]+2, bbox[3]+2]

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — GPM IMERG Daily Precipitation Extractor
    // Basin    : {basin.get('name','Basin')}
    // Product  : NASA/GPM/3IMERGDL (IMERG Late Daily Run V06)
    // Band     : HQprecipitation (mm/hr → mm/day × 24)
    // Catchment: Extended bbox for upstream precipitation
    // Output   : date, GPM_precip_mm, GPM_max_mm, n_pixels
    // ═══════════════════════════════════════════════════════════════

    // Reservoir footprint
    var reservoir = ee.Geometry.Rectangle([{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]);
    // Extended catchment (upstream precipitation source)
    var catchment  = ee.Geometry.Rectangle([{cbbox[0]}, {cbbox[1]}, {cbbox[2]}, {cbbox[3]}]);

    var START = '2014-03-01';  // GPM IMERG begins March 2014
    var END   = '2025-12-31';

    var gpm = ee.ImageCollection('NASA/GPM_L3/IMERG_V06')
      .filterDate(START, END)
      .select('precipitationCal');

    // Daily aggregation (GPM is 30-min; daily = sum of 48 half-hours)
    // For IMERGDL (Late Daily), one image per day
    var gpm_daily = ee.ImageCollection('NASA/GPM/3IMERGDL')
      .filterDate(START, END)
      .select('precipitation');

    var days = gpm_daily.aggregate_array('system:time_start');

    var daily_stats = gpm_daily.map(function(img) {{
      var t = img.date();

      // Mean over catchment (mm/day)
      var catch_mean = img.reduceRegion({{
        reducer:  ee.Reducer.mean(),
        geometry: catchment,
        scale:    11132,   // GPM native 0.1° ≈ 11 km
        maxPixels: 1e10
      }}).get('precipitation');

      var catch_max = img.reduceRegion({{
        reducer:  ee.Reducer.max(),
        geometry: catchment,
        scale:    11132,
        maxPixels: 1e10
      }}).get('precipitation');

      // Pixel count
      var n_px = img.reduceRegion({{
        reducer: ee.Reducer.count(), geometry: catchment,
        scale: 11132, maxPixels: 1e10
      }}).get('precipitation');

      return ee.Feature(null, {{
        'date':          t.format('YYYY-MM-dd'),
        'GPM_precip_mm': catch_mean,
        'GPM_max_mm':    catch_max,
        'n_pixels':      n_px,
        'basin':         '{name}'
      }});
    }});

    Export.table.toDrive({{
      collection: daily_stats,
      description: 'HSAE_{name}_GPM_IMERG',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','GPM_precip_mm','GPM_max_mm','n_pixels','basin']
    }});

    print('GPM daily images:', gpm_daily.size());
    Map.centerObject(catchment, 6);
    Map.addLayer(gpm_daily.mean().clip(catchment),
      {{min:0, max:10, palette:['white','blue','darkblue']}}, 'GPM Mean Precip');
    """)


def generate_modis_et_script(basin: dict) -> str:
    """
    Generate GEE JavaScript for MODIS MOD16A2 Evapotranspiration.
    Product: MODIS/061/MOD16A2
    Band: ET (kg/m²/8-day → mm/day ÷8)
    Output: date, MODIS_ET_mm_8day, MODIS_PET_mm_8day
    """
    lat  = basin.get("lat", 11.2)
    lon  = basin.get("lon", 35.1)
    name = basin.get("name","Basin").replace(" ","_")
    bbox = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — MODIS MOD16A2 Evapotranspiration Extractor
    // Basin   : {basin.get('name','Basin')}
    // Product : MODIS/061/MOD16A2 (Terra, 8-day, 500m)
    // Bands   : ET (kg/m²/8-day), PET (kg/m²/8-day)
    //           Scale: 0.1 applied → actual mm/8-day
    // Usage   : TDI ET-correction in hsae_science.py
    //           (replaces simulated ET₀ for forensic TDI_adj)
    // ═══════════════════════════════════════════════════════════════

    var basin = ee.Geometry.Rectangle([{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]);
    // Extended for upstream ET
    var upstream = ee.Geometry.Rectangle([{bbox[0]-1}, {bbox[1]-1}, {bbox[2]+1}, {bbox[3]+1}]);

    var START = '2000-01-01';  // MODIS begins 2000
    var END   = '2025-12-31';
    var SCALE = 0.1;           // MODIS MOD16A2 scale factor

    var mod16 = ee.ImageCollection('MODIS/061/MOD16A2')
      .filterDate(START, END)
      .filterBounds(basin)
      .select(['ET', 'PET', 'ET_QC']);

    // Quality filter: keep only good quality pixels (ET_QC bit 0 = good)
    function filterQuality(img) {{
      var qc   = img.select('ET_QC');
      var good = qc.bitwiseAnd(1).eq(0);  // bit 0 = 0 means good
      return img.updateMask(good);
    }}

    var mod16_qc = mod16.map(filterQuality);

    var et_stats = mod16_qc.map(function(img) {{
      var t = img.date();

      // Apply scale factor
      var et_scaled  = img.select('ET').multiply(SCALE);
      var pet_scaled = img.select('PET').multiply(SCALE);

      var et_mean = et_scaled.reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: upstream,
        scale: 500, maxPixels: 1e13
      }}).get('ET');

      var pet_mean = pet_scaled.reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: upstream,
        scale: 500, maxPixels: 1e13
      }}).get('PET');

      var et_reservoir = et_scaled.reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: basin,
        scale: 500, maxPixels: 1e13
      }}).get('ET');

      return ee.Feature(null, {{
        'date':                t.format('YYYY-MM-dd'),
        'MODIS_ET_mm_8day':    et_mean,
        'MODIS_PET_mm_8day':   pet_mean,
        'MODIS_ET_reservoir':  et_reservoir,
        'basin':               '{name}'
      }});
    }});

    Export.table.toDrive({{
      collection: et_stats,
      description: 'HSAE_{name}_MODIS_ET',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','MODIS_ET_mm_8day','MODIS_PET_mm_8day','MODIS_ET_reservoir','basin']
    }});

    print('MODIS ET images:', mod16_qc.size());
    Map.centerObject(basin, 7);
    Map.addLayer(mod16_qc.mean().select('ET').multiply(0.1).clip(upstream),
      {{min:0, max:100, palette:['red','orange','yellow','green','blue']}},
      'MODIS Mean ET (mm/8-day)');
    """)


def generate_modis_ndvi_script(basin: dict) -> str:
    """
    MODIS MOD13A2 NDVI — downstream vegetation stress detection.
    Product: MODIS/061/MOD13A2
    """
    lat  = basin.get("lat", 11.2)
    lon  = basin.get("lon", 35.1)
    name = basin.get("name","Basin").replace(" ","_")
    bbox = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])
    # Downstream bbox (shifted south for Nile, etc.)
    ds_bbox = [bbox[0]-0.5, bbox[1]-3, bbox[2]+0.5, bbox[3]-0.5]

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — MODIS MOD13A2 NDVI Downstream Impact Extractor
    // Basin      : {basin.get('name','Basin')}
    // Product    : MODIS/061/MOD13A2 (Terra, 16-day, 1km)
    // Band       : NDVI (scale: 0.0001)
    // Usage      : Downstream vegetation stress (NW-2 paper)
    //              Detects agricultural/ecosystem impact of TDI events
    // ═══════════════════════════════════════════════════════════════

    // Reservoir footprint
    var reservoir  = ee.Geometry.Rectangle([{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]);
    // Downstream irrigation zone
    var downstream = ee.Geometry.Rectangle([{ds_bbox[0]}, {ds_bbox[1]}, {ds_bbox[2]}, {ds_bbox[3]}]);

    var START = '2000-01-01';
    var END   = '2025-12-31';

    var mod13 = ee.ImageCollection('MODIS/061/MOD13A2')
      .filterDate(START, END)
      .select(['NDVI', 'EVI', 'SummaryQA']);

    // Quality filter (SummaryQA = 0 or 1 = good/marginal)
    function filterQA(img) {{
      var qa = img.select('SummaryQA');
      return img.updateMask(qa.lte(1));
    }}

    var mod13_qc = mod13.map(filterQA);

    var ndvi_series = mod13_qc.map(function(img) {{
      var t = img.date();
      var ndvi = img.select('NDVI').multiply(0.0001);  // scale factor
      var evi  = img.select('EVI').multiply(0.0001);

      var ndvi_upstream = ndvi.reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: reservoir,
        scale: 1000, maxPixels: 1e13
      }}).get('NDVI');

      var ndvi_downstream = ndvi.reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: downstream,
        scale: 1000, maxPixels: 1e13
      }}).get('NDVI');

      var ndvi_std = ndvi.reduceRegion({{
        reducer: ee.Reducer.stdDev(), geometry: downstream,
        scale: 1000, maxPixels: 1e13
      }}).get('NDVI');

      var evi_downstream = evi.reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: downstream,
        scale: 1000, maxPixels: 1e13
      }}).get('EVI');

      return ee.Feature(null, {{
        'date':              t.format('YYYY-MM-dd'),
        'NDVI_upstream':     ndvi_upstream,
        'NDVI_downstream':   ndvi_downstream,
        'NDVI_std':          ndvi_std,
        'EVI_downstream':    evi_downstream,
        'basin':             '{name}'
      }});
    }});

    Export.table.toDrive({{
      collection: ndvi_series,
      description: 'HSAE_{name}_MODIS_NDVI',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','NDVI_upstream','NDVI_downstream','NDVI_std','EVI_downstream','basin']
    }});

    print('MODIS NDVI images:', mod13_qc.size());
    Map.centerObject(downstream, 7);
    Map.addLayer(mod13_qc.median().select('NDVI').multiply(0.0001).clip(downstream),
      {{min:0, max:0.8, palette:['red','yellow','green']}},
      'Downstream NDVI Median');
    """)


def generate_viirs_ntl_script(basin: dict) -> str:
    """
    VIIRS Night-Time Light — socioeconomic downstream impact proxy.
    Product: NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG
    """
    lat  = basin.get("lat", 11.2)
    lon  = basin.get("lon", 35.1)
    name = basin.get("name","Basin").replace(" ","_")
    bbox = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])
    ds_bbox = [bbox[0]-0.5, bbox[1]-4, bbox[2]+0.5, bbox[3]-0.5]

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — VIIRS Night-Time Light Monthly Extractor
    // Basin   : {basin.get('name','Basin')}
    // Product : NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG
    // Band    : avg_rad (nW/cm²/sr)
    // Usage   : Downstream socioeconomic stress (NW-2 paper)
    //           Night-light dimming correlates with power/crop losses
    // Period  : 2012-present
    // ═══════════════════════════════════════════════════════════════

    var downstream = ee.Geometry.Rectangle([{ds_bbox[0]}, {ds_bbox[1]}, {ds_bbox[2]}, {ds_bbox[3]}]);

    var START = '2012-04-01';
    var END   = '2025-12-31';

    var viirs = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG')
      .filterDate(START, END)
      .select('avg_rad');

    var ntl_series = viirs.map(function(img) {{
      var t = img.date();

      var ntl_mean = img.reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: downstream,
        scale: 500, maxPixels: 1e13
      }}).get('avg_rad');

      var ntl_sum = img.reduceRegion({{
        reducer: ee.Reducer.sum(), geometry: downstream,
        scale: 500, maxPixels: 1e13
      }}).get('avg_rad');

      return ee.Feature(null, {{
        'date':       t.format('YYYY-MM-dd'),
        'NTL_mean':   ntl_mean,
        'NTL_sum':    ntl_sum,
        'basin':      '{name}'
      }});
    }});

    Export.table.toDrive({{
      collection: ntl_series,
      description: 'HSAE_{name}_VIIRS_NTL',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','NTL_mean','NTL_sum','basin']
    }});

    print('VIIRS monthly images:', viirs.size());
    Map.centerObject(downstream, 7);
    Map.addLayer(viirs.mean().clip(downstream),
      {{min:0, max:60, palette:['black','yellow','white']}},
      'VIIRS Night Lights');
    """)


def generate_modis_lst_script(basin: dict) -> str:
    """
    MODIS MYD11A2 Land Surface Temperature — DO proxy for WQ module.
    Product: MODIS/061/MYD11A2
    """
    lat  = basin.get("lat", 11.2)
    lon  = basin.get("lon", 35.1)
    name = basin.get("name","Basin").replace(" ","_")
    bbox = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — MODIS LST Water Temperature Extractor
    // Basin   : {basin.get('name','Basin')}
    // Product : MODIS/061/MYD11A2 (Aqua, 8-day, 1km)
    // Band    : LST_Day_1km (scale: 0.02 → K → °C)
    // Usage   : Water quality DO estimation (hsae_quality.py)
    // ═══════════════════════════════════════════════════════════════

    var basin = ee.Geometry.Rectangle([{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]);
    var START = '2002-07-04';
    var END   = '2025-12-31';

    var myd11 = ee.ImageCollection('MODIS/061/MYD11A2')
      .filterDate(START, END)
      .filterBounds(basin)
      .select(['LST_Day_1km','QC_Day']);

    function convertLST(img) {{
      // Scale 0.02 → Kelvin → Celsius
      var lst_k = img.select('LST_Day_1km').multiply(0.02);
      var lst_c = lst_k.subtract(273.15).rename('LST_C');
      // Quality: keep only good pixels (QC bits 0-1 = 00)
      var qc   = img.select('QC_Day');
      var good = qc.bitwiseAnd(3).eq(0);
      return img.addBands(lst_c).updateMask(good);
    }}

    var lst_qc = myd11.map(convertLST);

    var lst_series = lst_qc.map(function(img) {{
      var t = img.date();
      var lst_mean = img.select('LST_C').reduceRegion({{
        reducer: ee.Reducer.mean(), geometry: basin,
        scale: 1000, maxPixels: 1e13
      }}).get('LST_C');
      var lst_max = img.select('LST_C').reduceRegion({{
        reducer: ee.Reducer.max(), geometry: basin,
        scale: 1000, maxPixels: 1e13
      }}).get('LST_C');
      return ee.Feature(null, {{
        'date':     t.format('YYYY-MM-dd'),
        'LST_C':    lst_mean,
        'LST_max_C':lst_max,
        'basin':    '{name}'
      }});
    }});

    Export.table.toDrive({{
      collection: lst_series,
      description: 'HSAE_{name}_MODIS_LST',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','LST_C','LST_max_C','basin']
    }});
    """)


def generate_landsat_wq_script(basin: dict) -> str:
    """
    Landsat 8/9 OLI — turbidity, CDOM, water quality indices.
    Product: LANDSAT/LC09/C02/T1_L2
    """
    lat  = basin.get("lat", 11.2)
    lon  = basin.get("lon", 35.1)
    name = basin.get("name","Basin").replace(" ","_")
    bbox = basin.get("bbox", [lon-1, lat-1, lon+1, lat+1])

    return textwrap.dedent(f"""\
    // ═══════════════════════════════════════════════════════════════
    // HSAE v6.0.0 — Landsat 8/9 Water Quality Index Extractor
    // Basin   : {basin.get('name','Basin')}
    // Product : LANDSAT/LC08+LC09/C02/T1_L2
    // Indices : Turbidity (B4/B3), CDOM (B3), Chlorophyll-a
    // Usage   : hsae_quality.py RSE-3 paper
    // ═══════════════════════════════════════════════════════════════

    var basin = ee.Geometry.Rectangle([{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]);
    var START = '2013-01-01';
    var END   = '2025-12-31';
    var CLOUD_THRESH = 20;

    function maskL8clouds(img) {{
      var qa = img.select('QA_PIXEL');
      var cloud = qa.bitwiseAnd(1 << 3).eq(0);
      var shadow = qa.bitwiseAnd(1 << 4).eq(0);
      return img.updateMask(cloud).updateMask(shadow)
                .multiply(0.0000275).add(-0.2)
                .copyProperties(img, img.propertyNames());
    }}

    var l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
      .filterBounds(basin).filterDate(START, END)
      .filter(ee.Filter.lt('CLOUD_COVER', CLOUD_THRESH))
      .map(maskL8clouds).select(['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6']);

    var l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
      .filterBounds(basin).filterDate('2021-10-01', END)
      .filter(ee.Filter.lt('CLOUD_COVER', CLOUD_THRESH))
      .map(maskL8clouds).select(['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6']);

    var merged = l8.merge(l9).sort('system:time_start');

    var wq_series = merged.map(function(img) {{
      var t = img.date();
      var B2 = img.select('SR_B2');  // Blue
      var B3 = img.select('SR_B3');  // Green
      var B4 = img.select('SR_B4');  // Red
      var B5 = img.select('SR_B5');  // NIR
      var B6 = img.select('SR_B6');  // SWIR1

      // Turbidity proxy: Nechad 2010 model (B4/B3)
      var turbidity = B4.divide(B3).rename('turbidity');
      // CDOM proxy: blue/green ratio
      var cdom = B2.divide(B3).rename('cdom');
      // Chlorophyll-a: blue/red ratio (Gitelson 2007)
      var chla = B3.divide(B4).rename('chla');
      // NDWI water mask
      var ndwi = img.normalizedDifference(['SR_B3','SR_B5']);
      var water = ndwi.gt(0.1);

      function masked_mean(band) {{
        return band.updateMask(water).reduceRegion({{
          reducer: ee.Reducer.mean(), geometry: basin,
          scale: 30, maxPixels: 1e13
        }});
      }}

      var turb_m = masked_mean(turbidity).get('turbidity');
      var cdom_m = masked_mean(cdom).get('cdom');
      var chla_m = masked_mean(chla).get('chla');

      return ee.Feature(null, {{
        'date':       t.format('YYYY-MM-dd'),
        'turbidity':  turb_m,
        'CDOM':       cdom_m,
        'Chla_proxy': chla_m,
        'sensor':     'Landsat',
        'basin':      '{name}'
      }});
    }});

    Export.table.toDrive({{
      collection: wq_series,
      description: 'HSAE_{name}_Landsat_WQ',
      fileFormat: 'CSV',
      folder: 'HSAE_GEE_Exports',
      selectors: ['date','turbidity','CDOM','Chla_proxy','sensor','basin']
    }});
    """)


# ══════════════════════════════════════════════════════════════════════════════
# ── SECTION 2: GEE CSV PARSERS ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names from any GEE export variant."""
    df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
    # Find date column
    for dc in ["date","system:time_start","time","timestamp","datetime"]:
        if dc in df.columns:
            df["Date"] = pd.to_datetime(df[dc], errors="coerce")
            break
    return df


def parse_s1_csv(f) -> pd.DataFrame | None:
    """Parse Sentinel-1 SAR GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        # Map column variants
        for src, dst in [
            ("s1_vv_mean_db","S1_VV_dB"), ("s1_vv_mean","S1_VV_dB"),
            ("vv_mean","S1_VV_dB"), ("mean_vv","S1_VV_dB"),
            ("s1_water_area_km2","S1_Area"), ("water_area_km2","S1_Area"),
            ("s1_area","S1_Area"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        # Fill missing columns
        if "S1_VV_dB" not in df.columns:
            df["S1_VV_dB"] = np.nan
        if "S1_Area" not in df.columns:
            df["S1_Area"] = np.nan
        df["S1_VV_dB"] = pd.to_numeric(df["S1_VV_dB"], errors="coerce")
        df["S1_Area"]  = pd.to_numeric(df["S1_Area"],   errors="coerce").clip(lower=0)
        df["source_s1"] = "Sentinel-1 SAR (GEE)"
        return df[["Date","S1_VV_dB","S1_Area","source_s1"]].dropna(subset=["Date"])
    except Exception:
        return None


def parse_s2_csv(f) -> pd.DataFrame | None:
    """Parse Sentinel-2 NDWI GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        for src, dst in [
            ("s2_ndwi_mean","S2_NDWI"), ("ndwi_mean","S2_NDWI"), ("ndwi","S2_NDWI"),
            ("s2_water_area_km2","S2_Area"), ("water_area_km2","S2_Area"), ("s2_area","S2_Area"),
            ("cloud_pct","Cloud_pct"), ("cloud_cover","Cloud_pct"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        for c in ["S2_NDWI","S2_Area","Cloud_pct"]:
            if c not in df.columns:
                df[c] = np.nan
        df["S2_NDWI"]   = pd.to_numeric(df["S2_NDWI"], errors="coerce").clip(-1, 1)
        df["S2_Area"]   = pd.to_numeric(df["S2_Area"],  errors="coerce").clip(lower=0)
        df["Optical_Valid"] = (df["S2_NDWI"] >= 0.2).astype(int)
        df["source_s2"] = "Sentinel-2 NDWI (GEE)"
        return df[["Date","S2_NDWI","S2_Area","Cloud_pct","Optical_Valid","source_s2"]].dropna(subset=["Date"])
    except Exception:
        return None


def parse_gpm_csv(f) -> pd.DataFrame | None:
    """Parse GPM IMERG GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        for src, dst in [
            ("gpm_precip_mm","GPM_Rain_mm"), ("precipitation","GPM_Rain_mm"),
            ("gpm_catchment_mean_mm","GPM_Rain_mm"), ("precip_mean","GPM_Rain_mm"),
            ("gpm_max_mm","GPM_max_mm"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        if "GPM_Rain_mm" not in df.columns:
            df["GPM_Rain_mm"] = np.nan
        if "GPM_max_mm" not in df.columns:
            df["GPM_max_mm"] = np.nan
        df["GPM_Rain_mm"] = pd.to_numeric(df["GPM_Rain_mm"], errors="coerce").clip(lower=0)
        df["source_gpm"]  = "GPM IMERG (GEE)"
        return df[["Date","GPM_Rain_mm","GPM_max_mm","source_gpm"]].dropna(subset=["Date"])
    except Exception:
        return None


def parse_modis_et_csv(f) -> pd.DataFrame | None:
    """Parse MODIS MOD16A2 ET GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        for src, dst in [
            ("modis_et_mm_8day","MODIS_ET_mm"), ("et_mean","MODIS_ET_mm"),
            ("et","MODIS_ET_mm"), ("modis_et","MODIS_ET_mm"),
            ("modis_pet_mm_8day","MODIS_PET_mm"), ("pet_mean","MODIS_PET_mm"),
            ("modis_et_reservoir","MODIS_ET_reservoir"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        for c in ["MODIS_ET_mm","MODIS_PET_mm","MODIS_ET_reservoir"]:
            if c not in df.columns: df[c] = np.nan
        df["MODIS_ET_mm"]  = pd.to_numeric(df["MODIS_ET_mm"], errors="coerce").clip(lower=0)
        df["ET0_mm_day"]   = (df["MODIS_ET_mm"] / 8).clip(lower=0)   # 8-day → daily
        df["source_modis_et"] = "MODIS MOD16A2 ET (GEE)"
        return df[["Date","MODIS_ET_mm","MODIS_PET_mm","MODIS_ET_reservoir","ET0_mm_day","source_modis_et"]].dropna(subset=["Date"])
    except Exception:
        return None


def parse_modis_ndvi_csv(f) -> pd.DataFrame | None:
    """Parse MODIS MOD13A2 NDVI GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        for src, dst in [
            ("ndvi_upstream","NDVI_upstream"), ("ndvi_up","NDVI_upstream"),
            ("ndvi_downstream","NDVI_downstream"), ("ndvi_down","NDVI_downstream"),
            ("evi_downstream","EVI_downstream"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        for c in ["NDVI_upstream","NDVI_downstream","EVI_downstream"]:
            if c not in df.columns: df[c] = np.nan
        # Use upstream NDVI as NDVI column for main df
        df["NDVI"] = pd.to_numeric(df.get("NDVI_upstream", df.get("ndvi", np.nan)), errors="coerce")
        df["source_ndvi"] = "MODIS MOD13A2 NDVI (GEE)"
        return df[["Date","NDVI","NDVI_upstream","NDVI_downstream","EVI_downstream","source_ndvi"]].dropna(subset=["Date"])
    except Exception:
        return None


def parse_viirs_csv(f) -> pd.DataFrame | None:
    """Parse VIIRS Night-Time Light GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        for src, dst in [
            ("ntl_mean","NTL_mean"), ("avg_rad","NTL_mean"), ("mean_rad","NTL_mean"),
            ("ntl_sum","NTL_sum"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        for c in ["NTL_mean","NTL_sum"]:
            if c not in df.columns: df[c] = np.nan
        df["source_viirs"] = "VIIRS NTL (GEE)"
        return df[["Date","NTL_mean","NTL_sum","source_viirs"]].dropna(subset=["Date"])
    except Exception:
        return None


def parse_modis_lst_csv(f) -> pd.DataFrame | None:
    """Parse MODIS LST GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        for src, dst in [
            ("lst_c","LST_C"), ("lst_mean","LST_C"), ("lst_day_c","LST_C"),
            ("lst_max_c","LST_max_C"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        for c in ["LST_C","LST_max_C"]:
            if c not in df.columns: df[c] = np.nan
        df["source_lst"] = "MODIS LST (GEE)"
        return df[["Date","LST_C","LST_max_C","source_lst"]].dropna(subset=["Date"])
    except Exception:
        return None


def parse_landsat_wq_csv(f) -> pd.DataFrame | None:
    """Parse Landsat WQ GEE export CSV."""
    try:
        raw = f.read().decode("utf-8", errors="replace")
        df  = pd.read_csv(io.StringIO(raw))
        df  = _normalize_cols(df)
        for src, dst in [
            ("turbidity","Turbidity"), ("turb","Turbidity"),
            ("cdom","CDOM"),
            ("chla_proxy","Chla"), ("chlorophyll","Chla"),
        ]:
            if src in df.columns and dst not in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
        for c in ["Turbidity","CDOM","Chla"]:
            if c not in df.columns: df[c] = np.nan
        df["source_ls"] = "Landsat 8/9 WQ (GEE)"
        return df[["Date","Turbidity","CDOM","Chla","source_ls"]].dropna(subset=["Date"])
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# ── SECTION 3: MERGE ALL GEE LAYERS INTO HSAE MASTER DF ──────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def merge_all_gee_layers(
    df_base: pd.DataFrame,
    s1_df:   pd.DataFrame | None = None,
    s2_df:   pd.DataFrame | None = None,
    gpm_df:  pd.DataFrame | None = None,
    et_df:   pd.DataFrame | None = None,
    ndvi_df: pd.DataFrame | None = None,
    viirs_df:pd.DataFrame | None = None,
    lst_df:  pd.DataFrame | None = None,
    wq_df:   pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Merge all GEE satellite layers into the HSAE master DataFrame.
    Real GEE data overrides simulated columns.
    Returns (merged_df, source_report)
    """
    df   = df_base.copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    info = {"layers": [], "overrides": [], "warnings": []}

    def _merge(sat_df: pd.DataFrame | None, cols: list[str], label: str):
        if sat_df is None or len(sat_df) == 0:
            return
        sat = sat_df.copy()
        sat["Date"] = pd.to_datetime(sat["Date"]).dt.normalize()
        # Forward-fill sparse data (MODIS 8-day → daily)
        sat = sat.set_index("Date").reindex(df["Date"].values).ffill().bfill().reset_index()
        sat.rename(columns={"index":"Date"}, inplace=True)
        for c in cols:
            if c in sat.columns:
                # Remove old simulated column
                if c in df.columns:
                    info["overrides"].append(f"{c} → replaced simulation with {label}")
                df = df.drop(columns=[c], errors="ignore")
                df = df.merge(sat[["Date", c]], on="Date", how="left")
        info["layers"].append(label)

    _merge(s1_df,    ["S1_VV_dB","S1_Area"],                       "Sentinel-1 SAR")
    _merge(s2_df,    ["S2_NDWI","S2_Area","Optical_Valid"],         "Sentinel-2 NDWI")
    _merge(gpm_df,   ["GPM_Rain_mm"],                               "GPM IMERG")
    _merge(et_df,    ["ET0_mm_day","MODIS_ET_mm","MODIS_PET_mm"],   "MODIS MOD16 ET")
    _merge(ndvi_df,  ["NDVI","NDVI_downstream","EVI_downstream"],   "MODIS MOD13 NDVI")
    _merge(viirs_df, ["NTL_mean"],                                   "VIIRS NTL")
    _merge(lst_df,   ["LST_C"],                                      "MODIS LST")
    _merge(wq_df,    ["Turbidity","CDOM","Chla"],                    "Landsat WQ")

    # Recompute Fused_Area from real S1+S2 when available
    has_s1 = s1_df is not None and "S1_Area" in df.columns
    has_s2 = s2_df is not None and "S2_Area" in df.columns
    if has_s1 and has_s2:
        cloud_frac = df.get("Cloud_pct", pd.Series(0, index=df.index)) / 100
        cloud_frac = cloud_frac.fillna(0).clip(0, 1)
        w_sar = (cloud_frac / 0.4).clip(0, 1)   # cloud-adaptive weight (RSE-1 eq.)
        df["Fused_Area"]     = df["S2_Area"] * (1 - w_sar) + df["S1_Area"] * w_sar
        df["Effective_Area"] = df["Fused_Area"]
        info["layers"].append("Fused Area (S1+S2 cloud-adaptive)")

    # Recompute TDI_adj with real MODIS ET if available
    if "MODIS_ET_mm" in df.columns and "Inflow_BCM" in df.columns:
        modis_et_bcm = (df["MODIS_ET_mm"] / 1000 * df.get("Effective_Area", 1000)).clip(lower=0) / 1e6
        et0_bcm      = (df.get("ET0_mm_day", 0) * df.get("Effective_Area", 1000)).clip(lower=0) / 1e6
        # Use canonical TDI function (hsae_tdi.py)
        df = add_tdi_to_df(df, inflow_col="Inflow_BCM", outflow_col="Outflow_BCM",
                            et_pm_col="ET0_mm_day", et_mod_col="MODIS_ET_mm",
                            area_col="Effective_Area")
        info["layers"].append("TDI_adj (MODIS ET-corrected — RSE-2 method)")

    info["n_layers"]  = len(info["layers"])
    info["n_overrides"] = len(info["overrides"])
    return df.reset_index(drop=True), info


# ══════════════════════════════════════════════════════════════════════════════
# ── SECTION 4: LIVE APIs (no GEE needed) ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_open_meteo(lat: float, lon: float, start: str, end: str) -> pd.DataFrame | None:
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": "precipitation_sum,temperature_2m_mean,temperature_2m_max,"
                 "temperature_2m_min,et0_fao_evapotranspiration,"
                 "shortwave_radiation_sum,windspeed_10m_max",
        "timezone": "UTC",
    }
    try:
        r = requests.get(_WEATHER_API, params=params, timeout=40)
        r.raise_for_status()
        d = r.json()["daily"]
        n = len(d["time"])
        return pd.DataFrame({
            "Date":       pd.to_datetime(d["time"]),
            "GPM_Rain_mm":d.get("precipitation_sum",       [np.nan]*n),
            "Temp_C":     d.get("temperature_2m_mean",      [np.nan]*n),
            "Temp_max_C": d.get("temperature_2m_max",       [np.nan]*n),
            "Temp_min_C": d.get("temperature_2m_min",       [np.nan]*n),
            "ET0_mm_day": d.get("et0_fao_evapotranspiration",[np.nan]*n),
            "Rn_MJ_m2":  d.get("shortwave_radiation_sum",  [np.nan]*n),
            "Wind_ms":    d.get("windspeed_10m_max",        [np.nan]*n),
            "source_meteo": "Open-Meteo ERA5",
        }).dropna(subset=["GPM_Rain_mm"])
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_glofas(lat: float, lon: float, start: str, end: str) -> pd.DataFrame | None:
    try:
        r = requests.get(_FLOOD_API, params={
            "latitude": lat, "longitude": lon,
            "daily": "river_discharge",
            "start_date": start, "end_date": end,
        }, timeout=40)
        r.raise_for_status()
        d = r.json()["daily"]
        q = np.array(d["river_discharge"], dtype=float)
        return pd.DataFrame({
            "Date":      pd.to_datetime(d["time"]),
            "Q_m3s":     q,
            "Q_BCM_day": q * _M3S_TO_BCM_DAY,
            "source_q":  "GloFAS",
        }).dropna(subset=["Q_m3s"])
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_usgs(site_id: str, start: str, end: str) -> pd.DataFrame | None:
    try:
        r = requests.get(_USGS_API, params={
            "format": "json", "sites": site_id,
            "startDT": start, "endDT": end,
            "parameterCd": "00060", "statCd": "00003",
        }, timeout=30)
        r.raise_for_status()
        ts = r.json()["value"]["timeSeries"]
        if not ts: return None
        rows = [{"Date": pd.to_datetime(v["dateTime"][:10]),
                 "Q_m3s": float(v["value"]) * _FT3S_TO_M3S}
                for v in ts[0]["values"][0]["value"]
                if v["value"] not in ["-999999","null"]]
        if not rows: return None
        df = pd.DataFrame(rows).set_index("Date").resample("D").mean().reset_index()
        df["Q_BCM_day"] = df["Q_m3s"] * _M3S_TO_BCM_DAY
        df["source_q"]  = "USGS NWIS"
        return df[["Date","Q_m3s","Q_BCM_day","source_q"]]
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_grace(lat: float, lon: float) -> pd.DataFrame | None:
    try:
        r = requests.get(_GRACE_API, params={
            "lat": round(lat, 2), "lon": round(lon, 2), "output_format": "json"
        }, timeout=30)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                df = pd.DataFrame(data)
                df["Date"]   = pd.to_datetime(df["time"])
                df["TWS_cm"] = pd.to_numeric(df["lwe_thickness"], errors="coerce")
                return df[["Date","TWS_cm"]].dropna()
        return None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# ── SECTION 5: GRDC CSV PARSER ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def parse_grdc_csv(f) -> pd.DataFrame | None:
    try:
        raw   = f.read().decode("utf-8", errors="replace")
        lines = [l for l in raw.splitlines() if not l.startswith("#") and l.strip()]
        df    = pd.read_csv(io.StringIO("\n".join(lines)), sep=";", on_bad_lines="skip")
        df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
        date_c = next((c for c in df.columns if any(x in c for x in ["date","yyyy","time"])), None)
        q_c    = next((c for c in df.columns if any(x in c for x in ["discharge","flow","q","runoff","m3s"])), None)
        if not date_c or not q_c: return None
        df["Date"]      = pd.to_datetime(df[date_c], errors="coerce")
        df["Q_m3s"]     = pd.to_numeric(df[q_c], errors="coerce").clip(lower=0)
        df["Q_BCM_day"] = df["Q_m3s"] * _M3S_TO_BCM_DAY
        df["source_q"]  = "GRDC"
        return df[["Date","Q_m3s","Q_BCM_day","source_q"]].dropna(subset=["Date","Q_m3s"]).sort_values("Date").reset_index(drop=True)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# ── SECTION 6: FULL STREAMLIT PAGE ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def render_real_data_panel(basin_name: str, basin: dict) -> pd.DataFrame | None:
    import plotly.graph_objects as go

    lat = basin.get("lat", 11.2)
    lon = basin.get("lon", 35.1)

    st.markdown("""
<div style='background:linear-gradient(135deg,#020617,#060c1a);
            border:2px solid #10b981;border-radius:14px;padding:1.2rem 1.8rem;margin-bottom:1rem;'>
  <b style='color:#10b981;font-size:1.2rem;'>📡 Real Satellite + Ground Data — v6.0.0</b><br>
  <span style='color:#94a3b8;font-size:0.8rem;'>
    Sentinel-1 SAR · Sentinel-2 NDWI · GPM IMERG · MODIS ET · MODIS NDVI ·
    VIIRS NTL · MODIS LST · Landsat WQ · GloFAS · USGS · GRACE-FO · Open-Meteo
  </span>
</div>""", unsafe_allow_html=True)

    tab_gee, tab_live, tab_merge, tab_scripts = st.tabs([
        "🛰️ GEE Uploads",
        "📶 Live APIs",
        "🔗 Merged Dataset",
        "📝 GEE Scripts",
    ])

    # ── TAB 1: GEE CSV UPLOADS ────────────────────────────────────────────────
    with tab_gee:
        st.markdown("### 🛰️ Upload GEE Exported CSV Files")
        st.info("Export from Google Earth Engine → Google Drive → upload below. Each file is parsed automatically.")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**Sentinel-1 SAR**")
            st.caption("S1_GRD · VV · Water area")
            f_s1 = st.file_uploader("Upload S1 CSV", type=["csv"], key="gee_s1")
        with col2:
            st.markdown("**Sentinel-2 NDWI**")
            st.caption("S2_SR · NDWI · Cloud mask")
            f_s2 = st.file_uploader("Upload S2 CSV", type=["csv"], key="gee_s2")
        with col3:
            st.markdown("**GPM IMERG**")
            st.caption("NASA GPM · Daily precip")
            f_gpm = st.file_uploader("Upload GPM CSV", type=["csv"], key="gee_gpm")
        with col4:
            st.markdown("**MODIS MOD16 ET**")
            st.caption("8-day ET · Penman-Monteith")
            f_et = st.file_uploader("Upload MODIS ET CSV", type=["csv"], key="gee_et")

        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.markdown("**MODIS NDVI**")
            st.caption("MOD13A2 · 16-day · 1km")
            f_ndvi = st.file_uploader("Upload NDVI CSV", type=["csv"], key="gee_ndvi")
        with col6:
            st.markdown("**VIIRS NTL**")
            st.caption("Night-time light monthly")
            f_viirs = st.file_uploader("Upload VIIRS CSV", type=["csv"], key="gee_viirs")
        with col7:
            st.markdown("**MODIS LST**")
            st.caption("MYD11A2 · 8-day · 1km")
            f_lst = st.file_uploader("Upload LST CSV", type=["csv"], key="gee_lst")
        with col8:
            st.markdown("**Landsat WQ**")
            st.caption("LC08/09 · Turbidity · CDOM")
            f_wq = st.file_uploader("Upload Landsat WQ CSV", type=["csv"], key="gee_wq")

        # Parse all
        s1_df   = parse_s1_csv(f_s1)     if f_s1   else None
        s2_df   = parse_s2_csv(f_s2)     if f_s2   else None
        gpm_df  = parse_gpm_csv(f_gpm)   if f_gpm  else None
        et_df   = parse_modis_et_csv(f_et)  if f_et  else None
        ndvi_df = parse_modis_ndvi_csv(f_ndvi) if f_ndvi else None
        viirs_df = parse_viirs_csv(f_viirs) if f_viirs else None
        lst_df  = parse_modis_lst_csv(f_lst) if f_lst else None
        wq_df   = parse_landsat_wq_csv(f_wq) if f_wq  else None

        # Status badges
        sources = [
            ("S1 SAR", s1_df, "#22c55e"),
            ("S2 NDWI", s2_df, "#3b82f6"),
            ("GPM", gpm_df, "#06b6d4"),
            ("MODIS ET", et_df, "#f59e0b"),
            ("NDVI", ndvi_df, "#84cc16"),
            ("VIIRS NTL", viirs_df, "#a78bfa"),
            ("MODIS LST", lst_df, "#f97316"),
            ("Landsat WQ", wq_df, "#ec4899"),
        ]
        cols_b = st.columns(8)
        for cb, (name, data, col) in zip(cols_b, sources):
            if data is not None:
                cb.markdown(f"<div style='text-align:center;background:#064e3b;border:1px solid {col};border-radius:6px;padding:6px;color:{col};font-size:0.72rem;'>✅ {name}<br><span style='color:#94a3b8;font-size:0.65rem;'>{len(data):,} rows</span></div>", unsafe_allow_html=True)
            else:
                cb.markdown(f"<div style='text-align:center;background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:6px;color:#484f58;font-size:0.72rem;'>⬜ {name}</div>", unsafe_allow_html=True)

        # Save parsed GEE layers to session state
        any_gee = any(x is not None for x in [s1_df,s2_df,gpm_df,et_df,ndvi_df,viirs_df,lst_df,wq_df])
        if any_gee:
            st.session_state.update({
                "gee_s1": s1_df, "gee_s2": s2_df, "gee_gpm": gpm_df,
                "gee_et": et_df, "gee_ndvi": ndvi_df, "gee_viirs": viirs_df,
                "gee_lst": lst_df, "gee_wq": wq_df,
            })
            st.success(f"✅ {sum(1 for x in [s1_df,s2_df,gpm_df,et_df,ndvi_df,viirs_df,lst_df,wq_df] if x is not None)}/8 satellite layers loaded.")

    # ── TAB 2: LIVE APIs ──────────────────────────────────────────────────────
    with tab_live:
        st.markdown("### 📶 Live API Data (no GEE required)")
        c1, c2 = st.columns(2)
        start_d = c1.date_input("Start", value=date(2020,1,1), key="rd_start")
        end_d   = c2.date_input("End",   value=date(2024,12,31), key="rd_end")

        # GRDC
        grdc_file = st.file_uploader("GRDC CSV (optional manual upload)", type=["csv","txt"], key="rd_grdc")

        if st.button("🚀 Fetch All Live APIs", type="primary", key="rd_fetch"):
            results = {}
            with st.spinner("Fetching Open-Meteo ERA5…"):
                results["meteo"] = fetch_open_meteo(lat, lon, str(start_d), str(end_d))
            with st.spinner("Fetching GloFAS discharge…"):
                usgs_id = basin.get("usgs_id")
                if usgs_id:
                    results["q"] = fetch_usgs(usgs_id, str(start_d), str(end_d))
                else:
                    results["q"] = fetch_glofas(lat, lon, str(start_d), str(end_d))
            with st.spinner("Fetching GRACE-FO TWS…"):
                results["grace"] = fetch_grace(lat, lon)
            if grdc_file:
                results["q"] = parse_grdc_csv(grdc_file) or results.get("q")
            st.session_state["live_api_results"] = results
            st.session_state["live_api_basin"]   = basin_name

        results = st.session_state.get("live_api_results", {})
        if results:
            # Metrics row
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("🌤️ Open-Meteo", f"{len(results.get('meteo') or [])} rows" if results.get('meteo') is not None else "⬜")
            src = (results.get('q') or pd.DataFrame()).get("source_q", pd.Series()).iloc[0] if results.get('q') is not None and len(results.get('q',[])) else "⬜"
            m2.metric("💧 Discharge", src)
            m3.metric("🛰️ GRACE-FO", f"{len(results.get('grace') or [])} pts" if results.get('grace') is not None else "⬜")
            m4.metric("🌊 Source", basin.get("continent","—"))

            # Charts
            if results.get("meteo") is not None:
                dm = results["meteo"]
                fig = go.Figure()
                fig.add_bar(x=dm["Date"], y=dm["GPM_Rain_mm"], name="Precipitation (mm)", marker_color="#3b82f6")
                fig.add_trace(go.Scatter(x=dm["Date"], y=dm["ET0_mm_day"],
                    mode="lines", name="ET₀ FAO-56 (mm/d)", line=dict(color="#f59e0b",width=2), yaxis="y2"))
                fig.update_layout(template="plotly_dark", height=360,
                    title="Open-Meteo ERA5 — Precipitation & ET₀",
                    yaxis=dict(title="Rain (mm)"),
                    yaxis2=dict(title="ET₀ (mm/d)", overlaying="y", side="right"))
                st.plotly_chart(fig, use_container_width=True)

            if results.get("q") is not None:
                dq = results["q"]
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=dq["Date"], y=dq["Q_m3s"], mode="lines",
                    name=f"Discharge m³/s ({src})", line=dict(color="#22c55e", width=1.5)))
                fig2.update_layout(template="plotly_dark", height=300,
                    title=f"River Discharge — {src}", yaxis_title="m³/s")
                st.plotly_chart(fig2, use_container_width=True)

    # ── TAB 3: MERGED DATASET ─────────────────────────────────────────────────
    with tab_merge:
        st.markdown("### 🔗 Merge All Layers into HSAE Master DataFrame")
        st.markdown("Combines GEE uploads + Live APIs + simulation baseline. Real data overrides simulated columns.")

        if st.button("🔗 Merge All Sources", type="primary", key="rd_merge"):
            base_df = st.session_state.get("df")
            if base_df is None:
                st.warning("Run v430 first to generate baseline, then merge real data on top.")
            else:
                live = st.session_state.get("live_api_results", {})
                # Build API dataframes
                meteo  = live.get("meteo")
                q_data = live.get("q")
                grace  = live.get("grace")

                # Inject live API columns into base
                if meteo is not None:
                    meteo["Date"] = pd.to_datetime(meteo["Date"]).dt.normalize()
                    base_df = base_df.drop(columns=["GPM_Rain_mm","ET0_mm_day"], errors="ignore")
                    base_df = base_df.merge(meteo[["Date","GPM_Rain_mm","ET0_mm_day","Temp_C","Wind_ms"]], on="Date", how="left")
                if q_data is not None:
                    q_data["Date"] = pd.to_datetime(q_data["Date"]).dt.normalize()
                    base_df = base_df.drop(columns=["Outflow_BCM","Flow_m3s"], errors="ignore")
                    base_df = base_df.merge(q_data[["Date","Q_m3s","Q_BCM_day"]], on="Date", how="left")
                    base_df.rename(columns={"Q_BCM_day":"Outflow_BCM","Q_m3s":"Flow_m3s"}, inplace=True)
                if grace is not None:
                    grace["Date"] = pd.to_datetime(grace["Date"]).dt.to_period("M").dt.to_timestamp()
                    gm = grace.set_index("Date")["TWS_cm"].to_dict()
                    base_df["_m"] = base_df["Date"].dt.to_period("M").dt.to_timestamp()
                    base_df["TWS_cm"] = base_df["_m"].map(gm)
                    base_df = base_df.drop(columns=["_m"])

                # Merge GEE layers
                merged_df, info = merge_all_gee_layers(
                    base_df,
                    s1_df   = st.session_state.get("gee_s1"),
                    s2_df   = st.session_state.get("gee_s2"),
                    gpm_df  = st.session_state.get("gee_gpm"),
                    et_df   = st.session_state.get("gee_et"),
                    ndvi_df = st.session_state.get("gee_ndvi"),
                    viirs_df= st.session_state.get("gee_viirs"),
                    lst_df  = st.session_state.get("gee_lst"),
                    wq_df   = st.session_state.get("gee_wq"),
                )
                st.session_state["df"] = merged_df

                st.success(f"✅ Merged {info['n_layers']} layers, {info['n_overrides']} simulation columns replaced with real data.")
                st.markdown("**Layers merged:**")
                for l in info["layers"]: st.markdown(f"  - {l}")
                if info["overrides"]:
                    with st.expander("📋 Overridden simulation columns"):
                        for o in info["overrides"]: st.markdown(f"  - {o}")

                # Preview
                st.dataframe(merged_df.tail(30), use_container_width=True, height=300)
                st.download_button("⬇️ Download Master Dataset",
                    merged_df.to_csv(index=False).encode(),
                    f"HSAE_master_{basin_name.replace(' ','_')}.csv","text/csv")

    # ── TAB 4: GEE SCRIPTS ───────────────────────────────────────────────────
    with tab_scripts:
        st.markdown("### 📝 Google Earth Engine Scripts")
        st.markdown("""
**Instructions:**
1. Go to [code.earthengine.google.com](https://code.earthengine.google.com)
2. Copy the script for the sensor you need
3. Paste into GEE Code Editor → click **Run**
4. Export task will appear in **Tasks** tab → click **Run** to export to Google Drive
5. Download CSV from Google Drive → upload in **GEE Uploads** tab above
""")
        script_choice = st.selectbox("Select Sensor / Product", [
            "Sentinel-1 SAR (water area, VV backscatter)",
            "Sentinel-2 NDWI (water area, cloud mask)",
            "GPM IMERG (daily precipitation)",
            "MODIS MOD16A2 (evapotranspiration ET)",
            "MODIS MOD13A2 (NDVI downstream impact)",
            "VIIRS Night-Time Light (NTL socioeconomic)",
            "MODIS LST (land surface temperature)",
            "Landsat 8/9 (water quality indices)",
        ], key="script_sel")

        if "Sentinel-1" in script_choice:
            script = generate_s1_sar_script(basin)
            notes = "⏱ Processing: ~5–15 min for 10 years. Output: monthly S1 VV + water area."
        elif "Sentinel-2" in script_choice:
            script = generate_s2_ndwi_script(basin)
            notes = "⏱ Processing: ~10–20 min for 8 years. Output: 16-day NDWI + water area."
        elif "GPM" in script_choice:
            script = generate_gpm_script(basin)
            notes = "⏱ Processing: ~5–10 min. Output: daily GPM precipitation over catchment."
        elif "MOD16" in script_choice or "evapotranspiration" in script_choice.lower():
            script = generate_modis_et_script(basin)
            notes = "⏱ Processing: ~10–20 min for 25 years. Output: 8-day ET + PET."
        elif "MOD13" in script_choice or "NDVI" in script_choice:
            script = generate_modis_ndvi_script(basin)
            notes = "⏱ Processing: ~15–25 min. Output: 16-day NDVI upstream + downstream."
        elif "VIIRS" in script_choice:
            script = generate_viirs_ntl_script(basin)
            notes = "⏱ Processing: ~5 min. Output: monthly NTL radiance downstream."
        elif "LST" in script_choice:
            script = generate_modis_lst_script(basin)
            notes = "⏱ Processing: ~10 min. Output: 8-day LST day + night."
        else:
            script = generate_landsat_wq_script(basin)
            notes = "⏱ Processing: ~15–30 min. Output: 30m turbidity, CDOM, Chlorophyll-a proxy."

        st.info(notes)
        st.code(script, language="javascript")
        st.download_button(
            "⬇️ Download GEE Script (.js)",
            script.encode(),
            f"HSAE_{basin_name.replace(' ','_')}_{script_choice.split('(')[0].strip().replace(' ','_')}.js",
            "text/javascript",
        )

    return st.session_state.get("df")
