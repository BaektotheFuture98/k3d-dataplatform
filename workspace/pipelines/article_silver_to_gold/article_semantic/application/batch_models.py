"""Application contracts for durable Gemini Batch processing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, field_validator

from ..domain.models import ArticleInput


class BatchStatus(StrEnum):
    PREPARED = "PREPARED"
    QUOTA_PAUSED = "QUOTA_PAUSED"
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    RETRIED = "RETRIED"
    COMPLETED = "COMPLETED"


class RemoteBatchState(StrEnum):
    UNSPECIFIED = "UNSPECIFIED"
    QUEUED = "QUEUED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    UPDATING = "UPDATING"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("dt_ingested_at must be timezone-aware")


@dataclass(frozen=True)
class BatchManifestItem:
    request_key: str
    article_id: str
    dt_ingested_at: datetime

    def __post_init__(self) -> None:
        if not self.request_key or not self.article_id:
            raise ValueError("request_key and article_id must not be blank")
        _require_aware(self.dt_ingested_at)


@dataclass(frozen=True)
class BatchRequest:
    manifest: BatchManifestItem
    article: ArticleInput


@dataclass(frozen=True)
class PreparedRequests:
    accepted: tuple[BatchRequest, ...]
    oversized: tuple[BatchRequest, ...]


@dataclass(frozen=True)
class RemoteBatchItemResult:
    request_key: str
    response_text: str | None
    error_code: str | None


@dataclass(frozen=True)
class RemoteBatchJob:
    name: str
    display_name: str
    state: RemoteBatchState
    results: tuple[RemoteBatchItemResult, ...] = ()


@dataclass(frozen=True)
class BatchJobRecord:
    batch_key: str
    google_job_name: str | None
    ont_version: str
    article_ids_json: str
    status: BatchStatus
    next_retry_at: datetime | None
    dt_created_at: datetime
    dt_submitted_at: datetime | None
    dt_completed_at: datetime | None


class _ManifestItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_key: str
    article_id: str
    dt_ingested_at: datetime

    @field_validator("request_key", "article_id")
    @classmethod
    def reject_blank_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("manifest identity must not be blank")
        return value

    @field_validator("dt_ingested_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        _require_aware(value)
        return value


_MANIFEST_ADAPTER = TypeAdapter(list[_ManifestItemModel])


def _isoformat(value: datetime) -> str:
    rendered = value.isoformat()
    return (
        rendered.removesuffix("+00:00") + "Z"
        if rendered.endswith("+00:00")
        else rendered
    )


def serialize_manifest(items: tuple[BatchManifestItem, ...]) -> str:
    """Serialize an ordered manifest without persisting article bodies."""
    payload: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if item.request_key in seen:
            raise ValueError(f"duplicate request_key: {item.request_key}")
        seen.add(item.request_key)
        payload.append(
            {
                "request_key": item.request_key,
                "article_id": item.article_id,
                "dt_ingested_at": _isoformat(item.dt_ingested_at),
            }
        )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_manifest(value: str) -> tuple[BatchManifestItem, ...]:
    """Validate and deserialize an ordered persisted manifest."""
    parsed = _MANIFEST_ADAPTER.validate_json(value)
    items = tuple(
        BatchManifestItem(item.request_key, item.article_id, item.dt_ingested_at)
        for item in parsed
    )
    request_keys = [item.request_key for item in items]
    if len(set(request_keys)) != len(request_keys):
        raise ValueError("duplicate request_key in manifest")
    return items
