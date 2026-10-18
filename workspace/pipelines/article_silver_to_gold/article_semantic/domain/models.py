"""Domain contracts for semantic extraction and canonical graph candidates."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class EntityType(StrEnum):
    COMPANY = "Company"
    PERSON = "Person"
    PRODUCT = "Product"
    INDUSTRY = "Industry"


class ImpactDirection(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class RelationType(StrEnum):
    MENTIONS = "MENTIONS"
    REPORTS = "REPORTS"
    AFFECTS = "AFFECTS"


class ArticleInput(BaseModel):
    article_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime


class ExtractedEntity(BaseModel):
    local_id: str = Field(min_length=1)
    entity_type: EntityType
    name: str = Field(min_length=1)


class ExtractedEvent(BaseModel):
    local_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    occurred_at: datetime | None = None


class EventImpact(BaseModel):
    event_ref: str = Field(min_length=1)
    target_entity_ref: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    direction: ImpactDirection


class ArticleExtraction(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)
    impacts: list[EventImpact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph_references(self) -> ArticleExtraction:
        event_ids = {event.local_id for event in self.events}
        all_ids = [
            *(entity.local_id for entity in self.entities),
            *(event.local_id for event in self.events),
        ]

        if len(set(all_ids)) != len(all_ids):
            raise ValueError(
                "local IDs must be globally unique across entities and events"
            )

        entity_by_id = {entity.local_id: entity for entity in self.entities}
        for impact in self.impacts:
            if impact.event_ref not in event_ids:
                raise ValueError(
                    f"event_ref does not reference an extracted event: {impact.event_ref}"
                )
            target = entity_by_id.get(impact.target_entity_ref)
            if target is None:
                raise ValueError(
                    "target_entity_ref does not reference an extracted entity: "
                    f"{impact.target_entity_ref}"
                )
            if target.entity_type is EntityType.PERSON:
                raise ValueError("Person cannot be an AFFECTS target")
        return self


class CanonicalArticle(BaseModel):
    article_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime


class CanonicalEntity(BaseModel):
    canonical_id: str = Field(min_length=1)
    entity_type: EntityType
    name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)


class CanonicalEvent(BaseModel):
    event_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    occurred_at: datetime | None = None


class CanonicalRelation(BaseModel):
    relation_type: RelationType
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    direction: ImpactDirection | None = None
    evidence_article_id: str | None = None

    @model_validator(mode="after")
    def validate_impact_metadata(self) -> CanonicalRelation:
        impact_values = (self.confidence, self.direction, self.evidence_article_id)
        if self.relation_type is RelationType.AFFECTS and any(
            value is None for value in impact_values
        ):
            raise ValueError(
                "an AFFECTS relation requires confidence, direction, and "
                "evidence_article_id"
            )
        if self.relation_type is not RelationType.AFFECTS and any(
            value is not None for value in impact_values
        ):
            raise ValueError("only AFFECTS relations may carry impact fields")
        return self


class CanonicalGraphCandidate(BaseModel):
    article: CanonicalArticle
    entities: list[CanonicalEntity] = Field(default_factory=list)
    events: list[CanonicalEvent] = Field(default_factory=list)
    relations: list[CanonicalRelation] = Field(default_factory=list)


class ShaclValidationResult(BaseModel):
    conforms: bool
    report_text: str
