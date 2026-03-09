"""
basins_data.py — 26 Basin Registry for HSAE QGIS Plugin
Each basin: id, name, region, lat, lon, bbox [lon_min, lat_min, lon_max, lat_max],
            country_up, country_dn, treaty, tdi_default
"""

BASINS_26 = [
    # ── Africa ────────────────────────────────────────────────────────────────
    {"id": "blue_nile_gerd",    "name": "Blue Nile – GERD",        "region": "Africa",       "lat": 11.21, "lon": 35.09, "bbox": [33.0, 9.0,  37.0, 13.0], "country_up": "Ethiopia",   "country_dn": "Sudan/Egypt",  "tdi": 0.62},
    {"id": "nile_roseires",     "name": "Nile – Roseires",         "region": "Africa",       "lat": 11.78, "lon": 34.38, "bbox": [33.0, 10.0, 36.0, 13.5], "country_up": "Ethiopia",   "country_dn": "Sudan",        "tdi": 0.45},
    {"id": "nile_aswan",        "name": "Nile – Aswan",            "region": "Africa",       "lat": 23.97, "lon": 32.88, "bbox": [31.0, 22.0, 35.0, 26.0], "country_up": "Sudan",      "country_dn": "Egypt",        "tdi": 0.38},
    {"id": "zambezi_kariba",    "name": "Zambezi – Kariba",        "region": "Africa",       "lat": -16.52,"lon": 28.77, "bbox": [26.0,-19.0, 32.0,-14.0], "country_up": "Zambia",     "country_dn": "Zimbabwe",     "tdi": 0.28},
    {"id": "congo_inga",        "name": "Congo – Inga",            "region": "Africa",       "lat": -5.52, "lon": 13.58, "bbox": [11.0, -8.0, 17.0, -3.0], "country_up": "DRC",        "country_dn": "DRC/Congo",    "tdi": 0.15},
    {"id": "niger_kainji",      "name": "Niger – Kainji",          "region": "Africa",       "lat": 10.40, "lon": 4.58,  "bbox": [2.0,  7.0,  8.0, 14.0], "country_up": "Guinea",     "country_dn": "Nigeria",      "tdi": 0.31},
    # ── Middle East ───────────────────────────────────────────────────────────
    {"id": "euphrates_ataturk", "name": "Euphrates – Atatürk",     "region": "Middle East",  "lat": 37.48, "lon": 38.33, "bbox": [36.0, 35.0, 41.0, 40.0], "country_up": "Turkey",     "country_dn": "Syria/Iraq",   "tdi": 0.71},
    {"id": "tigris_mosul",      "name": "Tigris – Mosul",          "region": "Middle East",  "lat": 36.63, "lon": 42.83, "bbox": [41.0, 34.0, 46.0, 39.0], "country_up": "Turkey",     "country_dn": "Iraq",         "tdi": 0.58},
    # ── Central Asia ──────────────────────────────────────────────────────────
    {"id": "amu_darya_nurek",   "name": "Amu Darya – Nurek",       "region": "Central Asia", "lat": 38.37, "lon": 69.32, "bbox": [67.0, 36.0, 72.0, 41.0], "country_up": "Tajikistan", "country_dn": "Uzbekistan",   "tdi": 0.66},
    {"id": "syr_darya_toktogul","name": "Syr Darya – Toktogul",    "region": "Central Asia", "lat": 41.78, "lon": 72.82, "bbox": [70.0, 39.0, 76.0, 44.0], "country_up": "Kyrgyzstan", "country_dn": "Kazakhstan",   "tdi": 0.54},
    # ── Asia ──────────────────────────────────────────────────────────────────
    {"id": "mekong_xayaburi",   "name": "Mekong – Xayaburi",       "region": "Asia",         "lat": 19.52, "lon": 101.72,"bbox": [99.0,17.0,104.0,22.0],  "country_up": "Laos",       "country_dn": "Thailand",     "tdi": 0.49},
    {"id": "yangtze_3gorges",   "name": "Yangtze – Three Gorges",  "region": "Asia",         "lat": 30.82, "lon": 111.00,"bbox":[108.0,28.0,114.0,33.0],  "country_up": "China",      "country_dn": "China",        "tdi": 0.22},
    {"id": "indus_tarbela",     "name": "Indus – Tarbela",         "region": "Asia",         "lat": 33.98, "lon": 72.68, "bbox": [70.0, 31.0, 76.0, 37.0], "country_up": "Pakistan",   "country_dn": "Pakistan",     "tdi": 0.41},
    {"id": "brahmaputra_sub",   "name": "Brahmaputra – Subansiri", "region": "Asia",         "lat": 27.50, "lon": 94.20, "bbox": [92.0, 25.0, 97.0, 30.0], "country_up": "China",      "country_dn": "India",        "tdi": 0.55},
    {"id": "ganges_farakka",    "name": "Ganges – Farakka",        "region": "Asia",         "lat": 24.83, "lon": 87.92, "bbox": [85.0, 22.0, 91.0, 27.0], "country_up": "India",      "country_dn": "Bangladesh",   "tdi": 0.47},
    {"id": "salween_myitsone",  "name": "Salween – Myitsone",      "region": "Asia",         "lat": 25.32, "lon": 97.52, "bbox": [95.0, 23.0,100.0, 28.0], "country_up": "China",      "country_dn": "Myanmar",      "tdi": 0.60},
    # ── Americas ──────────────────────────────────────────────────────────────
    {"id": "amazon_belo_monte", "name": "Amazon – Belo Monte",     "region": "Americas",     "lat": -3.38, "lon": -51.77,"bbox":[-55.0,-6.0,-48.0,-1.0],  "country_up": "Brazil",     "country_dn": "Brazil",       "tdi": 0.18},
    {"id": "parana_itaipu",     "name": "Paraná – Itaipu",         "region": "Americas",     "lat": -25.41,"lon": -54.59,"bbox":[-57.0,-28.0,-52.0,-22.0],"country_up": "Brazil",     "country_dn": "Paraguay",     "tdi": 0.25},
    {"id": "orinoco_guri",      "name": "Orinoco – Guri",          "region": "Americas",     "lat": 7.76,  "lon": -63.00,"bbox":[-66.0, 5.0,-60.0,10.0],  "country_up": "Venezuela",  "country_dn": "Venezuela",    "tdi": 0.21},
    {"id": "colorado_hoover",   "name": "Colorado – Hoover",       "region": "Americas",     "lat": 36.01, "lon": -114.74,"bbox":[-117.0,34.0,-112.0,38.0],"country_up": "USA",       "country_dn": "USA/Mexico",   "tdi": 0.72},
    {"id": "columbia_gcoulee",  "name": "Columbia – Grand Coulee", "region": "Americas",     "lat": 47.96, "lon": -118.98,"bbox":[-121.0,45.0,-116.0,50.0],"country_up": "USA",       "country_dn": "USA",          "tdi": 0.30},
    {"id": "rio_grande_amistad","name": "Rio Grande – Amistad",    "region": "Americas",     "lat": 29.45, "lon": -101.07,"bbox":[-104.0,27.0,-99.0,31.0], "country_up": "USA",        "country_dn": "Mexico",       "tdi": 0.65},
    # ── Europe ────────────────────────────────────────────────────────────────
    {"id": "danube_iron_gates", "name": "Danube – Iron Gates I",   "region": "Europe",       "lat": 44.67, "lon": 22.52, "bbox": [20.0, 42.0, 26.0, 47.0], "country_up": "Romania",    "country_dn": "Serbia",       "tdi": 0.20},
    {"id": "rhine_basin",       "name": "Rhine – Basin",           "region": "Europe",       "lat": 51.50, "lon": 6.50,  "bbox": [4.0,  47.0,  9.0, 54.0], "country_up": "Switzerland","country_dn": "Netherlands",  "tdi": 0.12},
    {"id": "dnieper_kakhovka",  "name": "Dnieper – Kakhovka",      "region": "Europe",       "lat": 47.27, "lon": 33.37, "bbox": [31.0, 45.0, 36.0, 50.0], "country_up": "Russia",     "country_dn": "Ukraine",      "tdi": 0.68},
    # ── Oceania ───────────────────────────────────────────────────────────────
    {"id": "murray_hume",       "name": "Murray-Darling – Hume",   "region": "Oceania",      "lat": -36.10,"lon": 147.03,"bbox":[144.0,-38.0,150.0,-34.0],"country_up": "Australia",  "country_dn": "Australia",    "tdi": 0.35},
]
