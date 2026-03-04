# basins_global.py  ─  HSAE v500  Single Source of Truth
# =============================================================================
# ALL basin parameters live here — v430, v990, science, legal all import from
# this file.  Zero duplication.  Every key is documented below.
#
# Schema
# ──────
#  id          str   unique code
#  lat/lon     float centroid WGS-84
#  bbox        list  [lon_min, lat_min, lon_max, lat_max]
#  hybas_id    int   HydroBASINS lv-5  (None if unknown)
#  country     list  riparian states
#  continent   str   display label
#  river       str   main river
#  dam         str   primary dam / station
#  area_max    float max reservoir surface  km²
#  cap         float total storage capacity  BCM
#  head        float hydraulic head  m
#  bathy_a     float V = a × A^b  coefficient
#  bathy_b     float V = a × A^b  exponent
#  eff_cat_km2 float effective catchment area  km²
#  runoff_c    float mean annual runoff coefficient  (0-1)
#  evap_base   float baseline lake evaporation  mm/day
#  csv         str|None  local CSV archive path
#  treaty      str   governing treaty code
#  legal_arts  str   key treaty articles
#  context     str   one-line geopolitical context
#  tags        list  searchable keywords  (Arabic + English)
# =============================================================================

GLOBAL_BASINS = {

    # ── AFRICA ────────────────────────────────────────────────────────────────

    "Blue Nile (GERD)": {
        "name": "Blue Nile (GERD)",
        "glofas_lat": 11.2, "glofas_lon": 35.1,
        "usgs_id": None,
        "grdc_id": "1040250",
        "id": "GERD_ETH",
        "lat": 10.53, "lon": 35.09,
        "bbox": [33.0, 8.0, 37.5, 13.0],
        "geometry": {"type":"Polygon","coordinates":[[[33.0,8.0],[37.5,8.0],[37.5,13.0],[33.0,13.0],[33.0,8.0]]]},
        "hybas_id": 1040203650,
        "country": ["Ethiopia", "Sudan", "Egypt"],
        "continent": "🌍 Africa",
        "river": "Blue Nile", "dam": "Grand Ethiopian Renaissance Dam",
        "area_max": 1875, "cap": 74.0, "head": 145,
        "bathy_a": 0.038, "bathy_b": 1.12,
        "eff_cat_km2": 174_000, "runoff_c": 0.38, "evap_base": 5.4,
        "csv": "data/NileFlow_v228_RSE_SAR.csv",
        "treaty": "UN1997", "legal_arts": "Arts. 5, 7, 12, 20",
        "context": "Largest dam in Africa; transboundary Nile flashpoint",
        "tags": ["nile","gerd","ethiopia","abay","blue nile",
                 "النيل الأزرق","سد النهضة","إثيوبيا"],
    },

    "Nile – Roseires Dam": {
        "name": "Nile – Roseires Dam",
        "glofas_lat": 11.85, "glofas_lon": 34.38,
        "usgs_id": None,
        "grdc_id": "1040220",
        "id": "ROS_SDN",
        "lat": 11.85, "lon": 34.38,
        "bbox": [33.5, 10.5, 35.5, 13.0],
        "geometry": {"type":"Polygon","coordinates":[[[33.5,10.5],[35.5,10.5],[35.5,13.0],[33.5,13.0],[33.5,10.5]]]},
        "hybas_id": 1040210000,
        "country": ["Sudan"],
        "continent": "🌍 Africa",
        "river": "Blue Nile", "dam": "Roseires Dam",
        "area_max": 290, "cap": 3.0, "head": 35,
        "bathy_a": 0.045, "bathy_b": 1.08,
        "eff_cat_km2": 174_000, "runoff_c": 0.35, "evap_base": 6.0,
        "csv": None,
        "treaty": "UN1997", "legal_arts": "Arts. 5, 7",
        "context": "Sudan Blue Nile regulation; key GERD downstream gauge",
        "tags": ["roseires","sudan","الروصيرص","السودان","blue nile","nile"],
    },

    "Nile – High Aswan Dam": {
        "name": "Nile – High Aswan Dam",
        "glofas_lat": 23.97, "glofas_lon": 32.87,
        "usgs_id": None,
        "grdc_id": "1040600",
        "id": "ASWAN_EGY",
        "lat": 23.97, "lon": 32.87,
        "bbox": [30.0, 21.0, 33.5, 25.5],
        "geometry": {"type":"Polygon","coordinates":[[[30.0,21.0],[33.5,21.0],[33.5,25.5],[30.0,25.5],[30.0,21.0]]]},
        "hybas_id": 1040220000,
        "country": ["Egypt", "Sudan"],
        "continent": "🌍 Africa",
        "river": "Nile", "dam": "Aswan High Dam",
        "area_max": 5250, "cap": 162.0, "head": 111,
        "bathy_a": 0.031, "bathy_b": 1.15,
        "eff_cat_km2": 2_900_000, "runoff_c": 0.10, "evap_base": 8.0,
        "csv": "data/NileFlow_Rainfall_GPM_Daily.csv",
        "treaty": "UN1997", "legal_arts": "Arts. 5, 6, 7",
        "context": "Egypt lower-Nile regulation; Lake Nasser delta security",
        "tags": ["aswan","egypt","nasser","مصر","أسوان","السد العالي","nile"],
    },

    "Zambezi – Kariba Dam": {
        "name": "Zambezi – Kariba Dam",
        "glofas_lat": -16.52, "glofas_lon": 28.76,
        "usgs_id": None,
        "grdc_id": None,
        "id": "KARIBA_ZAM",
        "lat": -16.52, "lon": 28.76,
        "bbox": [27.0, -17.5, 30.5, -15.0],
        "geometry": {"type":"Polygon","coordinates":[[[27.0,-17.5],[30.5,-17.5],[30.5,-15.0],[27.0,-15.0],[27.0,-17.5]]]},
        "hybas_id": 1050130000,
        "country": ["Zambia", "Zimbabwe"],
        "continent": "🌍 Africa",
        "river": "Zambezi", "dam": "Kariba Dam",
        "area_max": 5580, "cap": 180.0, "head": 128,
        "bathy_a": 0.033, "bathy_b": 1.14,
        "eff_cat_km2": 663_000, "runoff_c": 0.25, "evap_base": 7.0,
        "csv": None,
        "treaty": "ZAMCOM2004", "legal_arts": "Arts. 5, 7, 20",
        "context": "Zambia/Zimbabwe shared reservoir; fisheries governance",
        "tags": ["kariba","zambezi","zambia","zimbabwe","africa"],
    },

    "Congo – Inga Dam": {
        "name": "Congo – Inga Dam",
        "glofas_lat": -4.3, "glofas_lon": 15.3,
        "usgs_id": None,
        "grdc_id": "1260900",
        "id": "INGA_COD",
        "lat": -5.52, "lon": 13.58,
        "bbox": [13.0, -6.0, 14.5, -4.5],
        "geometry": {"type":"Polygon","coordinates":[[[13.0,-6.0],[14.5,-6.0],[14.5,-4.5],[13.0,-4.5],[13.0,-6.0]]]},
        "hybas_id": 1060080000,
        "country": ["DRC"],
        "continent": "🌍 Africa",
        "river": "Congo", "dam": "Inga Dam",
        "area_max": 120, "cap": 0.5, "head": 96,
        "bathy_a": 0.060, "bathy_b": 1.05,
        "eff_cat_km2": 3_700_000, "runoff_c": 0.40, "evap_base": 4.0,
        "csv": None,
        "treaty": "LCBC", "legal_arts": "Arts. 5, 20",
        "context": "World's largest hydropower potential; DRC Grand Inga project",
        "tags": ["congo","inga","drc","kinshasa","africa"],
    },

    "Niger – Kainji Dam": {
        "name": "Niger – Kainji Dam",
        "glofas_lat": 10.4, "glofas_lon": 4.6,
        "usgs_id": None,
        "grdc_id": None,
        "id": "KAINJI_NGA",
        "lat": 10.40, "lon": 4.58,
        "bbox": [3.5, 9.5, 5.5, 11.5],
        "geometry": {"type":"Polygon","coordinates":[[[3.5,9.5],[5.5,9.5],[5.5,11.5],[3.5,11.5],[3.5,9.5]]]},
        "hybas_id": 1040350000,
        "country": ["Nigeria", "Niger", "Mali", "Guinea"],
        "continent": "🌍 Africa",
        "river": "Niger", "dam": "Kainji Dam",
        "area_max": 1250, "cap": 15.0, "head": 45,
        "bathy_a": 0.048, "bathy_b": 1.09,
        "eff_cat_km2": 2_200_000, "runoff_c": 0.20, "evap_base": 7.5,
        "csv": None,
        "treaty": "NigerBasinAuthority", "legal_arts": "Arts. 5, 7",
        "context": "West Africa Niger Basin transboundary hydropower",
        "tags": ["niger","kainji","nigeria","west africa"],
    },

    # ── MIDDLE EAST ───────────────────────────────────────────────────────────

    "Euphrates – Atatürk Dam": {
        "name": "Euphrates – Atatürk Dam",
        "glofas_lat": 37.48, "glofas_lon": 38.34,
        "usgs_id": None,
        "grdc_id": None,
        "id": "ATATURK_TUR",
        "lat": 37.48, "lon": 38.32,
        "bbox": [36.5, 36.5, 40.0, 38.5],
        "geometry": {"type":"Polygon","coordinates":[[[36.5,36.5],[40.0,36.5],[40.0,38.5],[36.5,38.5],[36.5,36.5]]]},
        "hybas_id": 5040160000,
        "country": ["Turkey", "Syria", "Iraq"],
        "continent": "🌏 Middle East",
        "river": "Euphrates", "dam": "Atatürk Dam",
        "area_max": 817, "cap": 48.7, "head": 169,
        "bathy_a": 0.042, "bathy_b": 1.11,
        "eff_cat_km2": 440_000, "runoff_c": 0.20, "evap_base": 6.5,
        "csv": None,
        "treaty": "TigrisEuphratesProtocol", "legal_arts": "Arts. 5, 7",
        "context": "Turkey GAP project; Tigris-Euphrates transboundary governance",
        "tags": ["ataturk","euphrates","turkey","syria","iraq",
                 "الفرات","تركيا","العراق","سوريا","دجلة"],
    },

    "Tigris – Mosul Dam": {
        "name": "Tigris – Mosul Dam",
        "glofas_lat": 36.62, "glofas_lon": 43.1,
        "usgs_id": None,
        "grdc_id": None,
        "id": "MOSUL_IRQ",
        "lat": 36.63, "lon": 42.82,
        "bbox": [42.0, 36.0, 44.0, 37.5],
        "geometry": {"type":"Polygon","coordinates":[[[42.0,36.0],[44.0,36.0],[44.0,37.5],[42.0,37.5],[42.0,36.0]]]},
        "hybas_id": 5040180000,
        "country": ["Iraq", "Turkey"],
        "continent": "🌏 Middle East",
        "river": "Tigris", "dam": "Mosul Dam",
        "area_max": 380, "cap": 11.1, "head": 113,
        "bathy_a": 0.050, "bathy_b": 1.09,
        "eff_cat_km2": 54_000, "runoff_c": 0.18, "evap_base": 7.0,
        "csv": None,
        "treaty": "TigrisEuphratesProtocol", "legal_arts": "Art. 7",
        "context": "Iraq largest dam; gypsum seepage risk",
        "tags": ["mosul","tigris","iraq","دجلة","العراق","سد الموصل"],
    },

    "Amu Darya – Nurek Dam": {
        "name": "Amu Darya – Nurek Dam",
        "glofas_lat": 38.38, "glofas_lon": 69.32,
        "usgs_id": None,
        "grdc_id": None,
        "id": "NUREK_TJK",
        "lat": 38.38, "lon": 69.38,
        "bbox": [68.5, 37.5, 70.5, 39.0],
        "geometry": {"type":"Polygon","coordinates":[[[68.5,37.5],[70.5,37.5],[70.5,39.0],[68.5,39.0],[68.5,37.5]]]},
        "hybas_id": 4080050000,
        "country": ["Tajikistan", "Uzbekistan", "Turkmenistan", "Afghanistan"],
        "continent": "🌏 Central Asia",
        "river": "Vakhsh / Amu Darya", "dam": "Nurek Dam",
        "area_max": 98, "cap": 10.5, "head": 300,
        "bathy_a": 0.065, "bathy_b": 1.04,
        "eff_cat_km2": 31_400, "runoff_c": 0.45, "evap_base": 5.0,
        "csv": None,
        "treaty": "AralSeaAgreement", "legal_arts": "Arts. 5, 7",
        "context": "Aral Sea basin; Tajikistan-Uzbekistan water-energy nexus",
        "tags": ["nurek","tajikistan","amu darya","aral sea","uzbekistan"],
    },

    # ── ASIA ──────────────────────────────────────────────────────────────────

    "Mekong – Xayaburi Dam": {
        "name": "Mekong – Xayaburi Dam",
        "glofas_lat": 19.17, "glofas_lon": 101.93,
        "usgs_id": None,
        "grdc_id": "2983020",
        "id": "XAYA_LAO",
        "lat": 19.17, "lon": 101.93,
        "bbox": [100.0, 17.0, 104.0, 21.0],
        "geometry": {"type":"Polygon","coordinates":[[[100.0,17.0],[104.0,17.0],[104.0,21.0],[100.0,21.0],[100.0,17.0]]]},
        "hybas_id": 7060123450,
        "country": ["Laos", "Thailand", "Cambodia", "Vietnam", "China"],
        "continent": "🌏 Asia",
        "river": "Mekong", "dam": "Xayaburi Dam",
        "area_max": 490, "cap": 7.4, "head": 32,
        "bathy_a": 0.055, "bathy_b": 1.07,
        "eff_cat_km2": 795_000, "runoff_c": 0.45, "evap_base": 4.5,
        "csv": None,
        "treaty": "MRC1995", "legal_arts": "Art. 5 (MRC)",
        "context": "Laos mainstream dam; downstream fisheries impact",
        "tags": ["mekong","xayaburi","laos","cambodia","vietnam","thailand","lancang"],
    },

    "Yangtze – Three Gorges Dam": {
        "name": "Yangtze – Three Gorges Dam",
        "glofas_lat": 30.82, "glofas_lon": 111.0,
        "usgs_id": None,
        "grdc_id": "2181100",
        "id": "3GORGES_CHN",
        "lat": 30.82, "lon": 111.00,
        "bbox": [109.0, 29.5, 113.0, 32.0],
        "geometry": {"type":"Polygon","coordinates":[[[109.0,29.5],[113.0,29.5],[113.0,32.0],[109.0,32.0],[109.0,29.5]]]},
        "hybas_id": 4050230000,
        "country": ["China"],
        "continent": "🌏 Asia",
        "river": "Yangtze", "dam": "Three Gorges Dam",
        "area_max": 1084, "cap": 39.3, "head": 110,
        "bathy_a": 0.040, "bathy_b": 1.14,
        "eff_cat_km2": 1_000_000, "runoff_c": 0.50, "evap_base": 4.0,
        "csv": None,
        "treaty": "Domestic", "legal_arts": "N/A",
        "context": "World's largest hydroelectric dam; seasonal flow control",
        "tags": ["three gorges","yangtze","china","sanxia","yangzi"],
    },

    "Indus – Tarbela Dam": {
        "name": "Indus – Tarbela Dam",
        "glofas_lat": 34.07, "glofas_lon": 72.68,
        "usgs_id": None,
        "grdc_id": None,
        "id": "TARB_PAK",
        "lat": 34.08, "lon": 72.70,
        "bbox": [72.0, 33.5, 73.5, 35.0],
        "geometry": {"type":"Polygon","coordinates":[[[72.0,33.5],[73.5,33.5],[73.5,35.0],[72.0,35.0],[72.0,33.5]]]},
        "hybas_id": 4050050000,
        "country": ["Pakistan", "India"],
        "continent": "🌏 Asia",
        "river": "Indus", "dam": "Tarbela Dam",
        "area_max": 250, "cap": 13.7, "head": 143,
        "bathy_a": 0.051, "bathy_b": 1.09,
        "eff_cat_km2": 171_200, "runoff_c": 0.32, "evap_base": 5.5,
        "csv": None,
        "treaty": "IndusWatersTreaty1960", "legal_arts": "Arts. I–VIII",
        "context": "World largest earth-filled dam; Indus Waters Treaty",
        "tags": ["tarbela","indus","pakistan","india","sindh"],
    },

    "Brahmaputra – Subansiri Dam": {
        "name": "Brahmaputra – Subansiri Dam",
        "glofas_lat": 27.5, "glofas_lon": 94.5,
        "usgs_id": None,
        "grdc_id": None,
        "id": "SUBANS_IND",
        "lat": 27.18, "lon": 94.25,
        "bbox": [93.5, 26.5, 95.0, 28.0],
        "geometry": {"type":"Polygon","coordinates":[[[93.5,26.5],[95.0,26.5],[95.0,28.0],[93.5,28.0],[93.5,26.5]]]},
        "hybas_id": 4040120000,
        "country": ["India", "China"],
        "continent": "🌏 Asia",
        "river": "Brahmaputra / Yarlung", "dam": "Subansiri Lower Dam",
        "area_max": 34, "cap": 1.37, "head": 116,
        "bathy_a": 0.072, "bathy_b": 1.03,
        "eff_cat_km2": 36_600, "runoff_c": 0.55, "evap_base": 3.5,
        "csv": None,
        "treaty": "IndiaChina_MOU", "legal_arts": "Data exchange",
        "context": "India-China Brahmaputra dispute; Chinese cascade flood risk",
        "tags": ["brahmaputra","yarlung","india","china","assam","tibet"],
    },

    "Ganges – Farakka Barrage": {
        "name": "Ganges – Farakka Barrage",
        "glofas_lat": 24.8, "glofas_lon": 87.93,
        "usgs_id": None,
        "grdc_id": "2650100",
        "id": "FARAKKA_IND",
        "lat": 24.82, "lon": 87.93,
        "bbox": [87.5, 24.4, 88.5, 25.3],
        "geometry": {"type":"Polygon","coordinates":[[[87.5,24.4],[88.5,24.4],[88.5,25.3],[87.5,25.3],[87.5,24.4]]]},
        "hybas_id": None,
        "country": ["India", "Bangladesh"],
        "continent": "🌏 Asia",
        "river": "Ganges", "dam": "Farakka Barrage",
        "area_max": 50, "cap": 0.26, "head": 8,
        "bathy_a": 0.080, "bathy_b": 1.02,
        "eff_cat_km2": 935_000, "runoff_c": 0.38, "evap_base": 5.0,
        "csv": None,
        "treaty": "GangesTreaty1996", "legal_arts": "Schedule Annex",
        "context": "India-Bangladesh Ganges water sharing",
        "tags": ["farakka","ganges","ganga","india","bangladesh","padma"],
    },

    # ── SOUTH AMERICA ─────────────────────────────────────────────────────────

    "Amazon – Belo Monte Dam": {
        "name": "Amazon – Belo Monte Dam",
        "glofas_lat": -3.1, "glofas_lon": -51.62,
        "usgs_id": None,
        "grdc_id": "3629000",
        "id": "AMZ_BRA",
        "lat": -3.12, "lon": -51.77,
        "bbox": [-53.5, -5.5, -50.5, -1.5],
        "geometry": {"type":"Polygon","coordinates":[[[-53.5,-5.5],[-50.5,-5.5],[-50.5,-1.5],[-53.5,-1.5],[-53.5,-5.5]]]},
        "hybas_id": 6080043210,
        "country": ["Brazil"],
        "continent": "🌎 Americas",
        "river": "Xingu / Amazon", "dam": "Belo Monte Dam",
        "area_max": 441, "cap": 11.2, "head": 87,
        "bathy_a": 0.052, "bathy_b": 1.10,
        "eff_cat_km2": 764_000, "runoff_c": 0.55, "evap_base": 3.5,
        "csv": None,
        "treaty": "AmazonCooperation", "legal_arts": "ACTO Arts. 5, 20",
        "context": "Brazil largest dam; indigenous rights; Amazon deforestation",
        "tags": ["amazon","belo monte","brazil","xingu","para","rainforest"],
    },

    "Paraná – Itaipu Dam": {
        "name": "Paraná – Itaipu Dam",
        "glofas_lat": -25.41, "glofas_lon": -54.59,
        "usgs_id": None,
        "grdc_id": "3270050",
        "id": "ITAIPU_BR_PY",
        "lat": -25.41, "lon": -54.58,
        "bbox": [-55.0, -26.0, -54.0, -24.5],
        "geometry": {"type":"Polygon","coordinates":[[[-55.0,-26.0],[-54.0,-26.0],[-54.0,-24.5],[-55.0,-24.5],[-55.0,-26.0]]]},
        "hybas_id": 6090030000,
        "country": ["Brazil", "Paraguay"],
        "continent": "🌎 Americas",
        "river": "Paraná", "dam": "Itaipu Dam",
        "area_max": 1350, "cap": 29.0, "head": 118,
        "bathy_a": 0.045, "bathy_b": 1.10,
        "eff_cat_km2": 820_000, "runoff_c": 0.42, "evap_base": 4.5,
        "csv": None,
        "treaty": "ItaipuTreaty1973", "legal_arts": "Arts. I–XXVII",
        "context": "Binational dam; Brazil-Paraguay power-sharing treaty",
        "tags": ["itaipu","parana","brazil","paraguay","binational"],
    },

    "Orinoco – Guri Dam": {
        "name": "Orinoco – Guri Dam",
        "glofas_lat": 7.76, "glofas_lon": -62.99,
        "usgs_id": None,
        "grdc_id": None,
        "id": "GURI_VEN",
        "lat": 7.76, "lon": -63.00,
        "bbox": [-64.0, 7.0, -62.0, 9.0],
        "geometry": {"type":"Polygon","coordinates":[[[-64.0,7.0],[-62.0,7.0],[-62.0,9.0],[-64.0,9.0],[-64.0,7.0]]]},
        "hybas_id": 6070050000,
        "country": ["Venezuela"],
        "continent": "🌎 Americas",
        "river": "Caroní / Orinoco", "dam": "Guri Dam",
        "area_max": 4250, "cap": 135.0, "head": 162,
        "bathy_a": 0.035, "bathy_b": 1.13,
        "eff_cat_km2": 424_000, "runoff_c": 0.52, "evap_base": 4.0,
        "csv": None,
        "treaty": "Domestic", "legal_arts": "N/A",
        "context": "Venezuela 70% national power; drought vulnerability",
        "tags": ["guri","venezuela","caroní","orinoco"],
    },

    # ── NORTH AMERICA ─────────────────────────────────────────────────────────

    "Colorado – Hoover Dam": {
        "name": "Colorado – Hoover Dam",
        "glofas_lat": 36.01, "glofas_lon": -114.74,
        "usgs_id": "09421500",
        "grdc_id": None,
        "id": "HOOVER_USA",
        "lat": 36.01, "lon": -114.73,
        "bbox": [-116.0, 34.5, -113.0, 37.5],
        "geometry": {"type":"Polygon","coordinates":[[[-116.0,34.5],[-113.0,34.5],[-113.0,37.5],[-116.0,37.5],[-116.0,34.5]]]},
        "hybas_id": 7100010000,
        "country": ["USA", "Mexico"],
        "continent": "🌎 Americas",
        "river": "Colorado", "dam": "Hoover Dam",
        "area_max": 640, "cap": 35.2, "head": 221,
        "bathy_a": 0.035, "bathy_b": 1.18,
        "eff_cat_km2": 629_000, "runoff_c": 0.12, "evap_base": 9.5,
        "csv": None,
        "treaty": "ColoradoCompact1922", "legal_arts": "Art. IV",
        "context": "Over-allocated Colorado; Lake Mead chronic drought crisis",
        "tags": ["hoover","colorado","usa","nevada","arizona","lake mead","mexico"],
    },

    "Columbia – Grand Coulee Dam": {
        "name": "Columbia – Grand Coulee Dam",
        "glofas_lat": 47.97, "glofas_lon": -118.98,
        "usgs_id": "12436500",
        "grdc_id": None,
        "id": "COULEE_USA",
        "lat": 47.96, "lon": -118.98,
        "bbox": [-119.5, 47.5, -118.5, 48.5],
        "geometry": {"type":"Polygon","coordinates":[[[-119.5,47.5],[-118.5,47.5],[-118.5,48.5],[-119.5,48.5],[-119.5,47.5]]]},
        "hybas_id": 7020020000,
        "country": ["USA", "Canada"],
        "continent": "🌎 Americas",
        "river": "Columbia", "dam": "Grand Coulee Dam",
        "area_max": 320, "cap": 11.8, "head": 168,
        "bathy_a": 0.040, "bathy_b": 1.12,
        "eff_cat_km2": 232_000, "runoff_c": 0.38, "evap_base": 5.5,
        "csv": None,
        "treaty": "ColumbiaTreaty1964", "legal_arts": "Arts. I–XV",
        "context": "USA-Canada Columbia River Treaty renegotiation 2024",
        "tags": ["columbia","grand coulee","usa","canada","washington"],
    },

    "Rio Grande – Amistad Dam": {
        "name": "Rio Grande – Amistad Dam",
        "glofas_lat": 29.45, "glofas_lon": -101.07,
        "usgs_id": "08450900",
        "grdc_id": None,
        "id": "AMISTAD_MEX",
        "lat": 29.45, "lon": -101.07,
        "bbox": [-101.8, 29.0, -100.3, 30.0],
        "geometry": {"type":"Polygon","coordinates":[[[-101.8,29.0],[-100.3,29.0],[-100.3,30.0],[-101.8,30.0],[-101.8,29.0]]]},
        "hybas_id": 7100050000,
        "country": ["USA", "Mexico"],
        "continent": "🌎 Americas",
        "river": "Rio Grande / Rio Bravo", "dam": "Amistad Dam",
        "area_max": 880, "cap": 7.5, "head": 75,
        "bathy_a": 0.042, "bathy_b": 1.10,
        "eff_cat_km2": 390_000, "runoff_c": 0.08, "evap_base": 10.0,
        "csv": None,
        "treaty": "RioGrandeTreaty1944", "legal_arts": "Arts. I–X",
        "context": "USA-Mexico shared dam; water allocation dispute",
        "tags": ["amistad","rio grande","rio bravo","usa","mexico","texas"],
    },

    # ── EUROPE ────────────────────────────────────────────────────────────────

    "Danube – Iron Gates I": {
        "name": "Danube – Iron Gates I",
        "glofas_lat": 44.68, "glofas_lon": 22.53,
        "usgs_id": None,
        "grdc_id": "6742900",
        "id": "IRONGATE_EU",
        "lat": 44.68, "lon": 22.52,
        "bbox": [21.5, 43.5, 23.5, 45.5],
        "geometry": {"type":"Polygon","coordinates":[[[21.5,43.5],[23.5,43.5],[23.5,45.5],[21.5,45.5],[21.5,43.5]]]},
        "hybas_id": 2050060000,
        "country": ["Romania", "Serbia"],
        "continent": "🇪🇺 Europe",
        "river": "Danube", "dam": "Iron Gates I",
        "area_max": 150, "cap": 2.4, "head": 35,
        "bathy_a": 0.048, "bathy_b": 1.09,
        "eff_cat_km2": 817_000, "runoff_c": 0.35, "evap_base": 3.5,
        "csv": None,
        "treaty": "DanubeConvention1994", "legal_arts": "Arts. 3, 5",
        "context": "Romania-Serbia; EU Water Framework Directive compliance",
        "tags": ["danube","iron gates","romania","serbia","donau","europe"],
    },

    "Rhine – Basin": {
        "name": "Rhine – Basin",
        "glofas_lat": 51.87, "glofas_lon": 6.14,
        "usgs_id": None,
        "grdc_id": "6335020",
        "id": "RHINE_EU",
        "lat": 47.68, "lon": 8.62,
        "bbox": [6.0, 47.0, 10.0, 48.5],
        "geometry": {"type":"Polygon","coordinates":[[[6.0,47.0],[10.0,47.0],[10.0,48.5],[6.0,48.5],[6.0,47.0]]]},
        "hybas_id": 2020030000,
        "country": ["Switzerland", "Germany", "France", "Netherlands"],
        "continent": "🇪🇺 Europe",
        "river": "Rhine", "dam": "Multiple weirs",
        "area_max": 80, "cap": 0.5, "head": 23,
        "bathy_a": 0.055, "bathy_b": 1.06,
        "eff_cat_km2": 185_000, "runoff_c": 0.42, "evap_base": 3.0,
        "csv": None,
        "treaty": "RhineConvention1999", "legal_arts": "Arts. 3–8",
        "context": "Most regulated river in Europe; model multi-state governance",
        "tags": ["rhine","switzerland","germany","france","netherlands","europe"],
    },

    "Dnieper – Kakhovka Dam": {
        "name": "Dnieper – Kakhovka Dam",
        "glofas_lat": 47.27, "glofas_lon": 34.9,
        "usgs_id": None,
        "grdc_id": None,
        "id": "KAKHOVKA_UKR",
        "lat": 47.10, "lon": 33.37,
        "bbox": [32.0, 46.0, 35.0, 48.5],
        "geometry": {"type":"Polygon","coordinates":[[[32.0,46.0],[35.0,46.0],[35.0,48.5],[32.0,48.5],[32.0,46.0]]]},
        "hybas_id": 2060030000,
        "country": ["Ukraine", "Russia"],
        "continent": "🇪🇺 Europe",
        "river": "Dnieper", "dam": "Kakhovka Dam (destroyed 2023)",
        "area_max": 2155, "cap": 18.2, "head": 16,
        "bathy_a": 0.030, "bathy_b": 1.08,
        "eff_cat_km2": 484_000, "runoff_c": 0.22, "evap_base": 5.0,
        "csv": None,
        "treaty": "Contested", "legal_arts": "IHL / Arts. 5, 7",
        "context": "Destroyed June 2023 (war); catastrophic ecological impact",
        "tags": ["kakhovka","dnieper","ukraine","russia","kherson","war","dnipro"],
    },

    # ── OCEANIA ───────────────────────────────────────────────────────────────

    "Murray-Darling – Hume Dam": {
        "name": "Murray-Darling – Hume Dam",
        "glofas_lat": -36.1, "glofas_lon": 147.03,
        "usgs_id": None,
        "grdc_id": None,
        "id": "HUME_AUS",
        "lat": -36.10, "lon": 147.03,
        "bbox": [146.5, -36.6, 147.8, -35.6],
        "geometry": {"type":"Polygon","coordinates":[[[146.5,-36.6],[147.8,-36.6],[147.8,-35.6],[146.5,-35.6],[146.5,-36.6]]]},
        "hybas_id": 5090020000,
        "country": ["Australia"],
        "continent": "🌏 Oceania",
        "river": "Murray", "dam": "Hume Dam",
        "area_max": 202, "cap": 3.0, "head": 50,
        "bathy_a": 0.058, "bathy_b": 1.07,
        "eff_cat_km2": 1_060_000, "runoff_c": 0.06, "evap_base": 8.0,
        "csv": None,
        "treaty": "MurrayDarlingAgreement1992", "legal_arts": "Schedule 1",
        "context": "Australia driest continent; Murray-Darling basin plan 2026",
        "tags": ["murray","darling","hume","australia","new south wales"],
    },
    # ── CENTRAL ASIA (added v6.0.0) ──────────────────────────────────────────

    "Syr Darya – Toktogul Dam": {
        "name": "Syr Darya – Toktogul Dam",
        "id": "TOKTO_KGZ",
        "lat": 41.78, "lon": 72.92,
        "bbox": [71.5, 41.0, 74.5, 42.5],
        "geometry": {"type":"Polygon","coordinates":[[[71.5,41.0],[74.5,41.0],[74.5,42.5],[71.5,42.5],[71.5,41.0]]]},
        "hybas_id": 4060020000,
        "country": ["Kyrgyzstan", "Uzbekistan", "Kazakhstan", "Tajikistan"],
        "continent": "\U0001f30f Central Asia",
        "river": "Syr Darya", "dam": "Toktogul Dam",
        "area_max": 284, "cap": 19.5, "head": 215,
        "bathy_a": 0.041, "bathy_b": 1.11,
        "eff_cat_km2": 38_000, "runoff_c": 0.48, "evap_base": 4.2,
        "csv": None,
        "usgs_id": None, "grdc_id": "2948800",
        "glofas_lat": 41.78, "glofas_lon": 72.92,
        "meteo_lat":  41.78, "meteo_lon":  72.92,
        "dispute_level": 4,
        "treaty": "AralSeaAgreement1992", "legal_arts": "Arts. 5, 7, 9",
        "context": "Central Asia water-energy nexus; Aral Sea crisis upstream",
        "tags": ["syr darya","toktogul","kyrgyzstan","uzbekistan","aral sea",
                 "\u0633\u064a\u0631 \u062f\u0627\u0631\u064a\u0627","\u062a\u0648\u0643\u062a\u0648\u063a\u0648\u0644"],
    },

    # ── SOUTHEAST ASIA (added v6.0.0) ────────────────────────────────────────

    "Salween – Myitsone Dam": {
        "name": "Salween – Myitsone Dam",
        "id": "MYIN_MMR",
        "lat": 25.47, "lon": 97.53,
        "bbox": [96.5, 24.5, 98.5, 26.5],
        "geometry": {"type":"Polygon","coordinates":[[[96.5,24.5],[98.5,24.5],[98.5,26.5],[96.5,26.5],[96.5,24.5]]]},
        "hybas_id": 4080070000,
        "country": ["Myanmar", "China", "Thailand"],
        "continent": "\U0001f30f Asia",
        "river": "Salween (Nu Jiang)", "dam": "Myitsone Dam (suspended)",
        "area_max": 766, "cap": 3.7, "head": 152,
        "bathy_a": 0.035, "bathy_b": 1.13,
        "eff_cat_km2": 324_000, "runoff_c": 0.52, "evap_base": 5.8,
        "csv": None,
        "usgs_id": None, "grdc_id": None,
        "glofas_lat": 25.47, "glofas_lon": 97.53,
        "meteo_lat":  25.47, "meteo_lon":  97.53,
        "dispute_level": 3,
        "treaty": "MekongAgreement1995", "legal_arts": "Arts. 5, 7, 20",
        "context": "Dam construction suspended 2011; ethnic conflict; China-Myanmar-Thailand",
        "tags": ["salween","myitsone","myanmar","china","thailand","nu jiang",
                 "\u0633\u0627\u0644\u0648\u064a\u0646","\u0645\u064a\u0627\u0646\u0645\u0627\u0631"],
    },


}

