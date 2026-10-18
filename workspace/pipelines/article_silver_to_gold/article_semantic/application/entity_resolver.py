"""Application service for deterministic entity resolution."""

from __future__ import annotations

from ..domain.ids import entity_id, normalize_name
from ..domain.models import ArticleExtraction, CanonicalEntity


class DeterministicEntityResolver:
    """Create stable entity IDs without depending on a downstream graph store."""

    def resolve(self, extraction: ArticleExtraction) -> dict[str, CanonicalEntity]:
        """Return canonical entities keyed by their extraction-local IDs."""
        resolved: dict[str, CanonicalEntity] = {}
        for entity in extraction.entities:
            normalized_name = normalize_name(entity.name)
            resolved[entity.local_id] = CanonicalEntity(
                canonical_id=entity_id(entity.entity_type, normalized_name),
                entity_type=entity.entity_type,
                name=entity.name,
                normalized_name=normalized_name,
            )
        return resolved
