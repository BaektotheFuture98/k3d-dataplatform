"""Offline end-to-end probe against isolated Iceberg tables and S3A checkpoints.

The external Batch service is an in-process implementation of the BatchClient
protocol. No Gemini client with a real transport or real API key is constructed.
"""
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pyspark.sql import SparkSession
from pipeline_runtime.settings import BronzeSettings
from article_bronze_to_silver.main import start_stream
from article_semantic.stream import SilverToGoldBatchProcessor
from article_semantic.application.batch_models import RemoteBatchJob, RemoteBatchState, RemoteBatchItemResult
from article_semantic.application.entity_resolver import DeterministicEntityResolver
from article_semantic.config import ROOT
from article_semantic.infrastructure.gemini_batch_client import GeminiBatchClient, GeminiQuotaExceeded
from article_semantic.infrastructure.gold_repository import validate_gold_table
from article_semantic.infrastructure.batch_job_repository import validate_batch_job_table
from article_semantic.infrastructure.rdf_projector import project_to_rdf
from article_semantic.infrastructure.shacl_validator import ShaclValidator

run_id = uuid4().hex
namespace = 'lakehouse.pipeline_smoke_' + run_id
names = {name: namespace + '.' + name for name in ('bronze', 'silver', 'gold', 'jobs')}
prefix = 's3a://warehouse/platform-validation/article-pipelines/' + run_id
spark = SparkSession.builder.appName('article-pipeline-offline-smoke').getOrCreate()
spark.sparkContext.setLogLevel('WARN')
clock = [datetime.now(UTC)]


class OfflineBatchService:
    def __init__(self, *, quota_once=False, bad_result=False):
        self.adapter = GeminiBatchClient(api_key='offline-only', model='offline', raw_client=object())
        self.jobs = {}
        self.requests = {}
        self.submissions = 0
        self.quota_once = quota_once
        self.bad_result = bad_result

    def prepare(self, rows, **options):
        return self.adapter.prepare(rows, **options)

    def find_by_display_name(self, key):
        if self.quota_once:
            self.quota_once = False
            raise GeminiQuotaExceeded('offline simulated quota')
        return tuple(job for job in self.jobs.values() if job.display_name == key)

    def submit(self, key, requests):
        self.submissions += 1
        job = RemoteBatchJob('offline/' + key, key, RemoteBatchState.PENDING)
        self.jobs[job.name] = job
        self.requests[job.name] = requests
        return job

    def get(self, name):
        extraction = {
            'entities': [{'local_id': 'c1', 'entity_type': 'Company', 'name': 'Example'}],
            'events': [{'local_id': 'e1', 'name': 'Product announcement', 'occurred_at': None}],
            'impacts': [{'event_ref': 'e1', 'target_entity_ref': 'c1', 'confidence': 0.9, 'direction': 'POSITIVE'}],
        }
        if self.bad_result:
            extraction['impacts'][0]['target_entity_ref'] = 'missing'
        results = tuple(RemoteBatchItemResult(r.manifest.request_key, json.dumps(extraction), None)
                        for r in self.requests[name])
        return replace(self.jobs[name], state=RemoteBatchState.SUCCEEDED, results=results)

    def cancel(self, name):
        raise AssertionError('No duplicate service jobs are expected')


def processor(service, version):
    return SilverToGoldBatchProcessor(
        batch_client=service, resolver=DeterministicEntityResolver(),
        projector=project_to_rdf, validator=ShaclValidator(ROOT / 'ontology'),
        ont_version=version, batch_size=1, max_bytes=100_000,
        poll_seconds=1, quota_pause_seconds=2, clock=lambda: clock[0],
        silver_table=names['silver'], gold_table=names['gold'], batch_job_table=names['jobs'],
    )


def tick(service, version, batch_id):
    # Reconstruct the processor each time to exercise durable state recovery.
    processor(service, version)(spark.range(1), batch_id)
    clock[0] += timedelta(seconds=3)


def append_article(title, ingested, *, status=200, metadata='{}', url='https://example.invalid/article'):
    row = dict(ingest_key=uuid4().hex, job_id='offline-smoke', start_url='https://example.invalid/',
               source_url=url, canonical_url=url, ar_title=title, ar_content='Example announced a product.',
               metadata_json=metadata, meta_description=None, language=' EN ', http_status_code=status,
               collected_at=ingested, ingested_at=ingested, ar_published_at=datetime(2026, 1, 1))
    spark.createDataFrame([row], spark.table(names['bronze']).schema).writeTo(names['bronze']).append()


def bronze_tick():
    settings = BronzeSettings(bronze_table=names['bronze'], silver_table=names['silver'],
                              checkpoint_uri=prefix + '/bronze-checkpoint', run_mode='available_now')
    query = start_stream(spark, settings)
    query.awaitTermination(90)
    if query.isActive:
        query.stop()
        raise TimeoutError('Bronze bounded stream timed out')
    # foreachBatch may commit through a different SparkSession/catalog cache.
    spark.catalog.refreshTable(names['silver'])


