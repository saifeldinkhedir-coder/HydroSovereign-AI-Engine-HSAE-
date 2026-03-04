# hsae_devops.py  –  HSAE DevOps & Advanced Integration Module
# Updated: 2026-02-26  |  Author: Seifeldin M. G. Alkedir
# Covers:  PostGIS schema | FastAPI router | Docker compose | CI/CD YAML

"""
This module contains:
  1. PostgreSQL + PostGIS schema SQL
  2. FastAPI REST router (to expose HSAE as open API)
  3. Docker Compose config (as Python string)
  4. GitHub Actions CI/CD YAML
  5. Streamlit DevOps dashboard
"""

from __future__ import annotations
import streamlit as st
import textwrap

# ══════════════════════════════════════════════════════════════════════════════
# 1. POSTGRESQL + POSTGIS SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

POSTGRES_SCHEMA = """
-- ══════════════════════════════════════════════════════════════════
--  HSAE PostGIS Schema — Run once in psql or pgAdmin
-- ══════════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;  -- optional for time-series

-- Basins catalogue
CREATE TABLE IF NOT EXISTS hsae_basins (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    river       TEXT,
    countries   TEXT[],
    cap_bcm     DOUBLE PRECISION,
    head_m      DOUBLE PRECISION,
    area_max_km DOUBLE PRECISION,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    geom        GEOMETRY(Point, 4326),
    treaty      TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Insert geom from lat/lon automatically
CREATE OR REPLACE FUNCTION hsae_set_geom() RETURNS TRIGGER AS $$
BEGIN
  NEW.geom := ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat), 4326);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_basins_geom
BEFORE INSERT OR UPDATE ON hsae_basins
FOR EACH ROW EXECUTE FUNCTION hsae_set_geom();

-- Time-series water balance
CREATE TABLE IF NOT EXISTS hsae_timeseries (
    id              BIGSERIAL PRIMARY KEY,
    basin_id        TEXT REFERENCES hsae_basins(id),
    obs_date        DATE NOT NULL,
    inflow_bcm      DOUBLE PRECISION,
    outflow_bcm     DOUBLE PRECISION,
    volume_bcm      DOUBLE PRECISION,
    gpm_rain_mm     DOUBLE PRECISION,
    s1_area_km2     DOUBLE PRECISION,
    s2_ndwi         DOUBLE PRECISION,
    evap_pm_bcm     DOUBLE PRECISION,
    power_mw        DOUBLE PRECISION,
    mb_error_pct    DOUBLE PRECISION,
    forensic_score  DOUBLE PRECISION,
    equity_pct      DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (basin_id, obs_date)
);
-- TimescaleDB hypertable (comment out if not using TimescaleDB)
-- SELECT create_hypertable('hsae_timeseries','obs_date');

-- Legal alerts log
CREATE TABLE IF NOT EXISTS hsae_alerts_log (
    id              BIGSERIAL PRIMARY KEY,
    basin_id        TEXT REFERENCES hsae_basins(id),
    alert_type      TEXT,
    value           DOUBLE PRECISION,
    threshold       DOUBLE PRECISION,
    article_refs    TEXT[],
    sent_telegram   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Forecast store
CREATE TABLE IF NOT EXISTS hsae_forecasts (
    id              BIGSERIAL PRIMARY KEY,
    basin_id        TEXT REFERENCES hsae_basins(id),
    run_date        DATE,
    forecast_date   DATE,
    inflow_bcm      DOUBLE PRECISION,
    ci_lower        DOUBLE PRECISION,
    ci_upper        DOUBLE PRECISION,
    model_type      TEXT,
    r2_score        DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Useful spatial view
CREATE OR REPLACE VIEW hsae_basins_geo AS
SELECT id, name, river, countries, cap_bcm,
       ST_AsGeoJSON(geom)::json AS geojson
FROM hsae_basins;
"""

# ══════════════════════════════════════════════════════════════════════════════
# 2. FASTAPI ROUTER
# ══════════════════════════════════════════════════════════════════════════════

