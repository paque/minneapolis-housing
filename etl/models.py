from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SCHEMA_VERSION = "1.0.0"

ConfidenceLevel = Literal["confirmed", "likely", "uncertain", "excluded"]

PROPERTY_FIELDS = [
    "property_id",
    "canonical_address",
    "city",
    "state",
    "zip",
    "parcel_id",
    "latitude",
    "longitude",
    "current_owner_name",
    "current_taxpayer_name",
    "property_type",
    "estimated_unit_count",
    "current_status",
    "confidence_level",
    "confidence_score",
    "public_notes",
    "first_seen_date",
    "last_seen_date",
    "is_current",
    "detail_url_slug",
]

PROPERTY_SOURCE_REQUIRED_FIELDS = [
    "property_id",
    "canonical_address",
    "city",
    "state",
    "zip",
    "parcel_id",
    "latitude",
    "longitude",
    "current_owner_name",
    "current_taxpayer_name",
    "property_type",
    "estimated_unit_count",
    "current_status",
    "public_notes",
    "first_seen_date",
    "last_seen_date",
    "is_current",
    "detail_url_slug",
]

PROPERTY_REQUIRED_VALUES = [
    "property_id",
    "canonical_address",
    "city",
    "state",
    "is_current",
]

PROPERTY_VERSION_FIELDS = [
    "property_id",
    "version_id",
    "valid_from",
    "valid_to",
    "is_current",
    "parcel_id",
    "owner_name",
    "taxpayer_name",
    "address",
    "property_type",
    "estimated_unit_count",
    "status",
    "confidence_level",
    "confidence_score",
    "source_run_id",
    "change_reason",
]

SOURCE_RECORD_FIELDS = [
    "source_id",
    "source_name",
    "source_agency",
    "source_type",
    "source_url",
    "retrieved_at",
    "record_date",
    "raw_file_uri",
    "sha256_hash",
    "public_citation_text",
]

SOURCE_REQUIRED_VALUES = [
    "source_id",
    "source_name",
    "source_agency",
    "source_type",
    "public_citation_text",
]

PROPERTY_EVIDENCE_FIELDS = [
    "evidence_id",
    "property_id",
    "source_id",
    "claim_type",
    "claim_value",
    "confidence_contribution",
    "evidence_note",
]

EVIDENCE_REQUIRED_VALUES = [
    "evidence_id",
    "property_id",
    "source_id",
    "claim_type",
]

CHANGE_EVENT_FIELDS = [
    "event_id",
    "property_id",
    "event_date",
    "event_type",
    "old_value",
    "new_value",
    "source_id",
    "public_note",
]

CHANGE_REQUIRED_VALUES = [
    "event_id",
    "property_id",
    "event_date",
    "event_type",
]

PROPERTY_FACT_FIELDS = [
    "property_id",
    "parcel_id",
    "source_ids",
    "sale_date",
    "sale_value",
    "assessed_land_value",
    "assessed_building_value",
    "assessed_total_value",
    "tax_year",
    "market_year",
    "total_tax",
    "use_classes",
    "zoning",
    "land_use",
    "parcel_area_sqft",
    "acres",
    "year_built",
    "finished_sqft",
    "above_ground_area",
    "below_ground_area",
    "total_units",
    "building_use",
]

PROPERTY_PERMIT_FIELDS = [
    "property_id",
    "parcel_id",
    "permit_number",
    "permit_type",
    "work_type",
    "occupancy_type",
    "status",
    "milestone",
    "value",
    "dwelling_units_new",
    "dwelling_units_eliminated",
    "issue_date",
    "complete_date",
    "work_description",
    "match_method",
    "source_id",
]


@dataclass
class PipelineWarning:
    code: str
    message: str


@dataclass
class PipelineRun:
    run_id: str
    started_at: str
    completed_at: str | None
    status: str
    git_commit: str
    row_counts: dict[str, int]
    warnings: list[PipelineWarning]


class PipelineInputError(RuntimeError):
    """Raised when required public source files are absent or invalid."""
