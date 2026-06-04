# Data Pipeline

The pipeline lives in `etl/` and follows an ELT shape:

1. Extract source-scope public snapshots into `data/raw/source-snapshots/`.
2. Transform landed rows into normalized property, source, evidence, change-event, property-fact, and permit CSVs in `data/raw/`.
3. Load/export static public CSV, JSON, and GeoJSON files to `data/public/` and `public/data/`.

## Source Fetching

Run:

```bash
python etl/fetch_public_sources.py
```

The current fetcher lands:

- HUD Public Housing Buildings FeatureServer records for MPHA participant `MN002`. The transform step identifies development `MN002000002 / SCATTERED SITES`.
- City of Minneapolis Construction and Code Services permit records. The transform step matches permits to exported properties by normalized parcel APN.
- City of Minneapolis Assessing Department Parcel Data 2023, 2024, and 2025 full annual table snapshots.
- Minnesota Geospatial Commons opt-in open parcel compilation for the full Hennepin/Minneapolis parcel slice, including parcel geometry.
- MPHA public properties overview as portfolio context for CHR scattered-site homes.

It does not request HUD resident demographic fields, tenant records, household records, voucher records, or resident occupancy fields. Public permit outputs omit applicant names, applicant addresses, phone numbers, and emails.

Bulky JSONL snapshots are generated and git-ignored. `data/raw/source-manifest.json`, `data/raw/fetch-summary.json`, and `data/raw/source_records.csv` retain row counts, retrieval timestamps, source scopes, raw file paths, and hashes.

## Inputs

Required:

- `data/raw/properties_source.csv`
- `data/raw/source_records.csv`
- `data/raw/property_evidence.csv`

Optional:

- `data/raw/change_events.csv`
- `data/raw/property_facts.csv`
- `data/raw/property_permits.csv`

The ETL does not fetch or scrape prohibited sources. Prefer official exports, documented public datasets, official APIs, and stable public files.

## Steps

1. Land each source-scope snapshot before candidate filtering.
2. Normalize parcel IDs, addresses, owner/taxpayer names, unit counts, source dates, and coordinates.
3. Transform Minneapolis assessing Hennepin County HARN X/Y coordinates to WGS84 with `pyproj`.
4. Build candidate/evidence records from HUD scattered-site evidence, Minneapolis assessing owner/taxpayer evidence, MetroGIS owner/taxpayer evidence, and MPHA portfolio context.
5. Validate required input files, headers, and values.
6. Validate coordinates and parse units/booleans.
7. Normalize source records and compute missing hashes for local raw files that exist at the recorded `raw_file_uri`.
8. Validate evidence references to known properties and sources.
9. Normalize optional property fact rows and permit rows; reject facts or permits that reference unknown properties or sources.
10. Compute confidence labels and scores.
11. Build current property versions and annual change events.
12. Export public CSV, JSON, and GeoJSON files.
13. Write `data/processed/etl-run-last.json` with run timestamps, status, row counts, warnings, and git commit when available.

## Public Outputs

The ETL writes these files to `data/public/` and copies them to `public/data/`:

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

Current row counts from the latest successful run:

- `properties`: 738
- `property_versions`: 738
- `source_records`: 7
- `property_evidence`: 3,486
- `change_events`: 2,764
- `property_facts`: 735
- `property_permits`: 1,585

## Missing Inputs

Normal generation fails when any required input is absent. This is intentional because the project must not invent records.

CI can run:

```bash
python etl/run_pipeline.py --validate-config
```

That mode exits successfully when required inputs are missing after printing the exact expected file paths and schemas. When required inputs exist, it reads required schemas and any optional schemas that are present.