# ── Utility functions (used by all pages) ─────────────────────────────────────

def search_basins(query: str) -> dict:
    """Free-text search: name, river, dam, country, tags (Arabic+English)."""
    if not query or not query.strip():
        return GLOBAL_BASINS
    q = query.lower().strip()
    return {
        name: cfg for name, cfg in GLOBAL_BASINS.items()
        if q in " ".join([
            name, cfg.get("id",""), cfg.get("river",""), cfg.get("dam",""),
            cfg.get("continent",""), cfg.get("context",""),
            " ".join(cfg.get("country",[])),
            " ".join(cfg.get("tags",[])),
        ]).lower()
    }


def list_by_continent(continent: str) -> dict:
    return {k: v for k, v in GLOBAL_BASINS.items()
            if continent.lower() in v.get("continent","").lower()}


def list_by_treaty(treaty: str) -> dict:
    return {k: v for k, v in GLOBAL_BASINS.items()
            if treaty.lower() in v.get("treaty","").lower()}


# Derived helpers for sidebar dropdowns
CONTINENTS = sorted({v["continent"] for v in GLOBAL_BASINS.values()})
TREATIES   = sorted({v["treaty"]    for v in GLOBAL_BASINS.values()})
ALL_NAMES  = list(GLOBAL_BASINS.keys())
