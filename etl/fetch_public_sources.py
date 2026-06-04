from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import (
    CHANGE_EVENT_FIELDS,
    PROPERTY_FACT_FIELDS,
    PROPERTY_EVIDENCE_FIELDS,
    PROPERTY_PERMIT_FIELDS,
    PROPERTY_SOURCE_REQUIRED_FIELDS,
    SOURCE_RECORD_FIELDS,
)
from normalize import clean_text, normalize_address, normalize_parcel_id, slugify

HUD_BUILDINGS_LAYER_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/ArcGIS/rest/services/"
    "Public_Housing_Buildings/FeatureServer/0"
)
HUD_BUILDINGS_URL = f"{HUD_BUILDINGS_LAYER_URL}/query"
METROGIS_PARCELS_LAYER_URL = (
    "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_mngeo/"
    "plan_parcels_open/FeatureServer/1"
)
METROGIS_PARCELS_URL = f"{METROGIS_PARCELS_LAYER_URL}/query"
CCS_PERMITS_LAYER_URL = (
    "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/"
    "CCS_Permits/FeatureServer/0"
)
CCS_PERMITS_URL = f"{CCS_PERMITS_LAYER_URL}/query"
MPHA_PROPERTIES_URL = "https://mphaonline.org/properties/"

SOURCE_SNAPSHOT_DIR = "source-snapshots"
HENNEPIN_HARN_WKID = "ESRI:103734"
WGS84 = "EPSG:4326"


@dataclass(frozen=True)
class ArcGISSource:
    source_id: str
    source_name: str
    source_agency: str
    source_type: str
    layer_url: str
    query_url: str
    raw_filename: str
    where: str
    out_fields: str
    return_geometry: bool
    page_size: int
    record_date: str
    public_citation_text: str


@dataclass(frozen=True)
class AssessingRecord:
    source_id: str
    year: int
    parcel_id: str
    address: str
    city: str
    state: str
    zip_code: str
    owner_name: str
    taxpayer_name: str
    property_type: str
    building_use: str
    estimated_unit_count: int | None
    longitude: float | None
    latitude: float | None
    raw_x: float | None
    raw_y: float | None
    raw: dict[str, Any]


ASSESSING_SOURCES = [
    ArcGISSource(
        source_id="minneapolis_assessing_parcels_2023",
        source_name="Assessing Department Parcel Data 2023",
        source_agency="City of Minneapolis Assessing Department",
        source_type="ArcGIS FeatureServer Table",
        layer_url=(
            "https://services.arcgis.com/afSMGVsC7QlRK1kZ/ArcGIS/rest/services/"
            "Assessing_Department_Parcel_Data_2023/FeatureServer/0"
        ),
        query_url=(
            "https://services.arcgis.com/afSMGVsC7QlRK1kZ/ArcGIS/rest/services/"
            "Assessing_Department_Parcel_Data_2023/FeatureServer/0/query"
        ),
        raw_filename="minneapolis_assessing_parcel_data_2023.jsonl",
        where="1=1",
        out_fields="*",
        return_geometry=False,
        page_size=2000,
        record_date="2023-01-01",
        public_citation_text="City of Minneapolis Assessing Department Parcel Data 2023 annual public parcel table.",
    ),
    ArcGISSource(
        source_id="minneapolis_assessing_parcels_2024",
        source_name="Assessing Department Parcel Data 2024",
        source_agency="City of Minneapolis Assessing Department",
        source_type="ArcGIS FeatureServer Table",
        layer_url=(
            "https://services.arcgis.com/afSMGVsC7QlRK1kZ/ArcGIS/rest/services/"
            "Assessing_Department_Parcel_Data_2024/FeatureServer/0"
        ),
        query_url=(
            "https://services.arcgis.com/afSMGVsC7QlRK1kZ/ArcGIS/rest/services/"
            "Assessing_Department_Parcel_Data_2024/FeatureServer/0/query"
        ),
        raw_filename="minneapolis_assessing_parcel_data_2024.jsonl",
        where="1=1",
        out_fields="*",
        return_geometry=False,
        page_size=2000,
        record_date="2024-01-01",
        public_citation_text="City of Minneapolis Assessing Department Parcel Data 2024 annual public parcel table.",
    ),
    ArcGISSource(
        source_id="minneapolis_assessing_parcels_2025",
        source_name="Assessing Department Parcel Data 2025",
        source_agency="City of Minneapolis Assessing Department",
        source_type="ArcGIS FeatureServer Table",
        layer_url=(
            "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/"
            "Assessing_Department_Parcel_Data_2025/FeatureServer/0"
        ),
        query_url=(
            "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/"
            "Assessing_Department_Parcel_Data_2025/FeatureServer/0/query"
        ),
        raw_filename="minneapolis_assessing_parcel_data_2025.jsonl",
        where="1=1",
        out_fields="*",
        return_geometry=False,
        page_size=1000,
        record_date="2025-01-01",
        public_citation_text="City of Minneapolis Assessing Department Parcel Data 2025 annual public parcel table.",
    ),
]

