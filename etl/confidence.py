from __future__ import annotations

from collections.abc import Iterable

from models import ConfidenceLevel
from normalize import clean_text

DIRECT_CONFIRMATION_CLAIMS = {
    "direct_mpha_scattered_site",
    "direct_chr_scattered_site",
    "official_scattered_site_listing",
    "public_housing_property_record",
}

EXCLUSION_CLAIMS = {
    "excluded",
    "not_scattered_site",
    "sold_or_released",
    "non_mpha_chr_owner",
}


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(clean_text(value))
    except ValueError:
        return default


def compute_confidence(
    property_row: dict[str, object],
    evidence_rows: Iterable[dict[str, object]],
) -> tuple[ConfidenceLevel, float]:
    evidence = list(evidence_rows)
    status = clean_text(property_row.get("current_status")).lower()
    property_type = clean_text(property_row.get("property_type")).lower()

    if "excluded" in status or property_type == "excluded":
        return "excluded", 0.0

    if any(clean_text(row.get("claim_type")).lower() in EXCLUSION_CLAIMS for row in evidence):
        return "excluded", 0.0

    score = min(
        1.0,
        sum(max(0.0, _as_float(row.get("confidence_contribution"))) for row in evidence),
    )

    has_direct_evidence = any(
        clean_text(row.get("claim_type")).lower() in DIRECT_CONFIRMATION_CLAIMS
        for row in evidence
    )
    if has_direct_evidence and score >= 0.7:
        return "confirmed", round(score, 3)
    if score >= 0.55:
        return "likely", round(score, 3)
    return "uncertain", round(score, 3)

