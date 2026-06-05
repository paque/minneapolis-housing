# ELT / ETL Pipeline

The pipeline lands public source snapshots first, transforms those snapshots into normalized CSV inputs, then exports static files consumed by the Astro site. It does not use a live database, scrape fragile web pages, or create mock property records.

## Current Checkout

The current source fetch was retrieved at `2026-06-03T20:27:17Z`, with the city limits layer refreshed at `2026-06-05T15:15:09Z`. The latest successful ETL run completed at `2026-06-05T15:21:34Z` with these row counts:

- `properties`: 739
- `property_versions`: 739
- `source_records`: 13
- `property_evidence`: 3,481
- `change_events`: 2,753
- `property_facts`: 730
- `property_permits`: 1,571

The counts above come from `data/processed/etl-run-last.json`. Source extraction counts and snapshot hashes are in `data/raw/fetch-summary.json`.

## Commands

Run from the repository root:

```bash
python -m venv .venv
pip install -r etl/requirements.txt
python etl/fetch_public_sources.py
python etl/run_pipeline.py
```

On Windows, if `python --version` returns the Microsoft Store alias message, replace `python` with `py` in the commands above.

Use `--transform-only` to reuse existing landed JSONL snapshots and regenerate transformed CSV inputs:

```bash
python etl/fetch_public_sources.py --transform-only
```

Use `--validate-config` to check the ETL scaffold and input schemas without generating public outputs:

```bash
python etl/run_pipeline.py --validate-config
```

If the three required inputs are missing, validation mode exits successfully after printing the exact expected file paths and schemas. Normal generation exits with code `2` instead of inventing records.

## Source Fetching

`etl/fetch_public_sources.py` writes JSONL snapshots under `data/raw/source-snapshots/`, writes `data/raw/source-manifest.json`, then writes transformed CSV inputs under `data/raw/`.

Current source adapters:

- `hud_public_housing_buildings_mn002`: HUD Public Housing Buildings FeatureServer records where `PARTICIPANT_CODE='MN002'`; transform logic treats development `MN002000002 / SCATTERED SITES` as direct scattered-site evidence.
- `metrogis_hennepin_minneapolis_parcels_current`: Minnesota Geospatial Commons / MetroGIS open parcels where `ctu_name='Minneapolis' AND co_name='Hennepin'`; transform logic filters owner and taxpayer names after landing.
- `minneapolis_ccs_permits_current`: City of Minneapolis Construction and Code Services permits with `where=1=1`; transform logic matches public permit records to exported properties by normalized parcel APN.
- `minneapolis_assessing_parcels_2023`, `minneapolis_assessing_parcels_2024`, and `minneapolis_assessing_parcels_2025`: City of Minneapolis annual assessing parcel tables with `where=1=1`; transform logic normalizes parcel IDs, addresses, owner/taxpayer names, property types, unit counts, and Hennepin County HARN X/Y coordinates.
- `mpha_properties_overview`: official MPHA properties overview parsed into `mpha_properties_overview.jsonl`; listed high-rise and townhome properties can confirm official portfolio records when matched, while the scattered-site entry provides CHR portfolio context.
- `minneapolis_city_limits`, `minneapolis_city_council_wards`, `minneapolis_neighborhoods`, `minneapolis_communities`, `minneapolis_police_precincts`, and `minneapolis_mpd_sectors`: City of Minneapolis boundary layers used for map overlays and property geography enrichment.

The fetcher does not request resident demographic, tenant, household, voucher, or resident occupancy records. Public permit exports omit applicant names, applicant addresses, phone numbers, and emails.

## Property Identity And Dedupe

The transformed `properties_source.csv` is property-level, not source-row-level. The ETL consolidates source records into one property when reliable parcel identity exists.

General rules:

- Use normalized parcel ID as the strongest identity key.
- Match HUD scattered-site records to parcels by unique exact normalized address before using point geometry. Strip apartment/unit suffixes for this identity match.
- Use HUD point geometry only when the point parcel owner or taxpayer also matches public-housing patterns.
- Match MPHA overview listings by exact address first, then conservative address fallbacks: direction-insensitive exact address, same-street public-housing candidate plus matching unit count, or a nearby same-street MPHA-owned candidate.
- Keep source-specific addresses in evidence notes or official listed-address fields when they differ from the parcel canonical address.
- Preserve unmatched HUD and MPHA rows as address-only records instead of inventing parcel IDs.

One-off rules:

- Do not add silent alias guesses in code.
- A one-off alias or campus-address override must document the source address, chosen parcel ID, public evidence, and reason the generalized rules are insufficient.
- Until a one-off is documented, leave the source row address-only or unmatched.

## Inputs

Required for `python etl/run_pipeline.py`:

- `data/raw/properties_source.csv`
- `data/raw/source_records.csv`
- `data/raw/property_evidence.csv`

Optional inputs read when present:

- `data/raw/change_events.csv`
- `data/raw/property_facts.csv`
- `data/raw/property_permits.csv`

Raw JSONL snapshots in `data/raw/source-snapshots/` are generated and git-ignored. Keep `data/raw/source-manifest.json`, `data/raw/fetch-summary.json`, transformed CSV inputs, and public outputs inspectable.

## Schemas

`properties_source.csv`

```csv
property_id,canonical_address,city,state,zip,parcel_id,latitude,longitude,current_owner_name,current_taxpayer_name,official_property_name,official_listed_address,is_official_mpha_listing,property_type,estimated_unit_count,unit_count_source,unit_count_confidence,unit_count_notes,ward,neighborhood,community,police_precinct,police_sector,current_status,public_notes,first_seen_date,last_seen_date,is_current,detail_url_slug
```

`source_records.csv`

```csv
source_id,source_name,source_agency,source_type,source_url,retrieved_at,record_date,raw_file_uri,sha256_hash,public_citation_text
```

`property_evidence.csv`

```csv
evidence_id,property_id,source_id,claim_type,claim_value,confidence_contribution,evidence_note
```

`change_events.csv`

```csv
event_id,property_id,event_date,event_type,old_value,new_value,source_id,public_note
```

`property_facts.csv`

```csv
property_id,parcel_id,source_ids,sale_date,sale_value,assessed_land_value,assessed_building_value,assessed_total_value,tax_year,market_year,total_tax,use_classes,zoning,land_use,parcel_area_sqft,acres,year_built,finished_sqft,above_ground_area,below_ground_area,total_units,inferred_unit_count,best_unit_count,unit_count_source,unit_count_confidence,unit_count_notes,assessed_value_per_unit,building_use
```

`property_permits.csv`

```csv
property_id,parcel_id,permit_number,permit_type,work_type,occupancy_type,status,milestone,value,dwelling_units_new,dwelling_units_eliminated,issue_date,complete_date,work_description,match_method,source_id
```

## Outputs

The pipeline writes these files to `data/public/` and copies the same files to `public/data/`:

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

`public/data/map-style.json` is a committed static MapLibre style. It is not generated by this pipeline.