RAW_SOURCES = [
    ArcGISSource(
        source_id="hud_public_housing_buildings_mn002",
        source_name="HUD Public Housing Buildings: MPHA MN002",
        source_agency="U.S. Department of Housing and Urban Development",
        source_type="ArcGIS FeatureServer",
        layer_url=HUD_BUILDINGS_LAYER_URL,
        query_url=HUD_BUILDINGS_URL,
        raw_filename="hud_public_housing_buildings_mn002.jsonl",
        where="PARTICIPANT_CODE='MN002'",
        out_fields="*",
        return_geometry=True,
        page_size=1000,
        record_date="",
        public_citation_text="HUD Public Housing Buildings FeatureServer records for MPHA participant MN002, including development MN002000002 / Scattered Sites.",
    ),
    ArcGISSource(
        source_id="metrogis_hennepin_minneapolis_parcels_current",
        source_name="MetroGIS Open Parcels: Hennepin County Minneapolis Slice",
        source_agency="Minnesota Geospatial Information Office / MetroGIS / Hennepin County",
        source_type="ArcGIS FeatureServer",
        layer_url=METROGIS_PARCELS_LAYER_URL,
        query_url=METROGIS_PARCELS_URL,
        raw_filename="metrogis_hennepin_minneapolis_parcels_current.jsonl",
        where="ctu_name='Minneapolis' AND co_name='Hennepin'",
        out_fields="*",
        return_geometry=True,
        page_size=4000,
        record_date="",
        public_citation_text="Minnesota Geospatial Commons opt-in open parcel compilation for Hennepin County parcels in Minneapolis.",
    ),
    ArcGISSource(
        source_id="minneapolis_ccs_permits_current",
        source_name="Construction and Code Services Permits",
        source_agency="City of Minneapolis Community Planning and Economic Development",
        source_type="ArcGIS FeatureServer",
        layer_url=CCS_PERMITS_LAYER_URL,
        query_url=CCS_PERMITS_URL,
        raw_filename="minneapolis_ccs_permits_current.jsonl",
        where="1=1",
        out_fields="*",
        return_geometry=False,
        page_size=2000,
        record_date="",
        public_citation_text="City of Minneapolis Construction and Code Services permit records matched to parcels by APN.",
    ),
    *ASSESSING_SOURCES,
]

