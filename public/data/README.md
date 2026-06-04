# Public Data

This directory contains downloadable data files for the Minneapolis Scattered-Site Housing Explorer.

Generated files copied here by `python etl/run_pipeline.py`:

- `properties.csv`: current property rows with confidence fields; the current generated file contains 738 rows.
- `properties.json`: current property rows in a JSON envelope.
- `properties.geojson`: current property rows as map points.
- `property-facts.csv`: parcel/property fact rows; the current generated file contains 735 rows.
- `property-facts.json`: property fact rows in a JSON envelope.
- `property-permits.csv`: matched permit rows; the current generated file contains 1,585 rows.
- `property-permits.json`: matched permit rows in a JSON envelope.
- `property-history.json`: property versions and change events.
- `sources.json`: source records and property evidence rows.
- `changelog.json`: change events sorted newest first.

Static file maintained here outside the ETL:

- `map-style.json`: blank MapLibre style used when `PUBLIC_BASEMAP_STYLE_URL` is not set.

Permit outputs omit applicant names, applicant addresses, phone numbers, emails, and resident-level information. This directory must not contain resident names, tenant records, household details, occupancy details tied to people, voucher records, or applicant contact details.
