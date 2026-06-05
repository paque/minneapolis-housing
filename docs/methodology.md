# Methodology

This project reconciles public property-level records that identify or suggest MPHA/CHR public housing properties. It publishes property records, source evidence, confidence labels, property facts, permits, and change events.

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
- `mpha_properties_overview`: MPHA public properties overview; this confirms official listed high-rise and townhome properties when matched by address/parcel evidence and provides portfolio context for CHR scattered-site housing.
- `minneapolis_city_limits`, `minneapolis_city_council_wards`, `minneapolis_neighborhoods`, `minneapolis_communities`, `minneapolis_police_precincts`, and `minneapolis_mpd_sectors`: City of Minneapolis boundary layers used for civic overlays and property geography labels.

Extraction lands source-scope snapshots before candidate filtering. Candidate logic is part of transformation and is documented in source evidence notes, not hidden in source URLs.

The current generated dataset contains 739 properties, 13 source records, 730 property fact rows, 1,571 permit rows, 3,481 evidence rows, 2,753 change events, and 125 civic boundary features.

## Property Identity And Consolidation

The pipeline treats a normalized parcel ID as the strongest property identity key. When a source row can be reliably matched to a parcel, its evidence is attached to the parcel-backed `property_id` instead of creating a separate property row. Source-specific address-only property IDs are used only when no reliable parcel match exists.

General consolidation rules:

- Normalize addresses before matching by cleaning whitespace, mapping common street suffixes and compass directions, and stripping apartment/unit suffixes such as `Apt`, `Unit`, `Ste`, and `Suite` for parcel identity matching.
- Keep parcel-backed canonical addresses from parcel or assessing sources. Preserve source-specific addresses as evidence notes or official listed-address fields when they differ.
- Attach HUD scattered-site evidence to a parcel by unique exact normalized address first. HUD unit-level addresses, such as an apartment suffix, may attach to the base parcel address.
- Use HUD point geometry only as a fallback, and only when the point lands on a parcel whose owner or taxpayer also matches public-housing patterns. Do not attach HUD evidence to an unrelated parcel just because a point is nearby.
- Attach official MPHA overview listings by exact address first, then conservative normalized-address fallbacks such as direction-insensitive exact matches, same-street public-housing candidates with matching unit counts, or nearby MPHA-owned same-street candidates with a small house-number delta.
- When multiple official listings resolve to the same parcel, publish one property row and combine official names or listed addresses with semicolon-separated values.
- Owner/taxpayer evidence alone can make a property `likely`; direct HUD scattered-site evidence or a specific official MPHA portfolio record can make it `confirmed`.

Do-not-merge rules:

- Do not merge on unit count alone.
- Do not merge on same street alone when several public-housing candidates exist and no stronger address, owner, unit-count, or proximity signal resolves the ambiguity.
- Do not merge HUD point-only records onto parcels with non-public-housing owner/taxpayer names.
- Do not use broad fuzzy string matching, cross-street guessing, map proximity alone, or undocumented manual assumptions.
- Preserve unmatched source rows as address-only records when a match is plausible but not reliable enough.

One-off situations must be handled explicitly. A one-off parcel alias or campus/frontage-address relationship is allowed only when it is documented with the source address, target parcel ID, reason for the override, and the public evidence supporting it. Until that documentation exists, the row remains address-only or unmatched rather than being silently merged.

Examples from the current run:

- `3501 Bloomington Ave Apt 1` from HUD resolves to parcel `0202824410118` / `3501 BLOOMINGTON AVE` through the generalized unit-suffix stripping and exact base-address rule.
- Parker Skyview is published on parcel `1202924330192` with parcel address `1801 CENTRAL AVE NE` while preserving MPHA's official listed address `1815 NE Central Avenue`.
- Four HUD scattered-site records and five official MPHA overview records remain address-only because the available parcel evidence is missing or ambiguous.

## Civic Geography

Boundary layers are kept separate from property evidence. They do not confirm whether a parcel belongs in the public-housing portfolio. Instead, they provide geographic context for map overlays, property detail pages, list filters, and explorer summaries.

The current boundary export contains city limits, wards, neighborhoods, communities, police precincts, and MPD sectors. Mapped property points are assigned geography labels by point-in-polygon matching. Address-only properties without coordinates remain `Not listed` for these geography fields until a reliable parcel or point geometry is available.

## Unit Count Basis

Reported unit counts from public records are used first. When reported counts are missing, the pipeline may infer a best unit count from public property type or building-use labels. Examples include:

- `Single Family` or equivalent residential building-use labels infer 1 unit.
- `Duplex` infers 2 units.
- `Triplex` infers 3 units.
- `Fourplex` or equivalent labels infer 4 units.
- Vacant land property types infer 0 units.

Inferred values are published with `unit_count_source`, `unit_count_confidence`, and `unit_count_notes`. They support portfolio summaries such as total units by ward or assessed value per unit, but they are not resident counts, occupancy counts, or proof that a building currently houses a specific number of households.

## Confidence Labels

- `confirmed`: Direct public-source evidence identifies the property as an MPHA/CHR public housing property.
- `likely`: Owner, taxpayer, parcel, or address evidence strongly suggests inclusion.
- `uncertain`: Evidence is weak, incomplete, stale, or conflicting.
- `excluded`: Evidence suggests the property should not be included.

## Evidence Notes

Each evidence row ties a property to a source and claim. Evidence notes must state the public source basis for the claim and why the claim contributes to the confidence label.

Direct HUD `MN002000002 / SCATTERED SITES` evidence or an official MPHA portfolio property record can support `confirmed`. Owner, taxpayer, parcel, or contextual MPHA/CHR evidence supports `likely` unless another property-level source directly confirms portfolio status. Weak, incomplete, stale, or conflicting evidence supports `uncertain`.

## Change Events

Change events describe public portfolio changes such as additions, removals, owner/taxpayer changes, property classification changes, estimated unit-count changes, status changes, or confidence changes. Source-backed events must include a `source_id`; source-agnostic system comparisons can leave `source_id` blank.

## Permit And Fact Enrichment

`property_facts.csv` condenses parcel-level property facts from public parcel and assessing sources into one row per exported property. `property_permits.csv` publishes matched permit metadata, permit status, dates, value, unit changes, and work descriptions. Permit output excludes applicant names, applicant addresses, phone numbers, and emails.

## Privacy Boundary

The site must publish property-level public records only. It must not publish resident names, tenant records, household details, occupancy details tied to people, voucher records, applicant contact details, or other resident-level data.
