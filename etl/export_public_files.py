from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from models import (
    CHANGE_EVENT_FIELDS,
    PROPERTY_FACT_FIELDS,
    PROPERTY_FIELDS,
    PROPERTY_PERMIT_FIELDS,
    SCHEMA_VERSION,
    SOURCE_RECORD_FIELDS,
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_properties_csv(path: Path, properties: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROPERTY_FIELDS)
        writer.writeheader()
        for row in properties:
            writer.writerow({field: row.get(field, "") for field in PROPERTY_FIELDS})


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def build_geojson(properties: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    features = []
    for row in properties:
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        if latitude is None or longitude is None:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    field: value
                    for field, value in row.items()
                    if field not in {"latitude", "longitude"}
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
        },
        "features": features,
    }


def export_public_files(
    *,
    output_dir: Path,
    site_data_dir: Path,
    generated_at: str,
    properties: list[dict[str, Any]],
    property_versions: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    property_evidence: list[dict[str, Any]],
    change_events: list[dict[str, Any]],
    property_facts: list[dict[str, Any]],
    property_permits: list[dict[str, Any]],
    civic_boundaries: dict[str, Any] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    site_data_dir.mkdir(parents=True, exist_ok=True)

    properties_json = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "properties": properties,
    }
    history_json = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "property_versions": property_versions,
        "change_events": change_events,
    }
    sources_json = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_records": [
            {field: row.get(field, "") for field in SOURCE_RECORD_FIELDS}
            for row in source_records
        ],
        "property_evidence": property_evidence,
    }
    changelog_json = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "changes": [
            {field: row.get(field, "") for field in CHANGE_EVENT_FIELDS}
            for row in sorted(
                change_events,
                key=lambda item: str(item.get("event_date", "")),
                reverse=True,
            )
        ],
    }
    property_facts_json = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "property_facts": [
            {field: row.get(field, "") for field in PROPERTY_FACT_FIELDS}
            for row in property_facts
        ],
    }
    property_permits_json = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "property_permits": [
            {field: row.get(field, "") for field in PROPERTY_PERMIT_FIELDS}
            for row in sorted(
                property_permits,
                key=lambda item: (
                    str(item.get("property_id", "")),
                    str(item.get("issue_date", "")),
                    str(item.get("permit_number", "")),
                ),
                reverse=True,
            )
        ],
    }
    civic_boundaries_json = civic_boundaries or {
        "type": "FeatureCollection",
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
        },
        "features": [],
    }
    civic_boundaries_json["metadata"] = {
        **civic_boundaries_json.get("metadata", {}),
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
    }

    write_properties_csv(output_dir / "properties.csv", properties)
    write_json(output_dir / "properties.json", properties_json)
    write_json(output_dir / "properties.geojson", build_geojson(properties, generated_at))
    write_json(output_dir / "civic-boundaries.geojson", civic_boundaries_json)
    write_json(output_dir / "property-history.json", history_json)
    write_json(output_dir / "sources.json", sources_json)
    write_json(output_dir / "changelog.json", changelog_json)
    write_csv(output_dir / "property-facts.csv", PROPERTY_FACT_FIELDS, property_facts)
    write_json(output_dir / "property-facts.json", property_facts_json)
    write_csv(output_dir / "property-permits.csv", PROPERTY_PERMIT_FIELDS, property_permits)
    write_json(output_dir / "property-permits.json", property_permits_json)

    for filename in [
        "properties.csv",
        "properties.json",
        "properties.geojson",
        "civic-boundaries.geojson",
        "property-history.json",
        "sources.json",
        "changelog.json",
        "property-facts.csv",
        "property-facts.json",
        "property-permits.csv",
        "property-permits.json",
    ]:
        shutil.copyfile(output_dir / filename, site_data_dir / filename)