FASTAPI_ROUTER = """
# hsae_api.py  –  FastAPI REST interface for HSAE
# Run: uvicorn hsae_api:app --host 0.0.0.0 --port 8000 --reload

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncpg, os, json
from datetime import date

app = FastAPI(
    title="HydroSovereign HSAE API",
    description="Open REST API for hydrological data and legal analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DB_DSN = os.getenv("DATABASE_URL", "postgresql://hsae:password@db:5432/hsae")


async def get_db():
    return await asyncpg.connect(DB_DSN)


@app.get("/basins", tags=["Basins"])
async def list_basins(continent: Optional[str] = None,
                      min_cap: float = 0.0):
    \"\"\"List all basins with optional filters.\"\"\"
    conn = await get_db()
    rows = await conn.fetch(
        "SELECT id, name, river, countries, cap_bcm, lat, lon "
        "FROM hsae_basins WHERE cap_bcm >= $1 ORDER BY cap_bcm DESC",
        min_cap,
    )
    await conn.close()
    return [dict(r) for r in rows]


@app.get("/basins/{basin_id}/timeseries", tags=["Data"])
async def get_timeseries(
    basin_id: str,
    start: date = Query(...),
    end:   date = Query(...),
):
    \"\"\"Return water balance time-series for a basin.\"\"\"
    conn = await get_db()
    rows = await conn.fetch(
        "SELECT * FROM hsae_timeseries "
        "WHERE basin_id=$1 AND obs_date BETWEEN $2 AND $3 "
        "ORDER BY obs_date",
        basin_id, start, end,
    )
    await conn.close()
    if not rows:
        raise HTTPException(404, "No data for this basin/period")
    return [dict(r) for r in rows]


@app.get("/basins/{basin_id}/forecast", tags=["AI Forecast"])
async def get_forecast(basin_id: str):
    \"\"\"Return latest 7-day forecast.\"\"\"
    conn = await get_db()
    rows = await conn.fetch(
        "SELECT * FROM hsae_forecasts WHERE basin_id=$1 "
        "ORDER BY forecast_date LIMIT 7",
        basin_id,
    )
    await conn.close()
    return [dict(r) for r in rows]


@app.get("/basins/{basin_id}/legal", tags=["Legal"])
async def get_legal_status(basin_id: str):
    \"\"\"Return latest legal compliance status.\"\"\"
    conn = await get_db()
    row = await conn.fetchrow(
        "SELECT equity_pct, forensic_score, mb_error_pct "
        "FROM hsae_timeseries WHERE basin_id=$1 "
        "ORDER BY obs_date DESC LIMIT 1",
        basin_id,
    )
    await conn.close()
    if not row:
        raise HTTPException(404, "No data")
    eq = float(row["equity_pct"] or 50)
    return {
        "equity_pct":      eq,
        "forensic_score":  float(row["forensic_score"] or 0),
        "mb_error_pct":    float(row["mb_error_pct"] or 0),
        "art5_triggered":  eq < 60,
        "art7_triggered":  eq < 50,
        "art9_triggered":  bool(row["forensic_score"] and row["forensic_score"] > 50),
    }
"""

# ══════════════════════════════════════════════════════════════════════════════
# 3. DOCKER COMPOSE
# ══════════════════════════════════════════════════════════════════════════════

DOCKER_COMPOSE = """
# docker-compose.yml  –  HSAE Full Stack
version: "3.9"

services:

  db:
    image: postgis/postgis:16-3.4
    container_name: hsae_db
    restart: always
    environment:
      POSTGRES_DB:       hsae
      POSTGRES_USER:     hsae
      POSTGRES_PASSWORD: hsae_secret
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./hsae_devops.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: hsae_api
    restart: always
    environment:
      DATABASE_URL: postgresql://hsae:hsae_secret@db:5432/hsae
    ports:
      - "8000:8000"
    depends_on:
      - db
    command: >
      uvicorn hsae_api:app --host 0.0.0.0 --port 8000 --workers 2

  app:
    build:
      context: .
      dockerfile: Dockerfile.app
    container_name: hsae_streamlit
    restart: always
    environment:
      DATABASE_URL: postgresql://hsae:hsae_secret@db:5432/hsae
    ports:
      - "8501:8501"
    depends_on:
      - db
      - api
    command: streamlit run app.py --server.port 8501 --server.address 0.0.0.0

volumes:
  pgdata:
"""

# ══════════════════════════════════════════════════════════════════════════════
# 4. DOCKERFILE.APP
# ══════════════════════════════════════════════════════════════════════════════

DOCKERFILE_APP = """
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1
CMD ["streamlit", "run", "app.py",
     "--server.port=8501", "--server.address=0.0.0.0",
     "--server.headless=true"]
"""

# ══════════════════════════════════════════════════════════════════════════════
# 5. GITHUB ACTIONS CI/CD
# ══════════════════════════════════════════════════════════════════════════════

GITHUB_CI = """
# .github/workflows/hsae_ci.yml  –  HSAE CI/CD Pipeline

name: HSAE CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  release:
    types: [created]

env:
  PYTHON_VERSION: "3.11"

jobs:

  # ── 1. Lint & Test ─────────────────────────────────────────────────────────
  test:
    name: 🧪 Lint, Test & Syntax Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest flake8 black

      - name: Syntax check all Python files
        run: |
          python -m py_compile app.py hsae_v430.py hsae_v990.py \\
            hsae_intro.py hsae_alerts.py hsae_science.py hsae_legal.py

      - name: Lint (flake8)
        run: flake8 . --max-line-length=100 --exclude=.git,__pycache__

      - name: Run tests
        run: pytest tests/ -v --tb=short

  # ── 2. Build & Push Docker ──────────────────────────────────────────────────
  docker:
    name: 🐳 Build & Push Docker
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USER }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.app
          push: true
          tags: |
            ${{ secrets.DOCKERHUB_USER }}/hsae:latest
            ${{ secrets.DOCKERHUB_USER }}/hsae:${{ github.sha }}

  # ── 3. Publish to PyPI ──────────────────────────────────────────────────────
  pypi:
    name: 📦 Publish to PyPI
    runs-on: ubuntu-latest
    needs: test
    if: github.event_name == 'release'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}

  # ── 4. Deploy to Streamlit Cloud ────────────────────────────────────────────
  deploy:
    name: 🚀 Deploy to Streamlit Cloud
    runs-on: ubuntu-latest
    needs: docker
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Trigger Streamlit Cloud redeploy
        run: |
          curl -X POST "${{ secrets.STREAMLIT_WEBHOOK_URL }}"
"""

