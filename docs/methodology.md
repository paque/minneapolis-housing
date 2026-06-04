# Methodology

This project reconciles public property-level records that identify or suggest MPHA/CHR scattered-site housing properties. It publishes property records, source evidence, confidence labels, property facts, permits, and change events.

## Source Principles

- Use official exports, documented public datasets, official APIs, or stable public files.
- Record source agency, source URL, record date, retrieval timestamp, raw file URI, hash when available, and public citation text.
- Avoid fragile scraping.
- Do not collect resident-level or tenant-level information.

## Current Sources

- `hud_public_housing_buildings_mn002`: HUD Public Housing Buildings FeatureServer records for MPHA `MN002`; development `MN002000002 / SCATTERED SITES` is direct public-source evidence.
- `minneapolis_assessing_parcels_2023`, `minneapolis_assessing_parcels_2024`, and `minneapolis_assessing_parcels_2025`: full annual City of Minneapolis assessing parcel table snapshots; these contribute owner/taxpayer, address, classification, unit-count, coordinate, and property-fact evidence after normalization.
- `metrogis_hennepin_minneapolis_parcels_current`: Minnesota Geospatial Commons / MetroGIS Hennepin County parcel slice for Minneapolis; this contributes parcel IDs, owner names, taxpayer names, property classes, and parcel geometry.
- `minneapolis_ccs_permits_current`: City of Minneapolis Construction and Code Services permit records; permits are matched to exported properties by normalized parcel APN after extraction.
- `mpha_properties_overview`: MPHA public properties overview; this is portfolio context for CHR scattered-site housing and does not confirm an individual parcel without parcel-level evidence.

Extraction lands source-scope snapshots before candidate filtering. Candidate logic is part of transformation and is documented in source evidence notes, not hidden in source URLs.

The current generated dataset contains 738 properties, 735 property fact rows, 1,585 permit rows, 3,486 evidence rows, and 2,764 change events.

## Confidence Labels

- `confirmed`: Direct public-source evidence identifies the property as MPHA/CHR scattered-site housing or equivalent.
- `likely`: Owner, taxpayer, parcel, or address evidence strongly suggests inclusion.
- `uncertain`: Evidence is weak, incomplete, stale, or conflicting.
- `excluded`: Evidence suggests the property should not be included.

## Evidence Notes

Each evidence row ties a property to a source and claim. Evidence notes must state the public source basis for the claim and why the claim contributes to the confidence label.

Direct HUD `MN002000002 / SCATTERED SITES` evidence can support `confirmed`. Owner, taxpayer, parcel, or contextual MPHA/CHR evidence supports `likely` unless another property-level source directly confirms scattered-site status. Weak, incomplete, stale, or conflicting evidence supports `uncertain`.

## Change Events

Change events describe public portfolio changes such as additions, removals, owner/taxpayer changes, property classification changes, estimated unit-count changes, status changes, or confidence changes. Source-backed events must include a `source_id`; source-agnostic system comparisons can leave `source_id` blank.

## Permit And Fact Enrichment

`property_facts.csv` condenses parcel-level property facts from public parcel and assessing sources into one row per exported property. `property_permits.csv` publishes matched permit metadata, permit status, dates, value, unit changes, and work descriptions. Permit output excludes applicant names, applicant addresses, phone numbers, and emails.

## Privacy Boundary

The site must publish property-level public records only. It must not publish resident names, tenant records, household details, occupancy details tied to people, voucher records, applicant contact details, or other resident-level data.
