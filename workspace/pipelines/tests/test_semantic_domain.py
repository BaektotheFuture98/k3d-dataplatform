import json
from datetime import UTC, datetime

from article_semantic.application.entity_resolver import DeterministicEntityResolver
from article_semantic.application.semantic_analyzer import analyze_batch_response
from article_semantic.config import ROOT
from article_semantic.domain.models import ArticleExtraction
from article_semantic.infrastructure.gemini_batch_client import GeminiBatchClient
from article_semantic.infrastructure.rdf_projector import project_to_rdf
from article_semantic.infrastructure.shacl_validator import ShaclValidator


def silver_row():
    return dict(article_id='AR_TEST', au_url='https://example.invalid/article',
                ar_title='Example launches a product', ar_content='Example announced a product.',
                language='en', dt_created_at=datetime(2026, 1, 1, tzinfo=UTC),
                dt_ingested_at=datetime(2026, 1, 2, tzinfo=UTC))


def extraction():
    return dict(entities=[dict(local_id='c1', entity_type='Company', name='Example')],
                events=[dict(local_id='e1', name='Product announcement', occurred_at=None)],
                impacts=[dict(event_ref='e1', target_entity_ref='c1', confidence=0.9, direction='POSITIVE')])


def analyze(payload, projector=project_to_rdf):
    return analyze_batch_response(json.dumps(payload), silver_row(),
        resolver=DeterministicEntityResolver(), projector=projector,
        validator=ShaclValidator(ROOT / 'ontology'), ont_version='test-v1',
        analyzed_at=datetime(2026, 1, 3, tzinfo=UTC))


def test_valid_result_becomes_versioned_canonical_graph():
    result = analyze(extraction())
    assert result['ont_version'] == 'test-v1'
    graph = json.loads(result['ont_candidate_json'])
    assert graph['article']['article_id'] == 'AR_TEST'
    assert {r['relation_type'] for r in graph['relations']} == {'MENTIONS', 'REPORTS', 'AFFECTS'}


def test_bad_reference_and_person_impact_are_rejected():
    bad = extraction()
    bad['impacts'][0]['target_entity_ref'] = 'missing'
    assert analyze(bad) is None
    bad = extraction()
    bad['entities'][0]['entity_type'] = 'Person'
    assert analyze(bad) is None


def test_shacl_failure_never_produces_gold_row():
    from rdflib import URIRef
    def missing_content(candidate):
        graph = project_to_rdf(candidate)
        graph.remove((None, URIRef('https://finbridge.dev/ontology/content'), None))
        return graph
    assert analyze(extraction(), projector=missing_content) is None


def test_entity_identity_normalizes_case_width_and_whitespace():
    resolver = DeterministicEntityResolver()
    def resolve(name):
        value = ArticleExtraction.model_validate({'entities': [dict(local_id='c', entity_type='Company', name=name)]})
        return resolver.resolve(value)['c'].canonical_id
    assert resolve(' ＥＸＡＭＰＬＥ ') == resolve('example')


def test_batch_preparation_is_bounded_and_never_constructs_remote_client():
    # Explicitly inject an inert transport. prepare() only serializes requests.
    client = GeminiBatchClient(api_key='offline-only', model='offline', raw_client=object())
    rows = [silver_row(), {**silver_row(), 'article_id': 'AR_SECOND'}]
    prepared = client.prepare(rows, ont_version='test-v1', max_items=1, max_bytes=100_000)
    assert len(prepared.accepted) == 1
    again = client.prepare(rows[:1], ont_version='test-v1', max_items=1, max_bytes=100_000)
    assert prepared.accepted[0].manifest.request_key == again.accepted[0].manifest.request_key
    oversized = client.prepare(rows[:1], ont_version='test-v1', max_items=1, max_bytes=1)
    assert len(oversized.oversized) == 1 and not oversized.accepted
