from __future__ import annotations

import re
from hashlib import sha256

WHITESPACE_RE = re.compile(r"\s+")
NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def clean_text(value: object) -> str:
    return WHITESPACE_RE.sub(" ", str(value or "").strip())


def normalize_address(value: object) -> str:
    return clean_text(value)


def normalize_parcel_id(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", clean_text(value)).upper()


def slugify(*parts: object) -> str:
    base = "-".join(clean_text(part).lower() for part in parts if clean_text(part))
    slug = NON_SLUG_RE.sub("-", base).strip("-")
    return slug or "property"


def stable_hash(*parts: object, length: int = 12) -> str:
    body = "|".join(clean_text(part) for part in parts)
    return sha256(body.encode("utf-8")).hexdigest()[:length]


def parse_bool(value: object) -> bool:
    normalized = clean_text(value).lower()
    if normalized in {"1", "true", "yes", "y", "current"}:
        return True
    if normalized in {"0", "false", "no", "n", "not current"}:
        return False
    raise ValueError(f"Expected boolean value, got {value!r}")


def parse_int_or_none(value: object) -> int | None:
    text = clean_text(value)
    if text == "":
        return None
    return int(float(text))


def parse_float_or_none(value: object) -> float | None:
    text = clean_text(value)
    if text == "":
        return None
    return float(text)