created = []
try:
    spark.sql('CREATE NAMESPACE ' + namespace)
    files = [('bronze_article.sql', 'lakehouse.bronze.article', 'bronze'),
             ('silver_article.sql', 'lakehouse.silver.article', 'silver'),
             ('gold_graph_article.sql', 'lakehouse.gold.graph_article', 'gold'),
             ('ops_ontology_batch_job.sql', 'lakehouse.ops.ontology_batch_job', 'jobs')]
    for filename, original, name in files:
        sql = (Path(__file__).parent / 'sql' / filename).read_text().replace(original, names[name])
        spark.sql(sql)
        created.append(names[name])
    validate_gold_table(spark, table=names['gold'])
    validate_batch_job_table(spark, table=names['jobs'])

    append_article('  First   title ', datetime(2026, 1, 2))
    append_article('Rejected status', datetime(2026, 1, 2), status=404, url='https://example.invalid/bad-status')
    append_article('Rejected JSON', datetime(2026, 1, 2), metadata='{broken', url='https://example.invalid/bad-json')
    bronze_tick()
    rows = spark.table(names['silver']).collect()
    assert len(rows) == 1 and rows[0].ar_title == 'First title' and rows[0].language == 'en'
    assert rows[0].article_id == 'AR' + hashlib.sha256(b'https://example.invalid/article').hexdigest()[:16].upper()
    print('BRONZE_QUALITY_AND_IDENTITY_PASS', flush=True)

    append_article('Updated title', datetime(2026, 1, 3))
    bronze_tick()
    rows = spark.table(names['silver']).collect()
    assert len(rows) == 1 and rows[0].ar_title == 'Updated title'
    assert rows[0].dt_created_at == datetime(2026, 1, 1)
    append_article('Stale title', datetime(2026, 1, 2))
    bronze_tick()
    assert spark.table(names['silver']).first().ar_title == 'Updated title'
    snapshots = spark.table(names['silver'] + '.snapshots').count()
    bronze_tick()
    assert spark.table(names['silver'] + '.snapshots').count() == snapshots
    print('BRONZE_CHECKPOINT_UPDATE_REPLAY_PASS', flush=True)

    service = OfflineBatchService()
    tick(service, 'offline-v1', 0)
    assert spark.table(names['jobs']).first().status == 'SUBMITTED'
    tick(service, 'offline-v1', 1)
    assert spark.table(names['gold']).count() == 1
    tick(service, 'offline-v1', 2)
    assert service.submissions == 1 and spark.table(names['gold']).count() == 1
    print('GOLD_OFFLINE_VALIDATION_RESTART_REPLAY_PASS', flush=True)

    service = OfflineBatchService(quota_once=True)
    tick(service, 'offline-quota', 3)
    assert spark.table(names['jobs']).where("ont_version = 'offline-quota'").first().status == 'QUOTA_PAUSED'
    tick(service, 'offline-quota', 4)
    tick(service, 'offline-quota', 5)
    assert service.submissions == 1
    assert spark.table(names['gold']).where("ont_version = 'offline-quota'").count() == 1
    print('GOLD_DURABLE_QUOTA_RECOVERY_PASS', flush=True)

    service = OfflineBatchService(bad_result=True)
    tick(service, 'offline-invalid', 6)
    tick(service, 'offline-invalid', 7)
    assert spark.table(names['gold']).where("ont_version = 'offline-invalid'").count() == 0
    print('GOLD_INVALID_RESULT_REJECTED_PASS', flush=True)

    service = OfflineBatchService()
    tick(service, 'offline-stale', 8)
    spark.sql(f"UPDATE {names['silver']} SET dt_ingested_at = TIMESTAMP '2026-01-04 00:00:00'")
    tick(service, 'offline-stale', 9)
    assert spark.table(names['gold']).where("ont_version = 'offline-stale'").count() == 0
    print('GOLD_STALE_RESULT_REJECTED_PASS', flush=True)
    print('NO_REAL_GEMINI_CALLS', flush=True)
finally:
    for table in reversed(created):
        spark.catalog.refreshTable(table)
        spark.sql('DROP TABLE ' + table + ' PURGE')
    spark.sql('DROP NAMESPACE IF EXISTS ' + namespace)
    fs = spark._jvm.org.apache.hadoop.fs.FileSystem.get(
        spark._jvm.java.net.URI(prefix), spark.sparkContext._jsc.hadoopConfiguration())
    fs.delete(spark._jvm.org.apache.hadoop.fs.Path(prefix), True)
    # Also remove empty owned table directories / any orphan from an interrupted commit.
    owned_tables = 's3a://warehouse/' + namespace.removeprefix('lakehouse.')
    fs.delete(spark._jvm.org.apache.hadoop.fs.Path(owned_tables), True)
    spark.stop()
    print('OWNED_PROBE_DATA_CLEANED', flush=True)
