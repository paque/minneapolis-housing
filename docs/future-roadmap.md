# Future Roadmap

This roadmap lists concrete next work while preserving the static-first MVP.

## Data Quality

- After each source refresh, review `data/raw/fetch-summary.json` and `data/processed/etl-run-last.json` for source row counts, exported row counts, hashes, and warnings.
- Keep `data/raw/properties_source.csv`, `data/raw/source_records.csv`, `data/raw/property_evidence.csv`, `data/raw/change_events.csv`, `data/raw/property_facts.csv`, and `data/raw/property_permits.csv` versioned by default. Move a generated file out of Git only after documenting the file name, current size, replacement storage location, and review workflow.
- Document each new `claim_type` in methodology before using it in `property_evidence.csv`.
- Add direct public property-level sources only when they identify specific addresses, parcels, buildings, or developments; portfolio-level context alone stays `likely` support.

## Site Features

- Add property-list filters for confidence, status, source year, and presence of matched permits.
- Improve property detail pages by grouping evidence by `source_id`, then by `claim_type`.
- Add a map filter panel that uses existing `properties.geojson` fields before adding new data files.
- Keep the default blank MapLibre style available even if a public basemap style is configured with `PUBLIC_BASEMAP_STYLE_URL`.

## Data Operations

- Keep `.github/workflows/scheduled-etl.yml` non-committing until maintainers approve an explicit generated-file commit workflow.
- Before adding PMTiles, document which geography layer cannot be served as the current point GeoJSON.
- Before adding Cloudflare R2, document each artifact path, size in MB, and the reason GitHub web review cannot handle it.
- Before adding Cloudflare D1, document the query that static JSON cannot answer.
- Before adding PostGIS, document the spatial analysis that cannot be completed in the Python ETL.

## Publishing

- Deploy with Cloudflare Pages build command `npm run build`.
- Publish the `dist` directory.
- Use Node version `22`.
