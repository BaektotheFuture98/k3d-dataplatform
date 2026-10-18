"""Structured Streaming orchestration from Silver to versioned Gold."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.streaming import StreamingQuery

from .application.batch_models import (
    BatchJobRecord,
    BatchRequest,
    BatchStatus,
    PreparedRequests,
    RemoteBatchJob,
    RemoteBatchState,
    parse_manifest,
    serialize_manifest,
)
from .application.entity_resolver import DeterministicEntityResolver
from .application.semantic_analyzer import (
    Projector,
    Resolver,
    Validator,
    analyze_batch_response,
)
from .config import ROOT, Settings
from .domain.ids import batch_key
from .infrastructure.batch_job_repository import (
    load_current_silver_rows,
    select_current_job,
    select_unclaimed_silver_rows,
    upsert_batch_jobs,
    validate_batch_job_table,
)
from .infrastructure.gemini_batch_client import (
    GeminiBatchClient,
    GeminiQuotaExceeded,
)
from .infrastructure.gold_repository import GOLD_TABLE, SILVER_TABLE, merge_gold_rows, validate_gold_table
from .infrastructure.batch_job_repository import BATCH_JOB_TABLE
from .infrastructure.rdf_projector import project_to_rdf
from .infrastructure.shacl_validator import ShaclValidator

LOGGER = logging.getLogger(__name__)
APP_NAME = "article-silver-to-gold"

_REMOTE_ACTIVE_STATES = {
    RemoteBatchState.QUEUED,
    RemoteBatchState.PENDING,
    RemoteBatchState.RUNNING,
    RemoteBatchState.PAUSED,
    RemoteBatchState.UPDATING,
    RemoteBatchState.CANCELLING,
}
_REMOTE_SUCCESS_STATES = {
    RemoteBatchState.SUCCEEDED,
    RemoteBatchState.PARTIALLY_SUCCEEDED,
}
_REMOTE_RETRY_STATES = {
    RemoteBatchState.FAILED,
    RemoteBatchState.EXPIRED,
    RemoteBatchState.CANCELLED,
}


class BatchClient(Protocol):
    def prepare(
        self,
        rows: Iterable[Mapping[str, object]],
        *,
        ont_version: str,
        max_items: int,
        max_bytes: int,
    ) -> PreparedRequests: ...

    def submit(
        self, batch_key: str, requests: tuple[BatchRequest, ...]
    ) -> RemoteBatchJob: ...

    def get(self, job_name: str) -> RemoteBatchJob: ...

    def find_by_display_name(self, batch_key: str) -> tuple[RemoteBatchJob, ...]: ...

    def cancel(self, job_name: str) -> None: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_due(value: datetime | None, now: datetime) -> bool:
    return value is None or _aware_utc(value) <= now


def unique_silver_rows(
    rows: Iterable[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Deduplicate the bounded selection without retaining cross-batch state."""
    seen_article_ids: set[object] = set()
    unique_rows: list[Mapping[str, object]] = []
    for row in rows:
        article_id = row["article_id"]
        if article_id in seen_article_ids:
            continue
        seen_article_ids.add(article_id)
        unique_rows.append(row)
    return unique_rows


