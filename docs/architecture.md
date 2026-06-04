# Architecture

Minneapolis Housing is a static-first civic data website. The MVP uses generated files instead of a live database, application server, custom tile server, paid map platform, or background worker.

## System Shape

```mermaid
flowchart LR
  A["Official public APIs and source pages"] --> B["Extract source-scope snapshots"]
  B --> C["Generated JSONL snapshots in data/raw/source-snapshots"]
  C --> D["Transform into required and optional data/raw CSV inputs"]
  D --> E["Export data/public static outputs"]
  E --> F["Copy identical files to public/data"]
  F --> G["Astro static build"]
  G --> H["Cloudflare Pages"]
```

The extraction stage lands source-scope snapshots before candidate filtering. The bulky JSONL snapshots are generated and git-ignored; source manifests, hashes, normalized CSV inputs, generated summaries, and public outputs remain inspectable.

## Frontend

Astro renders the public pages:

- Homepage
- Interactive map
- Searchable property list
- Property detail pages
- Methodology
- Data downloads
- Changelog
- Property characteristics and permit changes

MapLibre GL JS loads `public/data/properties.geojson` in the browser. The default style is `public/data/map-style.json`, a blank static style with no tile requests. Set `PUBLIC_BASEMAP_STYLE_URL` to a MapLibre style JSON URL or path to use a public basemap.

## Backend

The MVP backend is generated files:

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

These files are written to `data/public/` and copied to `public/data/`. They are inspectable in Git, cacheable on a CDN, and downloadable directly from the static site.

The latest full ETL run also writes `data/processed/etl-run-last.json`, which records run timestamps, status, row counts, warnings, and the git commit when available.

## Hosting

Cloudflare Pages configuration:

- Build command: `npm run build`
- Output directory: `dist`
- Node version: `22`

No paid backend service is required for the MVP.

## Future Layers

PMTiles, Cloudflare R2, D1, or PostGIS are outside the MVP. Add one only after documenting the static-file limit it solves, the new operating cost, and the public data workflow it changes.