DIRECT_SCATTERED_SITE_DEVELOPMENT = "MN002000002"
CCS_PERMITS_SOURCE_ID = "minneapolis_ccs_permits_current"
NAME_MATCH_RE = re.compile(
    r"\b(COMMUNITY\s+HOUSING\s+RESOURCES?|MPLS\s+PUBLIC\s+HOUSING|"
    r"MINNEAPOLIS\s+PUBLIC\s+HOUSING|PUBLIC\s+HOUSING\s+AUTH(?:ORITY)?|MPHA)\b"
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?i)\b(?:phone|ph|tel|telephone)\s*:?\s*"
    r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b"
    r"|\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"
)
EXCLUDED_PROPERTY_TYPE_RE = re.compile(r"\b(COMMERCIAL|INDUSTRIAL)\b")
EXCLUDED_BUILDING_USES = {
    "CENTER NEIGH/COMM.",
    "CHURCH",
    "DAY CARE CENTER",
    "OFFICE",
    "RESIDENTIAL CARE FACILITY",
    "TRANSIENT NAL HSG FAC",
    "WAREHOUSE",
}
CHANGE_EVENT_LABELS = {
    "owner_name_changed": "an owner name change",
    "taxpayer_name_changed": "a taxpayer name change",
    "property_type_changed": "a property classification change",
    "estimated_unit_count_changed": "an estimated unit count change",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def date_from_epoch_ms(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        return datetime.fromtimestamp(float(value) / 1000, UTC).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def request_json(url: str, params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{encoded}",
        headers={"User-Agent": "minneapolis-housing-etl/0.2"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("Request retry loop exited unexpectedly")


def feature_attributes(feature: dict[str, Any]) -> dict[str, Any]:
    attrs = feature.get("attributes", {})
    return {**attrs, **{key.upper(): value for key, value in attrs.items()}}


def first_value(row: dict[str, Any], *fields: str) -> str:
    for field in fields:
        value = clean_text(row.get(field))
        if value:
            return value
    return ""


def parse_int(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_pin(value: Any) -> str:
    parcel_id = normalize_parcel_id(value)
    if len(parcel_id) > 1 and parcel_id[0] == "P" and parcel_id[1].isdigit():
        return parcel_id[1:]
    return parcel_id


def normalized_name_blob(*values: Any) -> str:
    text = " ".join(clean_text(value).upper() for value in values if clean_text(value))
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def public_housing_name_matches(*values: Any) -> bool:
    return bool(NAME_MATCH_RE.search(normalized_name_blob(*values)))


def extract_arcgis_source(
    source: ArcGISSource,
    snapshot_dir: Path,
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    raw_path = snapshot_dir / source.raw_filename
    tmp_path = raw_path.with_suffix(raw_path.suffix + ".tmp")
    row_count = 0
    offset = 0
    with tmp_path.open("w", encoding="utf-8") as handle:
        while True:
            params = {
                "f": "json",
                "where": source.where,
                "outFields": source.out_fields,
                "returnGeometry": "true" if source.return_geometry else "false",
                "resultOffset": offset,
                "resultRecordCount": source.page_size,
                "outSR": 4326,
            }
            payload = request_json(source.query_url, params)
            if "error" in payload:
                raise RuntimeError(f"ArcGIS query failed for {source.source_id}: {payload['error']}")
            page = payload.get("features", [])
            if not page:
                break
            for feature in page:
                handle.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
            row_count += len(page)
            if not payload.get("exceededTransferLimit") and len(page) < source.page_size:
                break
            offset += len(page)
    tmp_path.replace(raw_path)
    return {
        "source_id": source.source_id,
        "raw_file_uri": f"data/raw/{SOURCE_SNAPSHOT_DIR}/{source.raw_filename}",
        "retrieved_at": retrieved_at,
        "where": source.where,
        "out_fields": source.out_fields,
        "return_geometry": source.return_geometry,
        "row_count": row_count,
        "sha256_hash": hash_file(raw_path),
    }


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def polygon_center(feature: dict[str, Any]) -> tuple[float | None, float | None]:
    rings = (feature.get("geometry") or {}).get("rings") or []
    coordinates = [
        point
        for ring in rings
        for point in ring
        if isinstance(point, list) and len(point) >= 2
    ]
    if not coordinates:
        return None, None
    xs = [float(point[0]) for point in coordinates if point[0] is not None]
    ys = [float(point[1]) for point in coordinates if point[1] is not None]
    if not xs or not ys:
        return None, None
    return sum(xs) / len(xs), sum(ys) / len(ys)


def point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = float(point[0]), float(point[1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        intersects = (yi > latitude) != (yj > latitude)
        if intersects:
            x_at_y = (xj - xi) * (latitude - yi) / (yj - yi) + xi
            if longitude < x_at_y:
                inside = not inside
        j = i
    return inside


def point_in_feature(longitude: float, latitude: float, feature: dict[str, Any]) -> bool:
    rings = (feature.get("geometry") or {}).get("rings") or []
    for ring in rings:
        if not ring:
            continue
        xs = [float(point[0]) for point in ring]
        ys = [float(point[1]) for point in ring]
        if not (min(xs) <= longitude <= max(xs) and min(ys) <= latitude <= max(ys)):
            continue
        if point_in_ring(longitude, latitude, ring):
            return True
    return False


def find_parcel_for_point(
    longitude: float | None,
    latitude: float | None,
    parcel_features: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    if longitude is None or latitude is None:
        return None
    for feature in parcel_features:
        if point_in_feature(longitude, latitude, feature):
            return feature
    return None


def parcel_address(parcel: dict[str, Any]) -> str:
    formatted = first_value(parcel, "ADDRESSFORMATTED", "FORMATTED_ADDRESS")
    if formatted:
        return normalize_address(formatted)
    parts = [
        parcel.get("ANUMBERPRE"),
        parcel.get("ANUMBER"),
        parcel.get("ANUMBERSUF"),
        parcel.get("ST_PRE_DIR"),
        parcel.get("ST_NAME"),
        parcel.get("ST_POS_TYP"),
        parcel.get("ST_POS_DIR"),
        parcel.get("HOUSE_NO"),
        parcel.get("STREET_NAME"),
    ]
    return normalize_address(" ".join(clean_text(part) for part in parts if clean_text(part)))


def state_parcel_record(feature: dict[str, Any]) -> dict[str, Any]:
    attrs = feature_attributes(feature)
    longitude, latitude = polygon_center(feature)
    return {
        "parcel_id": normalize_pin(attrs.get("COUNTY_PIN")),
        "address": parcel_address(attrs),
        "city": first_value(attrs, "CTU_NAME", "POSTCOMM") or "Minneapolis",
        "state": first_value(attrs, "STATE_CODE") or "MN",
        "zip": first_value(attrs, "ZIP"),
        "owner_name": first_value(attrs, "OWNER_NAME"),
        "taxpayer_name": first_value(attrs, "TAX_NAME"),
        "property_type": first_value(attrs, "DWELL_TYPE", "USECLASS1", "USECLASS2"),
        "estimated_unit_count": parse_int(attrs.get("NUM_UNITS")),
        "longitude": longitude,
        "latitude": latitude,
        "record_date": max(
            date_from_epoch_ms(attrs.get("EXP_DATE")),
            date_from_epoch_ms(attrs.get("EDIT_DATE")),
        ),
        "raw": attrs,
        "feature": feature,
    }


def get_transformer() -> Any:
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise RuntimeError(
            "pyproj is required to transform Minneapolis assessing X/Y coordinates "
            "from Hennepin County HARN feet to WGS84. Install ETL dependencies with "
            "pip install -r etl/requirements.txt."
        ) from exc
    return Transformer.from_crs(HENNEPIN_HARN_WKID, WGS84, always_xy=True)


def project_hennepin_xy(transformer: Any, x_value: Any, y_value: Any) -> tuple[float | None, float | None]:
    x = parse_float(x_value)
    y = parse_float(y_value)
    if x is None or y is None:
        return None, None
    longitude, latitude = transformer.transform(x, y)
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None, None
    return longitude, latitude


def assessing_record(
    feature: dict[str, Any],
    source: ArcGISSource,
    transformer: Any,
) -> AssessingRecord | None:
    attrs = feature_attributes(feature)
    parcel_id = normalize_pin(first_value(attrs, "TAX_MAP_UFMT", "PIN"))
    if not parcel_id:
        return None
    year = int(source.record_date[:4])
    taxpayer_names = [
        first_value(attrs, "TAXPAYER1"),
        first_value(attrs, "TAXPAYER2"),
        first_value(attrs, "TAXPAYER3"),
        first_value(attrs, "TAXPAYER4"),
    ]
    taxpayer_name = " | ".join(name for name in taxpayer_names if name)
    longitude, latitude = project_hennepin_xy(transformer, attrs.get("X"), attrs.get("Y"))
    return AssessingRecord(
        source_id=source.source_id,
        year=year,
        parcel_id=parcel_id,
        address=parcel_address(attrs),
        city="Minneapolis",
        state="MN",
        zip_code=first_value(attrs, "ZIP1", "ZIP_POSTAL"),
        owner_name=first_value(attrs, "OWNERNAME", "OWNERNM"),
        taxpayer_name=taxpayer_name,
        property_type=first_value(attrs, "PROPERTYTYPE", "PRIMARY_PROP_TYPE"),
        building_use=first_value(attrs, "BUILDINGUSE"),
        estimated_unit_count=parse_int(first_value(attrs, "TOTALUNITS", "TOTAL_UNITS")),
        longitude=longitude,
        latitude=latitude,
        raw_x=parse_float(attrs.get("X")),
        raw_y=parse_float(attrs.get("Y")),
        raw=attrs,
    )


def is_scattered_site_like(record: AssessingRecord) -> bool:
    property_type = record.property_type.upper()
    building_use = record.building_use.upper()
    units = record.estimated_unit_count
    if units is not None and units > 6:
        return False
    if EXCLUDED_PROPERTY_TYPE_RE.search(property_type) and "APARTMENT" not in property_type:
        return False
    if building_use in EXCLUDED_BUILDING_USES:
        return False
    if "RESIDENTIAL" in property_type or "APARTMENT" in property_type:
        return True
    if building_use in {"SINGLE FAMILY HOUSE", "DUPLEX", "TRIPLEX", "ROW HOUSE", "APARTMENT 4 OR 5 UNIT", "APARTMENT 6+ UNIT"}:
        return True
    return False


def choose_latest_assessing(records: list[AssessingRecord]) -> AssessingRecord | None:
    if not records:
        return None
    return sorted(records, key=lambda item: item.year, reverse=True)[0]


def clean_units(*values: int | None) -> int | str:
    for value in values:
        if value is not None and value > 0:
            return value
    return ""


def clean_coordinate(*values: float | None) -> float | str:
    for value in values:
        if value is not None:
            return value
    return ""


def first_clean_value(row: dict[str, Any], *fields: str) -> str:
    return first_value(row, *fields)


def first_int(row: dict[str, Any], *fields: str) -> int | str:
    for field in fields:
        value = parse_int(row.get(field))
        if value is not None:
            return value
    return ""


def first_float(row: dict[str, Any], *fields: str) -> float | str:
    for field in fields:
        value = parse_float(row.get(field))
        if value is not None:
            return value
    return ""


def first_date(row: dict[str, Any], *fields: str) -> str:
    for field in fields:
        value = row.get(field)
        epoch_date = date_from_epoch_ms(value)
        if epoch_date:
            return epoch_date
        text = clean_text(value)
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            return text[:10]
    return ""


def join_unique(*values: Any) -> str:
    seen: set[str] = set()
    output = []
    for value in values:
        text = clean_text(value)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return " | ".join(output)


def use_classes(attrs: dict[str, Any]) -> str:
    return join_unique(
        attrs.get("USECLASS1"),
        attrs.get("USECLASS2"),
        attrs.get("USECLASS3"),
        attrs.get("USECLASS4"),
        attrs.get("XUSECLASS1"),
        attrs.get("XUSECLASS2"),
        attrs.get("XUSECLASS3"),
        attrs.get("XUSECLASS4"),
    )


def sanitize_permit_description(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = EMAIL_RE.sub("[contact omitted]", text)
    text = PHONE_RE.sub("[contact omitted]", text)
    return clean_text(text)


def build_property_fact(
    property_id: str,
    parcel_id: str,
    state_record: dict[str, Any] | None,
    latest_assessing: AssessingRecord | None,
) -> dict[str, Any]:
    state_attrs = (state_record or {}).get("raw", {}) if state_record else {}
    assessing_attrs = latest_assessing.raw if latest_assessing else {}
    source_ids = []
    if state_record:
        source_ids.append("metrogis_hennepin_minneapolis_parcels_current")
    if latest_assessing:
        source_ids.append(latest_assessing.source_id)

    return {
        "property_id": property_id,
        "parcel_id": parcel_id,
        "source_ids": "|".join(source_ids),
        "sale_date": first_date(state_attrs, "SALE_DATE"),
        "sale_value": first_float(state_attrs, "SALE_VALUE"),
        "assessed_land_value": first_float(state_attrs, "EMV_LAND", "LANDVALUE", "LAND_VALUE")
        or first_float(assessing_attrs, "LANDVALUE", "LAND_VALUE"),
        "assessed_building_value": first_float(state_attrs, "EMV_BLDG", "BUILDINGVALUE", "BUILDING_VALUE")
        or first_float(assessing_attrs, "BUILDINGVALUE", "BUILDING_VALUE"),
        "assessed_total_value": first_float(state_attrs, "EMV_TOTAL", "TOTALVALUE", "TOTAL_VALUE")
        or first_float(assessing_attrs, "TOTALVALUE", "TOTAL_VALUE"),
        "tax_year": first_int(state_attrs, "TAX_YEAR") or first_int(assessing_attrs, "TAXYR", "TAX_YEAR"),
        "market_year": first_int(state_attrs, "MKT_YEAR") or first_int(assessing_attrs, "ASMTYEAR"),
        "total_tax": first_float(state_attrs, "TOTAL_TAX"),
        "use_classes": use_classes(state_attrs) or first_clean_value(assessing_attrs, "MULTIPLEUSES", "LANDUSE"),
        "zoning": first_clean_value(assessing_attrs, "ZONING"),
        "land_use": first_clean_value(assessing_attrs, "LANDUSE"),
        "parcel_area_sqft": first_float(assessing_attrs, "PARCELAREA", "PARCEL_AREA"),
        "acres": first_float(state_attrs, "ACRES_POLY", "ACRES_DEED"),
        "year_built": first_int(assessing_attrs, "YEARBUILT", "YEAR_BUILT") or first_int(state_attrs, "YEAR_BUILT"),
        "finished_sqft": first_float(state_attrs, "FIN_SQ_FT"),
        "above_ground_area": first_float(assessing_attrs, "ABOVEGROUNDAREA", "ABOVE_GROUND_AREA"),
        "below_ground_area": first_float(assessing_attrs, "BASEMENTAREA", "BELOW_GROUND_AREA"),
        "total_units": first_int(assessing_attrs, "TOTALUNITS", "TOTAL_UNITS") or first_int(state_attrs, "NUM_UNITS"),
        "building_use": first_clean_value(assessing_attrs, "BUILDINGUSE"),
    }


def build_property_permit(
    feature: dict[str, Any],
    property_id_by_parcel_id: dict[str, str],
) -> dict[str, Any] | None:
    attrs = feature_attributes(feature)
    parcel_id = normalize_pin(first_value(attrs, "APN", "PIN", "PARCEL_ID"))
    if not parcel_id:
        return None
    property_id = property_id_by_parcel_id.get(parcel_id)
    if not property_id:
        return None

    permit_number = first_value(attrs, "permitNumber", "PERMITNUMBER")
    work_description = sanitize_permit_description(first_value(attrs, "comments", "COMMENTS"))
    return {
        "property_id": property_id,
        "parcel_id": parcel_id,
        "permit_number": permit_number,
        "permit_type": first_value(attrs, "permitType", "PERMITTYPE"),
        "work_type": first_value(attrs, "workType", "WORKTYPE"),
        "occupancy_type": first_value(attrs, "occupancyType", "OCCUPANCYTYPE"),
        "status": first_value(attrs, "status", "STATUS"),
        "milestone": first_value(attrs, "milestone", "MILESTONE"),
        "value": first_float(attrs, "value", "VALUE"),
        "dwelling_units_new": first_int(attrs, "dwellingUnitsNew", "DWELLINGUNITSNEW"),
        "dwelling_units_eliminated": first_int(
            attrs,
            "dwellingUnitsEliminated",
            "DWELLINGUNITSELIMINATED",
        ),
        "issue_date": first_date(attrs, "issueDate", "ISSUEDATE"),
        "complete_date": first_date(attrs, "completeDate", "COMPLETEDATE"),
        "work_description": work_description,
        "match_method": "parcel_apn",
        "source_id": CCS_PERMITS_SOURCE_ID,
    }


def source_date_for_property(
    assessing_records: list[AssessingRecord],
    state_record: dict[str, Any] | None,
    hud_rows: list[dict[str, Any]],
    fallback: str,
) -> tuple[str, str]:
    dates = [f"{record.year}-01-01" for record in assessing_records]
    if state_record and state_record.get("record_date"):
        dates.append(str(state_record["record_date"]))
    dates.extend(date_from_epoch_ms(row.get("LAST_UPDT_DTTM")) for row in hud_rows)
    dates = sorted(date for date in dates if date)
    if not dates:
        return fallback, fallback
    return dates[0], dates[-1]


def mpha_source_note(
    has_hud: bool,
    has_state: bool,
    assessing_years: list[int],
    is_current: bool,
) -> str:
    notes = []
    if has_hud:
        notes.append("HUD directly lists this parcel/address in development MN002000002 / Scattered Sites.")
    if has_state:
        notes.append("MetroGIS/Hennepin parcel data contains a public housing owner or taxpayer-name match.")
    if assessing_years:
        years = ", ".join(str(year) for year in sorted(assessing_years))
        notes.append(f"Minneapolis assessing records show public housing owner or taxpayer evidence for {years}.")
    if not is_current:
        notes.append("The latest source evidence is historical rather than current.")
    return " ".join(notes)


def build_sources(
    project_root: Path,
    retrieved_at: str,
    extracts: dict[str, dict[str, Any]],
    source_dates: dict[str, str],
) -> list[dict[str, Any]]:
    source_specs = []
    for source in RAW_SOURCES:
        extract = extracts.get(source.source_id, {})
        source_specs.append(
            {
                "source_id": source.source_id,
                "source_name": source.source_name,
                "source_agency": source.source_agency,
                "source_type": source.source_type,
                "source_url": source.layer_url,
                "retrieved_at": extract.get("retrieved_at", retrieved_at),
                "record_date": source_dates.get(source.source_id, source.record_date),
                "raw_file_uri": extract.get(
                    "raw_file_uri",
                    f"data/raw/{SOURCE_SNAPSHOT_DIR}/{source.raw_filename}",
                ),
                "sha256_hash": extract.get("sha256_hash", ""),
                "public_citation_text": source.public_citation_text,
            }
        )
    source_specs.append(
        {
            "source_id": "mpha_properties_overview",
            "source_name": "MPHA Properties Overview",
            "source_agency": "Minneapolis Public Housing Authority",
            "source_type": "Website",
            "source_url": MPHA_PROPERTIES_URL,
            "retrieved_at": retrieved_at,
            "record_date": "",
            "raw_file_uri": "",
            "sha256_hash": "",
            "public_citation_text": "MPHA public properties page describing scattered-site homes as CHR single-family and multiplex homes, nearly 800 units.",
        }
    )
    for spec in source_specs:
        raw_file_uri = clean_text(spec["raw_file_uri"])
        raw_path = project_root / raw_file_uri if raw_file_uri else None
        if not spec["sha256_hash"] and raw_path and raw_path.exists():
            spec["sha256_hash"] = hash_file(raw_path)
    return source_specs


def evidence_row(
    evidence_id: str,
    property_id: str,
    source_id: str,
    claim_type: str,
    claim_value: str,
    confidence_contribution: float,
    evidence_note: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "property_id": property_id,
        "source_id": source_id,
        "claim_type": claim_type,
        "claim_value": claim_value,
        "confidence_contribution": confidence_contribution,
        "evidence_note": evidence_note,
    }


def transform_sources(
    project_root: Path,
    retrieved_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    snapshot_dir = project_root / "data" / "raw" / SOURCE_SNAPSHOT_DIR
    hud_path = snapshot_dir / "hud_public_housing_buildings_mn002.jsonl"
    metrogis_path = snapshot_dir / "metrogis_hennepin_minneapolis_parcels_current.jsonl"

    hud_features = list(read_jsonl(hud_path))
    hud_attrs = [feature_attributes(feature) for feature in hud_features]
    hud_scattered_features = [
        feature
        for feature in hud_features
        if clean_text(feature_attributes(feature).get("DEVELOPMENT_CODE")) == DIRECT_SCATTERED_SITE_DEVELOPMENT
    ]

    state_features = list(read_jsonl(metrogis_path))
    state_records_by_parcel: dict[str, dict[str, Any]] = {}
    state_candidate_ids: set[str] = set()
    state_record_dates: list[str] = []
    for feature in state_features:
        record = state_parcel_record(feature)
        parcel_id = record["parcel_id"]
        if not parcel_id:
            continue
        state_records_by_parcel[parcel_id] = record
        if record["record_date"]:
            state_record_dates.append(record["record_date"])
        if public_housing_name_matches(record["owner_name"], record["taxpayer_name"]):
            state_candidate_ids.add(parcel_id)

    transformer = get_transformer()
    assessing_by_parcel: dict[str, list[AssessingRecord]] = defaultdict(list)
    assessing_candidates_by_year: dict[int, set[str]] = defaultdict(set)
    for source in ASSESSING_SOURCES:
        path = snapshot_dir / source.raw_filename
        seen_source_parcels: set[str] = set()
        for feature in read_jsonl(path):
            record = assessing_record(feature, source, transformer)
            if record is None:
                continue
            if record.parcel_id in seen_source_parcels:
                continue
            seen_source_parcels.add(record.parcel_id)
            assessing_by_parcel[record.parcel_id].append(record)
            if public_housing_name_matches(record.owner_name, record.taxpayer_name) and is_scattered_site_like(record):
                assessing_candidates_by_year[record.year].add(record.parcel_id)

    hud_groups_by_parcel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hud_unmatched: list[dict[str, Any]] = []
    for feature in hud_scattered_features:
        attrs = feature_attributes(feature)
        longitude = parse_float(attrs.get("LON") or (feature.get("geometry") or {}).get("x"))
        latitude = parse_float(attrs.get("LAT") or (feature.get("geometry") or {}).get("y"))
        parcel_feature = find_parcel_for_point(longitude, latitude, state_features)
        if parcel_feature:
            parcel_id = normalize_pin(feature_attributes(parcel_feature).get("COUNTY_PIN"))
            hud_groups_by_parcel[parcel_id].append(attrs)
        else:
            hud_unmatched.append(attrs)

    current_candidate_ids = (
        set(hud_groups_by_parcel)
        | state_candidate_ids
        | assessing_candidates_by_year.get(2025, set())
    )
    historical_candidate_ids = set().union(*assessing_candidates_by_year.values()) if assessing_candidates_by_year else set()
    all_candidate_ids = current_candidate_ids | historical_candidate_ids

    property_rows: dict[str, dict[str, Any]] = {}
    property_facts: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    change_rows: list[dict[str, Any]] = []
    today = datetime.now(UTC).date().isoformat()

    for parcel_id in sorted(all_candidate_ids):
        state_record = state_records_by_parcel.get(parcel_id)
        assessing_records = sorted(assessing_by_parcel.get(parcel_id, []), key=lambda item: item.year)
        latest_assessing = choose_latest_assessing(assessing_records)
        hud_rows = hud_groups_by_parcel.get(parcel_id, [])
        latest_candidate_year = max(
            [record.year for record in assessing_records if record.parcel_id in assessing_candidates_by_year.get(record.year, set())],
            default=None,
        )
        is_current = parcel_id in current_candidate_ids
        property_id = f"parcel-{parcel_id}"
        hud_unit_count = sum(
            parse_int(row.get("TOTAL_DWELLING_UNITS")) or 0
            for row in hud_rows
            if row.get("TOTAL_DWELLING_UNITS") not in {None, ""}
        )
        first_seen, last_seen = source_date_for_property(assessing_records, state_record, hud_rows, today)
        address = (
            (latest_assessing.address if latest_assessing else "")
            or (state_record or {}).get("address", "")
            or normalize_address(hud_rows[0].get("STD_ADDR") if hud_rows else "")
        )
        owner_name = (latest_assessing.owner_name if latest_assessing else "") or (state_record or {}).get("owner_name", "")
        taxpayer_name = (state_record or {}).get("taxpayer_name", "") or (latest_assessing.taxpayer_name if latest_assessing else "")
        property_type = (
            (latest_assessing.property_type if latest_assessing else "")
            or (state_record or {}).get("property_type", "")
            or clean_text(hud_rows[0].get("BUILDING_TYPE_CODE") if hud_rows else "")
            or "Scattered-site housing"
        )
        status_parts = []
        hud_statuses = sorted(
            {
                clean_text(row.get("BUILDING_STATUS_TYPE_CODE"))
                for row in hud_rows
                if clean_text(row.get("BUILDING_STATUS_TYPE_CODE"))
            }
        )
        if hud_statuses:
            status_parts.append(f"HUD building status {', '.join(hud_statuses)}")
        if is_current and parcel_id in assessing_candidates_by_year.get(2025, set()):
            status_parts.append("Current public housing ownership match in Minneapolis assessing records")
        if is_current and parcel_id in state_candidate_ids:
            status_parts.append("Current public housing owner or taxpayer match in parcel records")
        if not is_current and latest_candidate_year:
            status_parts.append(f"Historical public housing owner or taxpayer match last observed in {latest_candidate_year}")
        if not status_parts:
            status_parts.append("Current public record")

        record = {
            "property_id": property_id,
            "canonical_address": address,
            "city": (latest_assessing.city if latest_assessing else "") or (state_record or {}).get("city", "") or "Minneapolis",
            "state": (latest_assessing.state if latest_assessing else "") or (state_record or {}).get("state", "") or "MN",
            "zip": (latest_assessing.zip_code if latest_assessing else "") or (state_record or {}).get("zip", ""),
            "parcel_id": parcel_id,
            "latitude": clean_coordinate(
                latest_assessing.latitude if latest_assessing else None,
                (state_record or {}).get("latitude"),
            ),
            "longitude": clean_coordinate(
                latest_assessing.longitude if latest_assessing else None,
                (state_record or {}).get("longitude"),
            ),
            "current_owner_name": owner_name,
            "current_taxpayer_name": taxpayer_name,
            "property_type": property_type,
            "estimated_unit_count": clean_units(
                hud_unit_count if hud_unit_count else None,
                latest_assessing.estimated_unit_count if latest_assessing else None,
                (state_record or {}).get("estimated_unit_count"),
            ),
            "current_status": "; ".join(status_parts),
            "public_notes": mpha_source_note(
                bool(hud_rows),
                parcel_id in state_candidate_ids,
                [record.year for record in assessing_records if record.parcel_id in assessing_candidates_by_year.get(record.year, set())],
                is_current,
            ),
            "first_seen_date": first_seen,
            "last_seen_date": last_seen,
            "is_current": "true" if is_current else "false",
            "detail_url_slug": slugify(address, parcel_id),
        }
        property_rows[property_id] = record
        property_facts.append(
            build_property_fact(
                property_id,
                parcel_id,
                state_record,
                latest_assessing,
            )
        )

        if hud_rows:
            evidence_rows.append(
                evidence_row(
                    f"ev-hud-{property_id}",
                    property_id,
                    "hud_public_housing_buildings_mn002",
                    "official_scattered_site_listing",
                    "DEVELOPMENT_CODE MN002000002 / PROJECT_NAME SCATTERED SITES",
                    0.8,
                    "HUD Public Housing Buildings directly lists this address/building as part of MPHA development MN002000002 / Scattered Sites.",
                )
            )
        if parcel_id in state_candidate_ids:
            state_value = normalized_name_blob(
                (state_record or {}).get("owner_name", ""),
                (state_record or {}).get("taxpayer_name", ""),
            )
            evidence_rows.append(
                evidence_row(
                    f"ev-metrogis-owner-taxpayer-{property_id}",
                    property_id,
                    "metrogis_hennepin_minneapolis_parcels_current",
                    "owner_taxpayer_match",
                    state_value,
                    0.65,
                    "MetroGIS/Hennepin parcel owner or taxpayer name matches MPHA, Minneapolis Public Housing Authority, or Community Housing Resources.",
                )
            )
        for assessing in assessing_records:
            if assessing.parcel_id not in assessing_candidates_by_year.get(assessing.year, set()):
                continue
            evidence_rows.append(
                evidence_row(
                    f"ev-minneapolis-assessing-{assessing.year}-{property_id}",
                    property_id,
                    assessing.source_id,
                    "owner_taxpayer_match",
                    normalized_name_blob(assessing.owner_name, assessing.taxpayer_name),
                    0.55 if assessing.year == 2025 else 0.2,
                    f"Minneapolis assessing {assessing.year} records show a public housing owner or taxpayer name match and a small residential property classification.",
                )
            )
        evidence_rows.append(
            evidence_row(
                f"ev-mpha-overview-{property_id}",
                property_id,
                "mpha_properties_overview",
                "portfolio_context",
                "CHR single-family and multiplex homes",
                0.05,
                "MPHA's public properties page describes scattered-site homes as CHR single-family and multiplex homes, nearly 800 units.",
            )
        )

        previous: AssessingRecord | None = None
        for assessing in assessing_records:
            if previous is not None:
                comparisons = [
                    ("owner_name_changed", previous.owner_name, assessing.owner_name),
                    ("taxpayer_name_changed", previous.taxpayer_name, assessing.taxpayer_name),
                    ("property_type_changed", previous.property_type, assessing.property_type),
                    (
                        "estimated_unit_count_changed",
                        "" if previous.estimated_unit_count is None else str(previous.estimated_unit_count),
                        "" if assessing.estimated_unit_count is None else str(assessing.estimated_unit_count),
                    ),
                ]
                for event_type, old_value, new_value in comparisons:
                    if clean_text(old_value) != clean_text(new_value):
                        change_rows.append(
                            {
                                "event_id": f"chg-{event_type}-{assessing.year}-{property_id}",
                                "property_id": property_id,
                                "event_date": f"{assessing.year}-01-01",
                                "event_type": event_type,
                                "old_value": old_value,
                                "new_value": new_value,
                                "source_id": assessing.source_id,
                                "public_note": f"Minneapolis assessing records show {CHANGE_EVENT_LABELS.get(event_type, event_type.replace('_', ' '))} between {previous.year} and {assessing.year}.",
                            }
                        )
            previous = assessing

    for attrs in hud_unmatched:
        key = clean_text(attrs.get("NATIONAL_BLDG_ID") or attrs.get("OBJECTID"))
        property_id = f"hud-mn002000002-{key}"
        longitude = parse_float(attrs.get("LON"))
        latitude = parse_float(attrs.get("LAT"))
        record_date = date_from_epoch_ms(attrs.get("LAST_UPDT_DTTM")) or today
        address = normalize_address(attrs.get("STD_ADDR"))
        property_rows[property_id] = {
            "property_id": property_id,
            "canonical_address": address,
            "city": clean_text(attrs.get("STD_CITY")) or "Minneapolis",
            "state": clean_text(attrs.get("STD_ST")) or "MN",
            "zip": clean_text(attrs.get("STD_ZIP5")),
            "parcel_id": "",
            "latitude": latitude if latitude is not None else "",
            "longitude": longitude if longitude is not None else "",
            "current_owner_name": "",
            "current_taxpayer_name": "",
            "property_type": clean_text(attrs.get("BUILDING_TYPE_CODE")) or "Scattered-site housing",
            "estimated_unit_count": parse_int(attrs.get("TOTAL_DWELLING_UNITS")) or "",
            "current_status": f"HUD building status {clean_text(attrs.get('BUILDING_STATUS_TYPE_CODE'))}",
            "public_notes": "HUD directly lists this address/building in development MN002000002 / Scattered Sites. No matching MetroGIS/Hennepin parcel ID was found for the mapped point.",
            "first_seen_date": record_date,
            "last_seen_date": record_date,
            "is_current": "true",
            "detail_url_slug": slugify(address, property_id),
        }
        evidence_rows.append(
            evidence_row(
                f"ev-hud-{property_id}",
                property_id,
                "hud_public_housing_buildings_mn002",
                "official_scattered_site_listing",
                "DEVELOPMENT_CODE MN002000002 / PROJECT_NAME SCATTERED SITES",
                0.8,
                "HUD Public Housing Buildings directly lists this address/building as part of MPHA development MN002000002 / Scattered Sites.",
            )
        )

    properties = sorted(
        property_rows.values(),
        key=lambda row: (clean_text(row.get("canonical_address")).lower(), clean_text(row.get("parcel_id"))),
    )
    property_id_by_parcel_id = {
        clean_text(row.get("parcel_id")): clean_text(row.get("property_id"))
        for row in properties
        if clean_text(row.get("parcel_id"))
    }
    permit_path = snapshot_dir / "minneapolis_ccs_permits_current.jsonl"
    permit_features = list(read_jsonl(permit_path)) if permit_path.exists() else []
    property_permits = [
        permit
        for permit in (
            build_property_permit(feature, property_id_by_parcel_id)
            for feature in permit_features
        )
        if permit is not None
    ]
    property_permits = sorted(
        property_permits,
        key=lambda row: (
            clean_text(row.get("property_id")),
            clean_text(row.get("issue_date")),
            clean_text(row.get("permit_number")),
        ),
        reverse=True,
    )
    source_dates = {
        "hud_public_housing_buildings_mn002": max(
            [date_from_epoch_ms(row.get("LAST_UPDT_DTTM")) for row in hud_attrs if date_from_epoch_ms(row.get("LAST_UPDT_DTTM"))],
            default="",
        ),
        "metrogis_hennepin_minneapolis_parcels_current": max(state_record_dates, default=""),
        CCS_PERMITS_SOURCE_ID: max(
            [
                clean_text(permit.get("issue_date") or permit.get("complete_date"))
                for permit in property_permits
                if clean_text(permit.get("issue_date") or permit.get("complete_date"))
            ],
            default="",
        ),
    }
    source_dates.update({source.source_id: source.record_date for source in ASSESSING_SOURCES})

    summary = {
        "retrieved_at": retrieved_at,
        "hud_mn002_building_records": len(hud_features),
        "hud_scattered_site_building_records": len(hud_scattered_features),
        "hud_scattered_site_unmatched_to_parcel": len(hud_unmatched),
        "metrogis_minneapolis_parcel_records": len(state_features),
        "metrogis_public_housing_name_candidates": len(state_candidate_ids),
        "minneapolis_ccs_permit_records": len(permit_features),
        "minneapolis_ccs_permits_matched_to_properties": len(property_permits),
        "minneapolis_assessing_candidates_by_year": {
            str(year): len(parcel_ids)
            for year, parcel_ids in sorted(assessing_candidates_by_year.items())
        },
        "exported_properties": len(properties),
        "exported_property_facts": len(property_facts),
        "exported_property_permits": len(property_permits),
        "exported_evidence_rows": len(evidence_rows),
        "exported_change_events": len(change_rows),
    }
    return properties, evidence_rows, change_rows, {
        "summary": summary,
        "source_dates": source_dates,
        "property_facts": property_facts,
        "property_permits": property_permits,
    }


def extract_sources(project_root: Path, retrieved_at: str) -> dict[str, dict[str, Any]]:
    snapshot_dir = project_root / "data" / "raw" / SOURCE_SNAPSHOT_DIR
    extracts = {}
    for source in RAW_SOURCES:
        print(f"Extracting {source.source_id}...")
        extracts[source.source_id] = extract_arcgis_source(source, snapshot_dir, retrieved_at=retrieved_at)
    write_json(project_root / "data" / "raw" / "source-manifest.json", {"retrieved_at": retrieved_at, "sources": extracts})
    return extracts


def read_source_manifest(project_root: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    manifest_path = project_root / "data" / "raw" / "source-manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(
            "No source manifest found. Run python etl/fetch_public_sources.py before using --transform-only."
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return clean_text(payload.get("retrieved_at")) or utc_now(), payload.get("sources", {})


def write_transformed_inputs(
    project_root: Path,
    *,
    retrieved_at: str,
    extracts: dict[str, dict[str, Any]],
) -> int:
    raw_dir = project_root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    properties, evidence_rows, change_rows, transform_result = transform_sources(project_root, retrieved_at)
    source_dates = transform_result["source_dates"]
    sources = build_sources(project_root, retrieved_at, extracts, source_dates)

    write_csv(raw_dir / "properties_source.csv", PROPERTY_SOURCE_REQUIRED_FIELDS, properties)
    write_csv(raw_dir / "source_records.csv", SOURCE_RECORD_FIELDS, sources)
    write_csv(raw_dir / "property_evidence.csv", PROPERTY_EVIDENCE_FIELDS, evidence_rows)
    write_csv(raw_dir / "change_events.csv", CHANGE_EVENT_FIELDS, change_rows)
    write_csv(
        raw_dir / "property_facts.csv",
        PROPERTY_FACT_FIELDS,
        transform_result["property_facts"],
    )
    write_csv(
        raw_dir / "property_permits.csv",
        PROPERTY_PERMIT_FIELDS,
        transform_result["property_permits"],
    )

    summary = {
        **transform_result["summary"],
        "source_extracts": {
            source_id: {
                "row_count": extract["row_count"],
                "raw_file_uri": extract["raw_file_uri"],
                "sha256_hash": extract["sha256_hash"],
            }
            for source_id, extract in extracts.items()
        },
    }
    write_json(raw_dir / "fetch-summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


def fetch_sources(project_root: Path) -> int:
    retrieved_at = utc_now()
    extracts = extract_sources(project_root, retrieved_at)
    return write_transformed_inputs(project_root, retrieved_at=retrieved_at, extracts=extracts)


def transform_existing_sources(project_root: Path) -> int:
    retrieved_at, extracts = read_source_manifest(project_root)
    return write_transformed_inputs(project_root, retrieved_at=retrieved_at, extracts=extracts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract public source snapshots, then transform them into ETL inputs.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of etl/.",
    )
    parser.add_argument(
        "--transform-only",
        action="store_true",
        help="Reuse existing landed source snapshots and regenerate transformed CSV inputs.",
    )
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    if args.transform_only:
        return transform_existing_sources(project_root)
    return fetch_sources(project_root)


if __name__ == "__main__":
    raise SystemExit(main())
