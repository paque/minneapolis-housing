# Minneapolis Housing Agent Guide

## Purpose

This project is a public civic data website and data pipeline for exploring Minneapolis Public Housing Authority / Community Housing Resources scattered-site housing properties. The product helps users inspect where properties are, what public records identify them, and how the portfolio changes over time.

## Stack

- Astro
- React islands
- TypeScript
- Tailwind CSS
- MapLibre GL JS
- Python ETL
- Static CSV, JSON, and GeoJSON outputs
- GitHub Actions
- Cloudflare Pages target

Do not introduce Next.js, Vercel-specific architecture, Supabase, PostGIS, a live database, a custom tile server, Google Maps, Mapbox paid dependencies, Kubernetes, or resident-level data collection.

## Commands

```bash
npm install
npm run dev
npm run check
npm run build
python -m venv .venv
pip install -r etl/requirements.txt
python etl/fetch_public_sources.py
python etl/run_pipeline.py
python etl/run_pipeline.py --validate-config
```

On Windows shells where `python` resolves to the Microsoft Store alias, use `py` in place of `python`.

## Static-First Architecture

The MVP has no live backend. The ETL writes generated files to `data/public/` and `public/data/`:

- `properties.csv`
- `properties.json`
- `properties.geojson`
- `property-facts.csv`
- `property-facts.json`
- `property-permits.csv`
- `property-permits.json`
- `property-history.json`
- `sources.json`
- `changelog.json`

The website reads these files at build time or in the browser. Keep changes inspectable, versionable, and compatible with static hosting.

## Data Pipeline Rules

- Use official exports, documented public datasets, APIs, and stable public files.
- Do not add prohibited scraping or brittle web scraping.
- Do not fabricate properties, parcels, addresses, owners, source records, or evidence.
- If source files or URLs are missing, preserve the ingestion structure and fail with a clear message describing the expected files and schemas.
- Use `etl/fetch_public_sources.py` to refresh official HUD, Minneapolis assessing, Minnesota Geospatial Commons / MetroGIS parcel, City of Minneapolis Construction and Code Services permit, and MPHA portfolio-context inputs.
- Preserve the ELT boundary: land source-scope snapshots first, then normalize/filter/merge into required inputs `properties_source.csv`, `source_records.csv`, and `property_evidence.csv`; optional inputs are `change_events.csv`, `property_facts.csv`, and `property_permits.csv`.
- Do not encode candidate filters into extraction URLs unless the source scope itself requires it. Examples: HUD extraction may scope to MPHA participant `MN002`; scattered-site filtering happens after landing. Minneapolis assessing extraction lands full annual tables.
- Raw snapshot `.jsonl` files under `data/raw/source-snapshots/` are generated and git-ignored because they are large. Keep manifests, hashes, transformed CSVs, and public outputs inspectable.
- Normalize parcel IDs and addresses, validate required fields, compute confidence levels, match permits by normalized parcel APN, and write public CSV, JSON, and GeoJSON outputs.
- Keep property-level public-records work separate from resident-level information.

## Confidence Labels

- `confirmed`: Direct public-source evidence identifies the property as MPHA/CHR scattered-site housing or equivalent.
- `likely`: Owner, taxpayer, parcel, or address evidence strongly suggests inclusion.
- `uncertain`: Evidence is weak, incomplete, stale, or conflicting.
- `excluded`: Evidence suggests the property should not be included.

## Privacy Boundary

This project is property-level public-records work only. Do not collect or publish resident names, tenant records, household details, occupancy details tied to people, voucher records, or other resident-level information.

## MVP Constraint

Do not use a live database for the MVP. Future upgrades may add PMTiles, Cloudflare R2, D1, or PostGIS only if static files stop being sufficient and the docs are updated with a clear reason.
