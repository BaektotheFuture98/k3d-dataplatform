"""Turn one completed Batch response into a validated Gold row."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from pydantic import ValidationError

from ..domain.graph_builder import build_graph_candidate
from ..domain.models import (
    ArticleExtraction,
    ArticleInput,
    CanonicalEntity,
    CanonicalGraphCandidate,
)
from .contracts import SILVER_COLUMNS

LOGGER = logging.getLogger(__name__)


class Resolver(Protocol):
    def resolve(self, extraction: ArticleExtraction) -> dict[str, CanonicalEntity]: ...


class Projector(Protocol):
    def __call__(self, candidate: CanonicalGraphCandidate) -> object: ...


class Validator(Protocol):
    def validate(self, graph: object) -> Any: ...


def _article_from_silver_row(row: Mapping[str, object]) -> ArticleInput:
    return ArticleInput.model_validate(
        {
            "article_id": row["article_id"],
            "source_url": row["au_url"],
            "title": row["ar_title"],
            "content": row["ar_content"],
            "created_at": row["dt_created_at"],
        }
    )


def analyze_batch_response(
    response_text: str,
    row: Mapping[str, object],
    *,
    resolver: Resolver,
    projector: Projector,
    validator: Validator,
    ont_version: str,
    analyzed_at: datetime,
) -> dict[str, object] | None:
    """Validate one asynchronous response and return a Gold row on success."""
    article_id = "unavailable"
    try:
        article = _article_from_silver_row(row)
        article_id = article.article_id
        extraction = ArticleExtraction.model_validate_json(response_text)
        candidate = build_graph_candidate(
            article, extraction, resolver.resolve(extraction)
        )
        validation = validator.validate(projector(candidate))
    except (KeyError, ValidationError) as error:
        LOGGER.error(
            "article_id=%s stage=validate error_type=%s",
            article_id,
            type(error).__name__,
        )
        return None
    except Exception:
        LOGGER.exception("article_id=%s stage=analyze", article_id)
        return None

    if not validation.conforms:
        LOGGER.error(
            "article_id=%s stage=shacl status=discarded",
            article_id,
        )
        return None

    return {
        **{column: row[column] for column in SILVER_COLUMNS},
        "ont_version": ont_version,
        "ont_analyzed_at": analyzed_at,
        "ont_candidate_json": candidate.model_dump_json(),
    }
