from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from confidence import compute_confidence
from export_public_files import export_public_files
from models import (
    CHANGE_EVENT_FIELDS,
    CHANGE_REQUIRED_VALUES,
    EVIDENCE_REQUIRED_VALUES,
    PROPERTY_FACT_FIELDS,
    PROPERTY_EVIDENCE_FIELDS,
    PROPERTY_PERMIT_FIELDS,
    PROPERTY_REQUIRED_VALUES,
    PROPERTY_SOURCE_REQUIRED_FIELDS,
    PROPERTY_VERSION_FIELDS,
    PipelineInputError,
    PipelineRun,
    PipelineWarning,
    SOURCE_RECORD_FIELDS,
    SOURCE_REQUIRED_VALUES,
)
from normalize import (
    clean_text,
    normalize_address,
    normalize_parcel_id,
    parse_bool,
    parse_float_or_none,
    parse_int_or_none,
    slugify,
    stable_hash,
)

REQUIRED_INPUT_FILES = {
    "properties_source": "data/raw/properties_source.csv",
    "source_records": "data/raw/source_records.csv",
    "property_evidence": "data/raw/property_evidence.csv",
}
OPTIONAL_INPUT_FILES = {
    "change_events": "data/raw/change_events.csv",
    "property_facts": "data/raw/property_facts.csv",
    "property_permits": "data/raw/property_permits.csv",
    "civic_boundaries": "data/raw/civic-boundaries.geojson",
}