# ══════════════════════════════════════════════════════════════════════════════
# 6. REQUIREMENTS.TXT
# ══════════════════════════════════════════════════════════════════════════════

REQUIREMENTS = """streamlit>=1.35
earthengine-api>=0.1.400
geemap>=0.31
folium>=0.16
streamlit-folium>=0.20
pandas>=2.1
numpy>=1.26
plotly>=5.20
scikit-learn>=1.4
requests>=2.31
asyncpg>=0.29
fastapi>=0.110
uvicorn[standard]>=0.29
reportlab>=4.1
fpdf2>=2.7
python-telegram-bot>=21.0
geopandas>=0.14
rasterio>=1.3
"""

# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT DEVOPS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def render_devops_page() -> None:
    """DevOps & Integration dashboard — show configs + copy buttons."""

    st.markdown("""
<style>
.devops-card{background:linear-gradient(135deg,#0d1117,#0f1923);
  border:2px solid #22c55e;border-radius:16px;padding:1.2rem 1.5rem;
  margin-bottom:1rem;box-shadow:0 8px 32px rgba(34,197,94,.15);}
.devops-card h3{color:#4ade80;}
</style>""", unsafe_allow_html=True)

    st.markdown("""
<div class="devops-card">
  <h3>🛠 DevOps & Advanced Integration</h3>
  <p style="color:#94a3b8;font-size:.85rem;">
    PostgreSQL + PostGIS &bull; FastAPI &bull; Docker &bull;
    GitHub Actions CI/CD &bull; PyPI Auto-Publish
  </p>
</div>""", unsafe_allow_html=True)

    d1, d2, d3, d4, d5 = st.tabs([
        "🗄 PostGIS Schema",
        "🚀 FastAPI",
        "🐳 Docker",
        "⚙ CI/CD",
        "📦 Requirements",
    ])

    with d1:
        st.subheader("PostgreSQL + PostGIS Schema")
        st.code(POSTGRES_SCHEMA, language="sql")
        st.download_button("⬇ hsae_devops.sql",
            POSTGRES_SCHEMA.encode(), "hsae_devops.sql", "text/plain",
            key="dl_sql")

    with d2:
        st.subheader("FastAPI REST Router")
        st.info(
            "**Endpoints:**\n"
            "- `GET /basins` — list all basins\n"
            "- `GET /basins/{id}/timeseries?start=&end=` — water balance data\n"
            "- `GET /basins/{id}/forecast` — 7-day AI forecast\n"
            "- `GET /basins/{id}/legal` — compliance status\n\n"
            "Run: `uvicorn hsae_api:app --reload`\n"
            "Docs: http://localhost:8000/docs"
        )
        st.code(FASTAPI_ROUTER, language="python")
        st.download_button("⬇ hsae_api.py",
            FASTAPI_ROUTER.encode(), "hsae_api.py", "text/plain",
            key="dl_api")

    with d3:
        st.subheader("Docker Compose — Full Stack")
        st.code(DOCKER_COMPOSE, language="yaml")
        st.code(DOCKERFILE_APP, language="dockerfile")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇ docker-compose.yml",
                DOCKER_COMPOSE.encode(), "docker-compose.yml", "text/plain",
                key="dl_compose")
        with col2:
            st.download_button("⬇ Dockerfile.app",
                DOCKERFILE_APP.encode(), "Dockerfile.app", "text/plain",
                key="dl_dockerfile")
        st.code(
            "# One command to run everything:\ndocker compose up -d",
            language="bash",
        )

    with d4:
        st.subheader("GitHub Actions CI/CD Pipeline")
        st.code(GITHUB_CI, language="yaml")
        st.download_button("⬇ hsae_ci.yml",
            GITHUB_CI.encode(), "hsae_ci.yml", "text/plain",
            key="dl_ci")
        st.info(
            "**Required GitHub Secrets:**\n"
            "- `DOCKERHUB_USER` / `DOCKERHUB_TOKEN`\n"
            "- `PYPI_API_TOKEN`\n"
            "- `STREAMLIT_WEBHOOK_URL`"
        )

    with d5:
        st.subheader("requirements.txt")
        st.code(REQUIREMENTS, language="text")
        st.download_button("⬇ requirements.txt",
            REQUIREMENTS.encode(), "requirements.txt", "text/plain",
            key="dl_req")
