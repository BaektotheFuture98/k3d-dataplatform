"""Build domain graph candidates from article extraction output."""

from __future__ import annotations

from .ids import event_id
from .models import (
    ArticleExtraction,
    ArticleInput,
    CanonicalArticle,
    CanonicalEntity,
    CanonicalEvent,
    CanonicalGraphCandidate,
    CanonicalRelation,
    RelationType,
)


def build_graph_candidate(
    article: ArticleInput,
    extraction: ArticleExtraction,
    resolved_entities: dict[str, CanonicalEntity],
) -> CanonicalGraphCandidate:
    """Construct canonical nodes and supported relations for one article."""
    canonical_article = CanonicalArticle(
        article_id=article.article_id,
        source_url=article.source_url,
        title=article.title,
        content=article.content,
        created_at=article.created_at,
    )
    canonical_events = [
        CanonicalEvent(
            event_id=event_id(
                canonical_article.article_id, event.name, event.occurred_at
            ),
            name=event.name,
            occurred_at=event.occurred_at,
        )
        for event in extraction.events
    ]
    events_by_local_id = dict(
        zip(
            (event.local_id for event in extraction.events),
            canonical_events,
            strict=True,
        )
    )
    canonical_entities = [
        resolved_entities[entity.local_id] for entity in extraction.entities
    ]

    relations = [
        CanonicalRelation(
            relation_type=RelationType.MENTIONS,
            source_id=canonical_article.article_id,
            target_id=entity.canonical_id,
        )
        for entity in canonical_entities
    ]
    relations.extend(
        CanonicalRelation(
            relation_type=RelationType.REPORTS,
            source_id=canonical_article.article_id,
            target_id=event.event_id,
        )
        for event in canonical_events
    )
    relations.extend(
        CanonicalRelation(
            relation_type=RelationType.AFFECTS,
            source_id=events_by_local_id[impact.event_ref].event_id,
            target_id=resolved_entities[impact.target_entity_ref].canonical_id,
            confidence=impact.confidence,
            direction=impact.direction,
            evidence_article_id=canonical_article.article_id,
        )
        for impact in extraction.impacts
    )

    return CanonicalGraphCandidate(
        article=canonical_article,
        entities=canonical_entities,
        events=canonical_events,
        relations=relations,
    )