PROPERTY_FACT_FLOAT_FIELDS = {
    "sale_value",
    "assessed_land_value",
    "assessed_building_value",
    "assessed_total_value",
    "total_tax",
    "parcel_area_sqft",
    "acres",
    "finished_sqft",
    "above_ground_area",
    "below_ground_area",
    "assessed_value_per_unit",
}
PROPERTY_FACT_INT_FIELDS = {
    "tax_year",
    "market_year",
    "year_built",
    "total_units",
    "inferred_unit_count",
    "best_unit_count",
}
PROPERTY_PERMIT_FLOAT_FIELDS = {"value"}
PROPERTY_PERMIT_INT_FIELDS = {"dwelling_units_new", "dwelling_units_eliminated"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_git_commit(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def read_csv(path: Path, required_fields: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise PipelineInputError(f"Required input file is missing: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [field for field in required_fields if field not in fieldnames]
        if missing:
            raise PipelineInputError(
                f"{path} is missing required columns: {', '.join(missing)}"
            )
        return [{key: clean_text(value) for key, value in row.items()} for row in reader]


def read_optional_csv(path: Path, required_fields: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv(path, required_fields)


def read_optional_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineInputError(f"Invalid JSON file: {path}") from exc


def validate_required_values(
    rows: list[dict[str, str]],
    fields: list[str],
    path_label: str,
) -> None:
    failures: list[str] = []
    for index, row in enumerate(rows, start=2):
        for field in fields:
            if clean_text(row.get(field)) == "":
                failures.append(f"{path_label}: row {index} missing {field}")
    if failures:
        preview = "\n".join(failures[:20])
        extra = "" if len(failures) <= 20 else f"\n...and {len(failures) - 20} more"
        raise PipelineInputError(f"Required values are missing:\n{preview}{extra}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_raw_file(project_root: Path, raw_file_uri: str) -> Path | None:
    if not raw_file_uri or raw_file_uri.startswith(("http://", "https://")):
        return None
    candidate = Path(raw_file_uri)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate


def normalize_source_records(
    project_root: Path,
    rows: list[dict[str, str]],
    warnings: list[PipelineWarning],
) -> list[dict[str, Any]]:
    normalized = []
    seen: set[str] = set()
    for row in rows:
        source_id = clean_text(row.get("source_id"))
        if source_id in seen:
            raise PipelineInputError(f"Duplicate source_id: {source_id}")
        seen.add(source_id)

        output = {field: clean_text(row.get(field)) for field in SOURCE_RECORD_FIELDS}
        raw_path = resolve_raw_file(project_root, output["raw_file_uri"])
        if output["sha256_hash"] == "" and raw_path and raw_path.exists():
            output["sha256_hash"] = sha256_file(raw_path)
        elif output["sha256_hash"] == "" and output["raw_file_uri"]:
            warnings.append(
                PipelineWarning(
                    "missing_hash",
                    f"No sha256_hash supplied and raw file was not found for source {source_id}",
                )
            )
        normalized.append(output)
    return normalized


def normalize_evidence(
    rows: list[dict[str, str]],
    property_ids: set[str],
    source_ids: set[str],
) -> list[dict[str, Any]]:
    normalized = []
    seen: set[str] = set()
    for row in rows:
        evidence_id = clean_text(row.get("evidence_id"))
        property_id = clean_text(row.get("property_id"))
        source_id = clean_text(row.get("source_id"))
        if evidence_id in seen:
            raise PipelineInputError(f"Duplicate evidence_id: {evidence_id}")
        if property_id not in property_ids:
            raise PipelineInputError(
                f"Evidence {evidence_id} references unknown property_id: {property_id}"
            )
        if source_id not in source_ids:
            raise PipelineInputError(
                f"Evidence {evidence_id} references unknown source_id: {source_id}"
            )
        seen.add(evidence_id)
        normalized.append(
            {
                "evidence_id": evidence_id,
                "property_id": property_id,
                "source_id": source_id,
                "claim_type": clean_text(row.get("claim_type")),
                "claim_value": clean_text(row.get("claim_value")),
                "confidence_contribution": parse_float_or_none(
                    row.get("confidence_contribution")
                )
                or 0.0,
                "evidence_note": clean_text(row.get("evidence_note")),
            }
        )
    return normalized


def normalize_change_events(
    rows: list[dict[str, str]],
    property_ids: set[str],
    source_ids: set[str],
) -> list[dict[str, Any]]:
    normalized = []
    seen: set[str] = set()
    for row in rows:
        event_id = clean_text(row.get("event_id"))
        property_id = clean_text(row.get("property_id"))
        source_id = clean_text(row.get("source_id"))
        if event_id in seen:
            raise PipelineInputError(f"Duplicate event_id: {event_id}")
        if property_id not in property_ids:
            raise PipelineInputError(
                f"Change event {event_id} references unknown property_id: {property_id}"
            )
        if source_id and source_id not in source_ids:
            raise PipelineInputError(
                f"Change event {event_id} references unknown source_id: {source_id}"
            )
        seen.add(event_id)
        normalized.append({field: clean_text(row.get(field)) for field in CHANGE_EVENT_FIELDS})
    return normalized


def parse_optional_float(value: object, label: str) -> float | None:
    try:
        return parse_float_or_none(value)
    except ValueError as exc:
        raise PipelineInputError(f"Invalid numeric value for {label}: {value}") from exc


def parse_optional_int(value: object, label: str) -> int | None:
    try:
        return parse_int_or_none(value)
    except ValueError as exc:
        raise PipelineInputError(f"Invalid integer value for {label}: {value}") from exc


def normalize_property_facts(
    rows: list[dict[str, str]],
    property_ids: set[str],
) -> list[dict[str, Any]]:
    normalized = []
    seen: set[str] = set()
    for row in rows:
        property_id = clean_text(row.get("property_id"))
        if property_id not in property_ids:
            raise PipelineInputError(
                f"Property facts row references unknown property_id: {property_id}"
            )
        if property_id in seen:
            raise PipelineInputError(f"Duplicate property facts row for {property_id}")
        seen.add(property_id)

        output: dict[str, Any] = {}
        for field in PROPERTY_FACT_FIELDS:
            if field in PROPERTY_FACT_FLOAT_FIELDS:
                output[field] = parse_optional_float(row.get(field), field)
            elif field in PROPERTY_FACT_INT_FIELDS:
                output[field] = parse_optional_int(row.get(field), field)
            else:
                output[field] = clean_text(row.get(field))
        normalized.append(output)
    return normalized


def normalize_property_permits(
    rows: list[dict[str, str]],
    property_ids: set[str],
    source_ids: set[str],
) -> list[dict[str, Any]]:
    normalized = []
    seen: set[str] = set()
    for row in rows:
        property_id = clean_text(row.get("property_id"))
        source_id = clean_text(row.get("source_id"))
        permit_number = clean_text(row.get("permit_number"))
        if property_id not in property_ids:
            raise PipelineInputError(
                f"Property permit {permit_number or '(blank)'} references unknown property_id: {property_id}"
            )
        if source_id and source_id not in source_ids:
            raise PipelineInputError(
                f"Property permit {permit_number or '(blank)'} references unknown source_id: {source_id}"
            )

        permit_key = "|".join(
            [
                property_id,
                permit_number,
                clean_text(row.get("issue_date")),
                clean_text(row.get("permit_type")),
                clean_text(row.get("work_description")),
            ]
        )
        if permit_key in seen:
            continue
        seen.add(permit_key)

        output: dict[str, Any] = {}
        for field in PROPERTY_PERMIT_FIELDS:
            if field in PROPERTY_PERMIT_FLOAT_FIELDS:
                output[field] = parse_optional_float(row.get(field), field)
            elif field in PROPERTY_PERMIT_INT_FIELDS:
                output[field] = parse_optional_int(row.get(field), field)
            else:
                output[field] = clean_text(row.get(field))
        normalized.append(output)
    return sorted(
        normalized,
        key=lambda item: (
            str(item.get("property_id", "")),
            str(item.get("issue_date", "")),
            str(item.get("permit_number", "")),
        ),
        reverse=True,
    )


def normalize_properties(
    rows: list[dict[str, str]],
    evidence_rows: list[dict[str, Any]],
    run_id: str,
    warnings: list[PipelineWarning],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence_by_property: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for evidence in evidence_rows:
        evidence_by_property[evidence["property_id"]].append(evidence)

    properties = []
    versions = []
    seen_property_ids: set[str] = set()
    seen_slugs: set[str] = set()

    for index, row in enumerate(rows, start=2):
        property_id = clean_text(row.get("property_id"))
        if property_id in seen_property_ids:
            raise PipelineInputError(f"Duplicate property_id: {property_id}")
        seen_property_ids.add(property_id)

        parcel_id = normalize_parcel_id(row.get("parcel_id"))
        address = normalize_address(row.get("canonical_address"))
        city = clean_text(row.get("city"))
        state = clean_text(row.get("state")).upper()
        zip_code = clean_text(row.get("zip"))

        try:
            latitude = parse_float_or_none(row.get("latitude"))
            longitude = parse_float_or_none(row.get("longitude"))
        except ValueError as exc:
            raise PipelineInputError(f"Invalid coordinate on properties_source.csv row {index}: {exc}") from exc

        if latitude is not None and not -90 <= latitude <= 90:
            raise PipelineInputError(f"Latitude out of range on row {index}: {latitude}")
        if longitude is not None and not -180 <= longitude <= 180:
            raise PipelineInputError(f"Longitude out of range on row {index}: {longitude}")
        if latitude is None or longitude is None:
            warnings.append(
                PipelineWarning(
                    "missing_coordinates",
                    f"Property {property_id} has no latitude/longitude and will not appear on the map",
                )
            )
        elif not (44 <= latitude <= 46 and -94 <= longitude <= -92):
            warnings.append(
                PipelineWarning(
                    "coordinate_outside_minneapolis_area",
                    f"Property {property_id} coordinates look outside the Minneapolis area",
                )
            )

        try:
            is_current = parse_bool(row.get("is_current"))
        except ValueError as exc:
            raise PipelineInputError(f"Invalid is_current on row {index}: {exc}") from exc

        try:
            is_official_mpha_listing = (
                parse_bool(row.get("is_official_mpha_listing"))
                if clean_text(row.get("is_official_mpha_listing"))
                else False
            )
        except ValueError as exc:
            raise PipelineInputError(f"Invalid is_official_mpha_listing on row {index}: {exc}") from exc

        try:
            estimated_unit_count = parse_int_or_none(row.get("estimated_unit_count"))
        except ValueError as exc:
            raise PipelineInputError(
                f"Invalid estimated_unit_count on row {index}: {exc}"
            ) from exc

        property_evidence = evidence_by_property[property_id]
        if not property_evidence:
            warnings.append(
                PipelineWarning(
                    "missing_property_evidence",
                    f"Property {property_id} has no evidence rows; confidence will be uncertain",
                )
            )

        confidence_level, confidence_score = compute_confidence(row, property_evidence)

        provided_slug = clean_text(row.get("detail_url_slug"))
        slug = slugify(provided_slug) if provided_slug else slugify(address, parcel_id or property_id)
        if slug in seen_slugs:
            slug = slugify(slug, property_id)
        if slug in seen_slugs:
            raise PipelineInputError(f"Could not create unique slug for {property_id}")
        seen_slugs.add(slug)

        property_record = {
            "property_id": property_id,
            "canonical_address": address,
            "city": city,
            "state": state,
            "zip": zip_code,
            "parcel_id": parcel_id,
            "latitude": latitude,
            "longitude": longitude,
            "current_owner_name": clean_text(row.get("current_owner_name")),
            "current_taxpayer_name": clean_text(row.get("current_taxpayer_name")),
            "official_property_name": clean_text(row.get("official_property_name")),
            "official_listed_address": normalize_address(row.get("official_listed_address")),
            "is_official_mpha_listing": is_official_mpha_listing,
            "property_type": clean_text(row.get("property_type")),
            "estimated_unit_count": estimated_unit_count,
            "unit_count_source": clean_text(row.get("unit_count_source")),
            "unit_count_confidence": clean_text(row.get("unit_count_confidence")),
            "unit_count_notes": clean_text(row.get("unit_count_notes")),
            "ward": clean_text(row.get("ward")),
            "neighborhood": clean_text(row.get("neighborhood")),
            "community": clean_text(row.get("community")),
            "police_precinct": clean_text(row.get("police_precinct")),
            "police_sector": clean_text(row.get("police_sector")),
            "current_status": clean_text(row.get("current_status")),
            "confidence_level": confidence_level,
            "confidence_score": confidence_score,
            "public_notes": clean_text(row.get("public_notes")),
            "first_seen_date": clean_text(row.get("first_seen_date")),
            "last_seen_date": clean_text(row.get("last_seen_date")),
            "is_current": is_current,
            "detail_url_slug": slug,
        }
        properties.append(property_record)

        version_id = stable_hash(
            property_id,
            parcel_id,
            address,
            property_record["official_property_name"],
            property_record["official_listed_address"],
            property_record["current_owner_name"],
            property_record["current_taxpayer_name"],
            property_record["current_status"],
            confidence_level,
        )
        versions.append(
            {
                "property_id": property_id,
                "version_id": version_id,
                "valid_from": property_record["first_seen_date"],
                "valid_to": "" if is_current else property_record["last_seen_date"],
                "is_current": is_current,
                "parcel_id": parcel_id,
                "owner_name": property_record["current_owner_name"],
                "taxpayer_name": property_record["current_taxpayer_name"],
                "address": address,
                "property_type": property_record["property_type"],
                "estimated_unit_count": estimated_unit_count,
                "status": property_record["current_status"],
                "confidence_level": confidence_level,
                "confidence_score": confidence_score,
                "source_run_id": run_id,
                "change_reason": "current source snapshot",
            }
        )

    return properties, versions


def expected_input_message(project_root: Path) -> str:
    lines = [
        "Required public source inputs are missing.",
        "",
        "Expected files:",
    ]
    for path in REQUIRED_INPUT_FILES.values():
        lines.append(f"  - {project_root / path}")
    lines.extend(
        [
            "",
            "Expected schemas:",
            f"  properties_source.csv: {', '.join(PROPERTY_SOURCE_REQUIRED_FIELDS)}",
            f"  source_records.csv: {', '.join(SOURCE_RECORD_FIELDS)}",
            f"  property_evidence.csv: {', '.join(PROPERTY_EVIDENCE_FIELDS)}",
            f"  change_events.csv optional: {', '.join(CHANGE_EVENT_FIELDS)}",
            f"  property_facts.csv optional: {', '.join(PROPERTY_FACT_FIELDS)}",
            f"  property_permits.csv optional: {', '.join(PROPERTY_PERMIT_FIELDS)}",
            "",
            "Do not create mock properties. Add official public exports/source files, then rerun:",
            "  python etl/run_pipeline.py",
        ]
    )
    return "\n".join(lines)


def validate_config(project_root: Path) -> int:
    missing = [
        project_root / relative_path
        for relative_path in REQUIRED_INPUT_FILES.values()
        if not (project_root / relative_path).exists()
    ]
    if missing:
        print(expected_input_message(project_root))
        print("")
        print("Validation mode passed: scaffold is present, but normal ETL generation would fail until inputs are added.")
        return 0

    for label, relative_path in REQUIRED_INPUT_FILES.items():
        fields = {
            "properties_source": PROPERTY_SOURCE_REQUIRED_FIELDS,
            "source_records": SOURCE_RECORD_FIELDS,
            "property_evidence": PROPERTY_EVIDENCE_FIELDS,
        }[label]
        read_csv(project_root / relative_path, fields)
    optional_change_path = project_root / OPTIONAL_INPUT_FILES["change_events"]
    if optional_change_path.exists():
        read_csv(optional_change_path, CHANGE_EVENT_FIELDS)
    optional_facts_path = project_root / OPTIONAL_INPUT_FILES["property_facts"]
    if optional_facts_path.exists():
        read_csv(optional_facts_path, PROPERTY_FACT_FIELDS)
    optional_permits_path = project_root / OPTIONAL_INPUT_FILES["property_permits"]
    if optional_permits_path.exists():
        read_csv(optional_permits_path, PROPERTY_PERMIT_FIELDS)
    print("Validation mode passed: required ETL inputs are present and schemas are readable.")
    return 0


def run_pipeline(project_root: Path) -> int:
    started_at = utc_now()
    run_id = started_at.replace(":", "").replace("-", "")
    warnings: list[PipelineWarning] = []

    missing = [
        project_root / relative_path
        for relative_path in REQUIRED_INPUT_FILES.values()
        if not (project_root / relative_path).exists()
    ]
    if missing:
        raise PipelineInputError(expected_input_message(project_root))

    property_rows = read_csv(
        project_root / REQUIRED_INPUT_FILES["properties_source"],
        PROPERTY_SOURCE_REQUIRED_FIELDS,
    )
    source_rows = read_csv(
        project_root / REQUIRED_INPUT_FILES["source_records"],
        SOURCE_RECORD_FIELDS,
    )
    evidence_rows_raw = read_csv(
        project_root / REQUIRED_INPUT_FILES["property_evidence"],
        PROPERTY_EVIDENCE_FIELDS,
    )
    change_rows_raw = read_optional_csv(
        project_root / OPTIONAL_INPUT_FILES["change_events"],
        CHANGE_EVENT_FIELDS,
    )
    property_facts_raw = read_optional_csv(
        project_root / OPTIONAL_INPUT_FILES["property_facts"],
        PROPERTY_FACT_FIELDS,
    )
    property_permits_raw = read_optional_csv(
        project_root / OPTIONAL_INPUT_FILES["property_permits"],
        PROPERTY_PERMIT_FIELDS,
    )
    civic_boundaries = read_optional_json(
        project_root / OPTIONAL_INPUT_FILES["civic_boundaries"],
        {
            "type": "FeatureCollection",
            "metadata": {
                "schema_version": "1.0.0",
                "generated_at": None,
            },
            "features": [],
        },
    )

    validate_required_values(property_rows, PROPERTY_REQUIRED_VALUES, "properties_source.csv")
    validate_required_values(source_rows, SOURCE_REQUIRED_VALUES, "source_records.csv")
    validate_required_values(evidence_rows_raw, EVIDENCE_REQUIRED_VALUES, "property_evidence.csv")
    if change_rows_raw:
        validate_required_values(change_rows_raw, CHANGE_REQUIRED_VALUES, "change_events.csv")

    property_ids = {clean_text(row.get("property_id")) for row in property_rows}
    source_records = normalize_source_records(project_root, source_rows, warnings)
    source_ids = {row["source_id"] for row in source_records}
    property_evidence = normalize_evidence(evidence_rows_raw, property_ids, source_ids)
    property_facts = normalize_property_facts(property_facts_raw, property_ids)
    property_permits = normalize_property_permits(
        property_permits_raw,
        property_ids,
        source_ids,
    )
    properties, property_versions = normalize_properties(
        property_rows,
        property_evidence,
        run_id,
        warnings,
    )
    change_events = normalize_change_events(change_rows_raw, property_ids, source_ids)

    generated_at = utc_now()
    export_public_files(
        output_dir=project_root / "data" / "public",
        site_data_dir=project_root / "public" / "data",
        generated_at=generated_at,
        properties=properties,
        property_versions=[
            {field: row.get(field, "") for field in PROPERTY_VERSION_FIELDS}
            for row in property_versions
        ],
        source_records=source_records,
        property_evidence=property_evidence,
        change_events=change_events,
        property_facts=property_facts,
        property_permits=property_permits,
        civic_boundaries=civic_boundaries,
    )

    run = PipelineRun(
        run_id=run_id,
        started_at=started_at,
        completed_at=utc_now(),
        status="success",
        git_commit=get_git_commit(project_root),
        row_counts={
            "properties": len(properties),
            "property_versions": len(property_versions),
            "source_records": len(source_records),
            "property_evidence": len(property_evidence),
            "change_events": len(change_events),
            "property_facts": len(property_facts),
            "property_permits": len(property_permits),
        },
        warnings=warnings,
    )
    processed_dir = project_root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    (processed_dir / "etl-run-last.json").write_text(
        json.dumps(
            {
                "run_id": run.run_id,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "status": run.status,
                "git_commit": run.git_commit,
                "row_counts": run.row_counts,
                "warnings": [warning.__dict__ for warning in run.warnings],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"status": "success", "row_counts": run.row_counts}, indent=2))
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning.code}: {warning.message}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static public housing data files.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of etl/.",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate ETL scaffold and input schemas without requiring generation to succeed.",
    )
    args = parser.parse_args()
    project_root = args.project_root.resolve()

    try:
        if args.validate_config:
            return validate_config(project_root)
        return run_pipeline(project_root)
    except PipelineInputError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