class SilverToGoldBatchProcessor:
    """Drive one recoverable Gemini Batch state transition per stream trigger."""

    def __init__(
        self,
        *,
        batch_client: BatchClient,
        resolver: Resolver,
        projector: Projector,
        validator: Validator,
        ont_version: str,
        batch_size: int,
        max_bytes: int,
        poll_seconds: int,
        quota_pause_seconds: int,
        clock: Callable[[], datetime] = _utc_now,
        silver_table: str = SILVER_TABLE,
        gold_table: str = GOLD_TABLE,
        batch_job_table: str = BATCH_JOB_TABLE,
    ) -> None:
        self._batch_client = batch_client
        self._resolver = resolver
        self._projector = projector
        self._validator = validator
        self._ont_version = ont_version
        self._batch_size = batch_size
        self._max_bytes = max_bytes
        self._poll_delay = timedelta(seconds=poll_seconds)
        self._quota_delay = timedelta(seconds=quota_pause_seconds)
        self._clock = clock
        self._silver_table = silver_table
        self._gold_table = gold_table
        self._batch_job_table = batch_job_table

    def _upsert_batch_jobs(self, spark, jobs):
        return upsert_batch_jobs(spark, jobs, table=self._batch_job_table)

    def _load_current_silver_rows(self, spark, manifest):
        return load_current_silver_rows(spark, manifest, table=self._silver_table)

    def __call__(self, trigger_batch: DataFrame, batch_id: int) -> None:
        """Run a bounded transition using the foreachBatch-attached session."""
        spark = trigger_batch.sparkSession
        now = _aware_utc(self._clock())
        current = select_current_job(spark, self._ont_version, table=self._batch_job_table)
        if current is None:
            self._prepare_new_job(spark, now, batch_id)
            return
        if not _is_due(current.next_retry_at, now):
            LOGGER.info(
                "batch_id=%s batch_key=%s status=%s action=waiting",
                batch_id,
                current.batch_key,
                current.status.value,
            )
            return
        if current.status in {BatchStatus.PREPARED, BatchStatus.QUOTA_PAUSED}:
            self._submit_prepared_job(spark, current, now)
            return
        if current.status in {BatchStatus.SUBMITTED, BatchStatus.RUNNING}:
            self._poll_remote_job(spark, current, now)
            return
        if current.status is BatchStatus.RETRY_WAIT:
            self._prepare_retry_attempt(spark, current, now)
            return
        raise RuntimeError(f"unsupported active Batch status: {current.status.value}")

    def _prepare_new_job(
        self, spark: SparkSession, now: datetime, batch_id: int
    ) -> None:
        selected = select_unclaimed_silver_rows(
            spark, self._ont_version, self._batch_size,
            silver_table=self._silver_table, gold_table=self._gold_table, batch_job_table=self._batch_job_table,
        )
        rows = unique_silver_rows(
            row.asDict(recursive=True) for row in selected.collect()
        )
        if not rows:
            return
        prepared = self._batch_client.prepare(
            rows,
            ont_version=self._ont_version,
            max_items=self._batch_size,
            max_bytes=self._max_bytes,
        )
        completed_oversized = [
            BatchJobRecord(
                batch_key=batch_key(),
                google_job_name=None,
                ont_version=self._ont_version,
                article_ids_json=serialize_manifest((request.manifest,)),
                status=BatchStatus.COMPLETED,
                next_retry_at=None,
                dt_created_at=now,
                dt_submitted_at=None,
                dt_completed_at=now,
            )
            for request in prepared.oversized
        ]
        if prepared.oversized:
            LOGGER.error(
                "batch_id=%s stage=prepare oversized=%s status=discarded",
                batch_id,
                len(prepared.oversized),
            )
        new_job = None
        if prepared.accepted:
            new_job = BatchJobRecord(
                batch_key=batch_key(),
                google_job_name=None,
                ont_version=self._ont_version,
                article_ids_json=serialize_manifest(
                    tuple(request.manifest for request in prepared.accepted)
                ),
                status=BatchStatus.PREPARED,
                next_retry_at=None,
                dt_created_at=now,
                dt_submitted_at=None,
                dt_completed_at=None,
            )
        jobs = [*completed_oversized, *(() if new_job is None else (new_job,))]
        self._upsert_batch_jobs(spark, jobs)
        if new_job is not None:
            self._submit_prepared_job(spark, new_job, now, requests=prepared.accepted)

    def _submit_prepared_job(
        self,
        spark: SparkSession,
        job: BatchJobRecord,
        now: datetime,
        *,
        requests: tuple[BatchRequest, ...] | None = None,
    ) -> None:
        try:
            matches = self._batch_client.find_by_display_name(job.batch_key)
        except GeminiQuotaExceeded:
            self._upsert_batch_jobs(
                spark,
                (
                    replace(
                        job,
                        status=BatchStatus.QUOTA_PAUSED,
                        next_retry_at=now + self._quota_delay,
                    ),
                ),
            )
            return

        if matches:
            authoritative = self._authoritative_remote(matches)
            self._cancel_duplicate_jobs(authoritative, matches)
            self._record_submitted_job(spark, job, authoritative, now)
            return

        if requests is None:
            manifest = parse_manifest(job.article_ids_json)
            current_rows = self._load_current_silver_rows(spark, manifest)
            ordered_rows = [
                current_rows[item.request_key]
                for item in manifest
                if item.request_key in current_rows
            ]
            prepared = self._batch_client.prepare(
                ordered_rows,
                ont_version=self._ont_version,
                max_items=len(manifest),
                max_bytes=self._max_bytes,
            )
            expected_keys = {item.request_key for item in manifest}
            requests = tuple(
                request
                for request in prepared.accepted
                if request.manifest.request_key in expected_keys
            )

        if not requests:
            self._upsert_batch_jobs(
                spark,
                (
                    replace(
                        job,
                        status=BatchStatus.COMPLETED,
                        next_retry_at=None,
                        dt_completed_at=now,
                    ),
                ),
            )
            return

        try:
            remote = self._batch_client.submit(job.batch_key, requests)
        except GeminiQuotaExceeded:
            self._upsert_batch_jobs(
                spark,
                (
                    replace(
                        job,
                        status=BatchStatus.QUOTA_PAUSED,
                        next_retry_at=now + self._quota_delay,
                    ),
                ),
            )
            return
        self._record_submitted_job(spark, job, remote, now)

    def _record_submitted_job(
        self,
        spark: SparkSession,
        job: BatchJobRecord,
        remote: RemoteBatchJob,
        now: datetime,
    ) -> None:
        status = (
            BatchStatus.RUNNING
            if remote.state not in {RemoteBatchState.QUEUED, RemoteBatchState.PENDING}
            else BatchStatus.SUBMITTED
        )
        self._upsert_batch_jobs(
            spark,
            (
                replace(
                    job,
                    google_job_name=remote.name,
                    status=status,
                    next_retry_at=now + self._poll_delay,
                    dt_submitted_at=job.dt_submitted_at or now,
                ),
            ),
        )

    @staticmethod
    def _authoritative_remote(
        matches: tuple[RemoteBatchJob, ...],
    ) -> RemoteBatchJob:
        def priority(remote: RemoteBatchJob) -> int:
            if remote.state in _REMOTE_SUCCESS_STATES:
                return 0
            if remote.state in _REMOTE_ACTIVE_STATES:
                return 1
            if remote.state in _REMOTE_RETRY_STATES:
                return 2
            return 3

        return min(matches, key=priority)

    def _cancel_duplicate_jobs(
        self,
        authoritative: RemoteBatchJob,
        matches: tuple[RemoteBatchJob, ...],
    ) -> None:
        for duplicate in matches:
            if duplicate.name == authoritative.name:
                continue
            if duplicate.state not in _REMOTE_ACTIVE_STATES:
                continue
            try:
                self._batch_client.cancel(duplicate.name)
            except Exception as error:  # noqa: BLE001 - cancellation is best-effort
                LOGGER.warning(
                    "stage=cancel_duplicate error_type=%s",
                    type(error).__name__,
                )

    def _poll_remote_job(
        self, spark: SparkSession, job: BatchJobRecord, now: datetime
    ) -> None:
        if not job.google_job_name:
            raise RuntimeError(
                f"{job.status.value} Batch job is missing google_job_name"
            )
        try:
            remote = self._batch_client.get(job.google_job_name)
        except GeminiQuotaExceeded:
            self._upsert_batch_jobs(
                spark,
                (replace(job, next_retry_at=now + self._quota_delay),),
            )
            return

        if remote.state is RemoteBatchState.UNSPECIFIED:
            raise RuntimeError("Gemini returned JOB_STATE_UNSPECIFIED")
        if remote.state in _REMOTE_ACTIVE_STATES:
            status = (
                BatchStatus.SUBMITTED
                if remote.state in {RemoteBatchState.QUEUED, RemoteBatchState.PENDING}
                else BatchStatus.RUNNING
            )
            self._upsert_batch_jobs(
                spark,
                (
                    replace(
                        job,
                        status=status,
                        next_retry_at=now + self._poll_delay,
                    ),
                ),
            )
            return
        if remote.state in _REMOTE_SUCCESS_STATES:
            self._complete_remote_job(spark, job, remote, now)
            return
        if remote.state in _REMOTE_RETRY_STATES:
            self._upsert_batch_jobs(
                spark,
                (
                    replace(
                        job,
                        status=BatchStatus.RETRY_WAIT,
                        next_retry_at=now + self._quota_delay,
                    ),
                ),
            )
            return
        raise RuntimeError(f"unsupported Gemini Batch state: {remote.state.value}")

    def _complete_remote_job(
        self,
        spark: SparkSession,
        job: BatchJobRecord,
        remote: RemoteBatchJob,
        now: datetime,
    ) -> None:
        manifest = parse_manifest(job.article_ids_json)
        current_rows = self._load_current_silver_rows(spark, manifest)
        gold_rows: list[dict[str, object]] = []
        seen_keys: set[str] = set()
        for result in remote.results:
            if result.request_key in seen_keys:
                continue
            seen_keys.add(result.request_key)
            if result.error_code is not None or result.response_text is None:
                continue
            silver_row = current_rows.get(result.request_key)
            if silver_row is None:
                continue
            analyzed = analyze_batch_response(
                result.response_text,
                silver_row,
                resolver=self._resolver,
                projector=self._projector,
                validator=self._validator,
                ont_version=self._ont_version,
                analyzed_at=now,
            )
            if analyzed is not None:
                gold_rows.append(analyzed)

        merge_gold_rows(spark, gold_rows, table=self._gold_table)
        self._upsert_batch_jobs(
            spark,
            (
                replace(
                    job,
                    status=BatchStatus.COMPLETED,
                    next_retry_at=None,
                    dt_completed_at=now,
                ),
            ),
        )

    def _prepare_retry_attempt(
        self, spark: SparkSession, job: BatchJobRecord, now: datetime
    ) -> None:
        retired = replace(
            job,
            status=BatchStatus.RETRIED,
            next_retry_at=None,
            dt_completed_at=now,
        )
        retry = BatchJobRecord(
            batch_key=batch_key(),
            google_job_name=None,
            ont_version=job.ont_version,
            article_ids_json=job.article_ids_json,
            status=BatchStatus.PREPARED,
            next_retry_at=None,
            dt_created_at=now,
            dt_submitted_at=None,
            dt_completed_at=None,
        )
        self._upsert_batch_jobs(spark, (retired, retry))


