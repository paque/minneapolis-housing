# Cost Model

The MVP cost model is static hosting plus GitHub Actions. There is no live database, API service, serverless function layer, custom tile server, paid map provider, or Mapbox dependency in this repo.

## Current Cost Controls

- Cloudflare Pages build command: `npm run build`.
- Cloudflare Pages output directory: `dist`.
- Cloudflare Pages Node version: `22`.
- GitHub Actions CI runs `npm install`, `npm run check`, `npm run build`, installs `etl/requirements.txt`, and runs `python etl/run_pipeline.py --validate-config`.
- Scheduled ETL runs every Monday at `08:23 UTC` from `.github/workflows/scheduled-etl.yml`; it fetches public sources, runs the ETL, and builds the site.
- Scheduled ETL intentionally does not commit generated files.
- Public outputs are static files copied to `public/data/`.
- Raw JSONL snapshots under `data/raw/source-snapshots/` are git-ignored; manifests, hashes, transformed CSV inputs, summaries, and public outputs remain inspectable.
- The default MapLibre style is `public/data/map-style.json`, a blank static style with no tile requests.

## Current Data Scale

The latest successful ETL run in this checkout produced:

- 738 property rows.
- 735 property-fact rows.
- 1,585 matched permit rows.
- 3,486 evidence rows.
- 2,764 change events.

## Why Static Files

Static generated files remove the operating cost of a live database, API service, serverless function layer, and tile server. They also make public data review concrete because CSV, JSON, GeoJSON, summaries, and source manifests can be versioned and diffed.

## Cost Change Rules

Document a reason before adding any of these:

- PMTiles for parcel outlines or historical geography layers.
- Cloudflare R2 for archived raw snapshots or large generated artifacts.
- Cloudflare D1 for query workflows that cannot be served by static JSON.
- PostGIS for spatial analysis that cannot be completed inside the ETL.
- A non-static basemap provider.
