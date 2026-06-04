# Data Model

The public site uses generated files that reflect these logical entities. Public JSON envelopes include `schema_version` and `generated_at`; CSV files contain only the entity columns listed below.

## properties

- `property_id`
- `canonical_address`
- `city`
- `state`
- `zip`
- `parcel_id`
- `latitude`
- `longitude`
- `current_owner_name`
- `current_taxpayer_name`
- `property_type`
- `estimated_unit_count`
- `current_status`
- `confidence_level`
- `confidence_score`
- `public_notes`
- `first_seen_date`
- `last_seen_date`
- `is_current`
- `detail_url_slug`

## property_versions

- `property_id`
- `version_id`
- `valid_from`
- `valid_to`
- `is_current`
- `parcel_id`
- `owner_name`
- `taxpayer_name`
- `address`
- `property_type`
- `estimated_unit_count`
- `status`
- `confidence_level`
- `confidence_score`
- `source_run_id`
- `change_reason`

## source_records

- `source_id`
- `source_name`
- `source_agency`
- `source_type`
- `source_url`
- `retrieved_at`
- `record_date`
- `raw_file_uri`
- `sha256_hash`
- `public_citation_text`

## property_evidence

- `evidence_id`
- `property_id`
- `source_id`
- `claim_type`
- `claim_value`
- `confidence_contribution`
- `evidence_note`

## change_events

- `event_id`
- `property_id`
- `event_date`
- `event_type`
- `old_value`
- `new_value`
- `source_id`
- `public_note`

## property_facts

- `property_id`
- `parcel_id`
- `source_ids`
- `sale_date`
- `sale_value`
- `assessed_land_value`
- `assessed_building_value`
- `assessed_total_value`
- `tax_year`
- `market_year`
- `total_tax`
- `use_classes`
- `zoning`
- `land_use`
- `parcel_area_sqft`
- `acres`
- `year_built`
- `finished_sqft`
- `above_ground_area`
- `below_ground_area`
- `total_units`
- `building_use`

`property_facts.csv` has at most one row per `property_id`. The pipeline rejects duplicate fact rows and fact rows that reference an unknown property.

## property_permits

- `property_id`
- `parcel_id`
- `permit_number`
- `permit_type`
- `work_type`
- `occupancy_type`
- `status`
- `milestone`
- `value`
- `dwelling_units_new`
- `dwelling_units_eliminated`
- `issue_date`
- `complete_date`
- `work_description`
- `match_method`
- `source_id`

Permit rows are matched to exported properties by normalized parcel APN. The public permit output omits applicant names, applicant addresses, phone numbers, and emails.

## etl_runs

- `run_id`
- `started_at`
- `completed_at`
- `status`
- `git_commit`
- `row_counts`
- `warnings`

The current MVP writes the latest ETL run metadata to `data/processed/etl-run-last.json` when a full generation succeeds.

## Public Files

- `properties.csv`: current property rows with confidence fields.
- `properties.json`: `properties` array.
- `properties.geojson`: point `FeatureCollection`; geometry is omitted for rows without latitude or longitude.
- `property-facts.csv`: property-fact rows.
- `property-facts.json`: `property_facts` array.
- `property-permits.csv`: property-permit rows.
- `property-permits.json`: `property_permits` array.
- `property-history.json`: `property_versions` and `change_events` arrays.
- `sources.json`: `source_records` and `property_evidence` arrays.
- `changelog.json`: reverse-date sorted `changes` array.
