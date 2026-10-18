"""RDFLib adapter that projects graph candidates for SHACL validation."""

from __future__ import annotations

from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

from ..domain.models import CanonicalGraphCandidate, EntityType, RelationType

ONTOLOGY = Namespace("https://finbridge.dev/ontology/")
RESOURCE = Namespace("https://finbridge.dev/resource/")

_ENTITY_CLASS_BY_TYPE = {
    EntityType.COMPANY: ONTOLOGY.Company,
    EntityType.PERSON: ONTOLOGY.Person,
    EntityType.PRODUCT: ONTOLOGY.Product,
    EntityType.INDUSTRY: ONTOLOGY.Industry,
}

_PREDICATE_BY_RELATION_TYPE = {
    RelationType.MENTIONS: ONTOLOGY.mentions,
    RelationType.REPORTS: ONTOLOGY.reports,
    RelationType.AFFECTS: ONTOLOGY.affects,
}


def _resource_uri(identifier: str) -> URIRef:
    return RESOURCE[identifier]


def project_to_rdf(candidate: CanonicalGraphCandidate) -> Graph:
    """Create the validation-only RDF representation of a graph candidate."""
    graph = Graph()

    article_node = _resource_uri(candidate.article.article_id)
    graph.add((article_node, RDF.type, ONTOLOGY.Article))
    graph.add((article_node, ONTOLOGY.articleId, Literal(candidate.article.article_id)))
    graph.add((article_node, ONTOLOGY.name, Literal(candidate.article.title)))
    graph.add(
        (
            article_node,
            ONTOLOGY.sourceUrl,
            Literal(candidate.article.source_url, datatype=XSD.anyURI),
        )
    )
    graph.add(
        (
            article_node,
            ONTOLOGY.content,
            Literal(candidate.article.content, datatype=XSD.string),
        )
    )
    graph.add(
        (
            article_node,
            ONTOLOGY.createdAt,
            Literal(candidate.article.created_at, datatype=XSD.dateTime),
        )
    )

    for entity in candidate.entities:
        entity_node = _resource_uri(entity.canonical_id)
        graph.add((entity_node, RDF.type, _ENTITY_CLASS_BY_TYPE[entity.entity_type]))
        graph.add((entity_node, ONTOLOGY.canonicalId, Literal(entity.canonical_id)))
        graph.add((entity_node, ONTOLOGY.name, Literal(entity.name)))

    for event in candidate.events:
        event_node = _resource_uri(event.event_id)
        graph.add((event_node, RDF.type, ONTOLOGY.NewsEvent))
        graph.add((event_node, ONTOLOGY.eventId, Literal(event.event_id)))
        graph.add((event_node, ONTOLOGY.name, Literal(event.name)))
        if event.occurred_at is not None:
            graph.add((event_node, ONTOLOGY.occurredAt, Literal(event.occurred_at)))

    for relation in candidate.relations:
        graph.add(
            (
                _resource_uri(relation.source_id),
                _PREDICATE_BY_RELATION_TYPE[relation.relation_type],
                _resource_uri(relation.target_id),
            )
        )

    return graph
