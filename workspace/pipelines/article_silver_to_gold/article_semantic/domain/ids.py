"""Domain rules for deterministic semantic graph identifiers."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

from .models import EntityType


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_name(value: str) -> str:
    """Normalize a display name for identity comparisons."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\s+", " ", normalized.strip())
    return normalized.casefold()


def entity_id(entity_type: EntityType, normalized_name: str) -> str:
    """Return a type-separated deterministic entity identifier."""
    return _sha256(f"{entity_type.value}:{normalized_name}")


def event_id(
    article_id_value: str,
    event_name: str,
    occurred_at: datetime | None,
) -> str:
    """Return a deterministic event identifier scoped to an article."""
    identity = json.dumps(
        {
            "article_id": article_id_value,
            "event_name": normalize_name(event_name),
            "occurred_at": (None if occurred_at is None else occurred_at.isoformat()),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256(identity)


def batch_request_key(
    article_id_value: str,
    dt_ingested_at: datetime,
    ont_version: str,
) -> str:
    """Return the stable identity of one article version and ontology version."""
    if dt_ingested_at.tzinfo is None or dt_ingested_at.utcoffset() is None:
        raise ValueError("dt_ingested_at must be timezone-aware")
    identity = json.dumps(
        {
            "article_id": article_id_value,
            "dt_ingested_at": dt_ingested_at.astimezone(UTC).isoformat(),
            "ont_version": ont_version,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256(identity)


def batch_key() -> str:
    """Return a unique, display-name-safe identifier for one Batch attempt."""
    return f"ontology-{uuid4().hex}"