def process_gold_batch(
    trigger_df: DataFrame,
    batch_id: int,
    processor: Callable[[DataFrame, int], None],
) -> None:
    """Run one observable Silver-to-Gold scheduler tick."""
    LOGGER.info("micro-batch=%s started", batch_id)
    processor(trigger_df, batch_id)
    LOGGER.info("micro-batch=%s completed", batch_id)


def build_trigger_stream(spark: SparkSession) -> DataFrame:
    """Create a lightweight clock stream; Silver is a MERGE-written table."""
    return (
        spark.readStream.format("rate")
        .option("rowsPerSecond", "1")
        .option("numPartitions", "1")
        .load()
    )


def start_stream(spark: SparkSession, settings: Settings) -> StreamingQuery:
    """Validate platform tables, assemble adapters, and start the scheduler."""
    validate_gold_table(spark, table=settings.gold_table)
    validate_batch_job_table(spark, table=settings.batch_job_table)
    batch_client = GeminiBatchClient(
        api_key=settings.google_api_key.get_secret_value(),
        model=settings.semantic_llm_model,
    )
    processor = SilverToGoldBatchProcessor(
        batch_client=batch_client,
        resolver=DeterministicEntityResolver(),
        projector=project_to_rdf,
        validator=ShaclValidator(ROOT / "ontology"),
        ont_version=settings.ontology_version,
        batch_size=settings.semantic_batch_size,
        max_bytes=settings.semantic_batch_max_bytes,
        poll_seconds=settings.semantic_batch_poll_seconds,
        quota_pause_seconds=settings.semantic_quota_pause_seconds,
        silver_table=settings.silver_table,
        gold_table=settings.gold_table,
        batch_job_table=settings.batch_job_table,
    )
    trigger_stream = build_trigger_stream(spark)
    return (
        trigger_stream.writeStream.foreachBatch(
            lambda batch_df, batch_id: process_gold_batch(batch_df, batch_id, processor)
        )
        .option("checkpointLocation", settings.checkpoint_uri)
        .trigger(processingTime=settings.trigger_interval)
        .queryName(APP_NAME)
        .start()
    )
