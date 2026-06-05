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
- MPHA public properties overview as an official portfolio source for listed high-rise and townhome properties, plus context for CHR scattered-site homes.
- City of Minneapolis city limits, ward, neighborhood, community, police precinct, and MPD sector boundary layers.

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
3. Strip apartment/unit suffixes from addresses for parcel identity matching while preserving the source address in evidence.
4. Transform Minneapolis assessing Hennepin County HARN X/Y coordinates to WGS84 with `pyproj`.
5. Build candidate/evidence records from HUD scattered-site evidence, official MPHA portfolio listings, Minneapolis assessing owner/taxpayer evidence, and MetroGIS owner/taxpayer evidence.
6. Consolidate records to parcel-backed `property_id` values when parcel evidence is reliable; preserve address-only source rows when it is not.
7. Infer best unit counts only when reported counts are missing, including vacant land as 0 units and simple residential building-use labels as their implied counts.
8. Assign mapped properties to ward, neighborhood, community, precinct, and sector labels from landed boundary layers.
9. Validate required input files, headers, and values.
10. Validate coordinates and parse units/booleans.
11. Normalize source records and compute missing hashes for local raw files that exist at the recorded `raw_file_uri`.
12. Validate evidence references to known properties and sources.
13. Normalize optional property fact rows and permit rows; reject facts or permits that reference unknown properties or sources.
14. Compute confidence labels and scores.
15. Build current property versions and annual change events.
16. Export public CSV, JSON, and GeoJSON files.
17. Write `data/processed/etl-run-last.json` with run timestamps, status, row counts, warnings, and git commit when available.

## Property Matching And Dedupe Rules

Parcel ID is the primary identity key. A source record that reliably matches a parcel contributes evidence to the parcel-backed property row; it does not create a second row. Source-specific property IDs are reserved for HUD or MPHA rows that cannot be reliably matched to a parcel.

General rules:

- HUD scattered-site records match parcels by unique exact normalized address first. Apartment/unit suffixes are ignored for this identity match.
- HUD point geometry is a fallback only when the matched point parcel has a public-housing owner or taxpayer name.
- MPHA overview records match parcels by exact address first, then conservative normalized fallbacks such as direction-insensitive exact matches, same-street public-housing candidates with matching unit counts, or nearby MPHA-owned same-street candidates.
- Multiple official MPHA listings on the same parcel are consolidated into one property row with semicolon-separated official names or listed addresses.
- Owner/taxpayer evidence can add or strengthen a candidate, but it does not override a missing or ambiguous parcel match from another source.

Do-not-merge rules:

- Do not merge on unit count alone, proximity alone, same street alone, or broad fuzzy string matching.
- Do not attach HUD point-only records to parcels whose owner/taxpayer names do not match MPHA/CHR/public-housing patterns.
- Do not add silent one-off address aliases. If a one-off parcel alias is needed, document the source address, target parcel ID, evidence, and rationale before using it.
- Preserve ambiguous rows as address-only records until a stronger rule or documented override exists.

## Public Outputs

The ETL writes these files to `data/public/` and copies them to `public/data/`:

- `properties.csv`
- `properties.json`
- `properties.geojson`
- `civic-boundaries.geojson`
- `property-facts.csv`
- `property-facts.json`
- `property-permits.csv`
- `property-permits.json`
- `property-history.json`
- `sources.json`
- `changelog.json`

Current row counts from the latest successful run:

- `properties`: 739
- `property_versions`: 739
- `source_records`: 13
- `property_evidence`: 3,481
- `change_events`: 2,753
- `property_facts`: 730
- `property_permits`: 1,571
- `civic_boundary_features`: 125

## Missing Inputs

Normal generation fails when any required input is absent. This is intentional because the project must not invent records.

CI can run:

```bash
python etl/run_pipeline.py --validate-config
```

That mode exits successfully when required inputs are missing after printing the exact expected file paths and schemas. When required inputs exist, it reads required schemas and any optional schemas that are present.
