"""Iceberg persistence for asynchronous ontology Batch job state."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from ..application.batch_models import (
    BatchJobRecord,
    BatchManifestItem,
    BatchStatus,
)
from ..application.contracts import SILVER_COLUMNS
from .gold_repository import GOLD_TABLE, SILVER_TABLE

BATCH_JOB_TABLE = "lakehouse.ops.ontology_batch_job"
BATCH_JOB_VIEW = "incoming_ontology_batch_job"
BATCH_JOB_COLUMNS = (
    "batch_key",
    "google_job_name",
    "ont_version",
    "article_ids_json",
    "status",
    "next_retry_at",
    "dt_created_at",
    "dt_submitted_at",
    "dt_completed_at",
)
BATCH_JOB_SCHEMA = StructType(
    [
        StructField("batch_key", StringType(), nullable=False),
        StructField("google_job_name", StringType(), nullable=True),
        StructField("ont_version", StringType(), nullable=False),
        StructField("article_ids_json", StringType(), nullable=False),
        StructField("status", StringType(), nullable=False),
        StructField("next_retry_at", TimestampType(), nullable=True),
        StructField("dt_created_at", TimestampType(), nullable=False),
        StructField("dt_submitted_at", TimestampType(), nullable=True),
        StructField("dt_completed_at", TimestampType(), nullable=True),
    ]
)
MANIFEST_SCHEMA = StructType(
    [
        StructField("request_key", StringType(), nullable=False),
        StructField("article_id", StringType(), nullable=False),
        StructField("dt_ingested_at", TimestampType(), nullable=False),
    ]
)
CLAIMING_STATUSES = (
    BatchStatus.PREPARED,
    BatchStatus.QUOTA_PAUSED,
    BatchStatus.SUBMITTED,
    BatchStatus.RUNNING,
    BatchStatus.RETRY_WAIT,
    BatchStatus.COMPLETED,
)
ACTIVE_STATUSES = tuple(
    status for status in CLAIMING_STATUSES if status is not BatchStatus.COMPLETED
)


def validate_batch_job_table(spark: SparkSession, *, table: str = BATCH_JOB_TABLE) -> None:
    """Fail fast unless the platform-owned ops table matches its contract."""
    actual_schema = spark.table(table).schema
    actual_by_name = {field.name: field for field in actual_schema.fields}
    expected_names = {field.name for field in BATCH_JOB_SCHEMA.fields}
    problems: list[str] = []

    for expected in BATCH_JOB_SCHEMA.fields:
        actual = actual_by_name.get(expected.name)
        if actual is None:
            problems.append(f"{expected.name}: missing")
            continue
        expected_type = expected.dataType.simpleString()
        actual_type = actual.dataType.simpleString()
        if actual_type != expected_type:
            problems.append(
                f"{expected.name}: expected {expected_type}, found {actual_type}"
            )
        if actual.nullable != expected.nullable:
            expected_value = "nullable" if expected.nullable else "required"
            actual_value = "nullable" if actual.nullable else "required"
            problems.append(
                f"{expected.name}: expected {expected_value}, found {actual_value}"
            )

    problems.extend(
        f"{field.name}: unexpected"
        for field in actual_schema.fields
        if field.name not in expected_names
    )

    ddl = "\n".join(
        str(row[0])
        for row in spark.sql(f"SHOW CREATE TABLE {table}").collect()
    )
    compact_ddl = re.sub(r"[`\s]+", "", ddl.lower())
    if "usingiceberg" not in compact_ddl:
        problems.append("provider: expected iceberg")
    if "partitionedby(days(dt_created_at))" not in compact_ddl:
        problems.append("partition: expected days(dt_created_at)")

    if problems:
        raise RuntimeError("invalid Batch job schema: " + "; ".join(problems))


def _job_from_mapping(row: Mapping[str, object]) -> BatchJobRecord:
    values = dict(row)
    return BatchJobRecord(
        batch_key=str(values["batch_key"]),
        google_job_name=(
            None
            if values["google_job_name"] is None
            else str(values["google_job_name"])
        ),
        ont_version=str(values["ont_version"]),
        article_ids_json=str(values["article_ids_json"]),
        status=BatchStatus(str(values["status"])),
        next_retry_at=values["next_retry_at"],  # type: ignore[arg-type]
        dt_created_at=values["dt_created_at"],  # type: ignore[arg-type]
        dt_submitted_at=values["dt_submitted_at"],  # type: ignore[arg-type]
        dt_completed_at=values["dt_completed_at"],  # type: ignore[arg-type]
    )


def select_current_job(spark: SparkSession, ont_version: str, *, table: str = BATCH_JOB_TABLE) -> BatchJobRecord | None:
    """Return the newest active attempt for an ontology version."""
    spark.catalog.refreshTable(table)
    rows = (
        spark.table(table)
        .where(F.col("ont_version") == F.lit(ont_version))
        .where(F.col("status").isin(*(status.value for status in ACTIVE_STATUSES)))
        .orderBy("dt_created_at", "batch_key", ascending=False)
        .limit(1)
        .collect()
    )
    if not rows:
        return None
    return _job_from_mapping(rows[0].asDict(recursive=True))


def select_unclaimed_silver_rows(
    spark: SparkSession,
    ont_version: str,
    limit: int,
    *, silver_table: str = SILVER_TABLE, gold_table: str = GOLD_TABLE, batch_job_table: str = BATCH_JOB_TABLE,
) -> DataFrame:
    """Select the oldest article versions not claimed by Gold or Batch state."""
    for table in (silver_table, gold_table, batch_job_table):
        spark.catalog.refreshTable(table)
    processed = (
        spark.table(gold_table)
        .where(F.col("ont_version") == F.lit(ont_version))
        .select("article_id")
        .dropDuplicates(["article_id"])
    )
    claimed = (
        spark.table(batch_job_table)
        .where(F.col("status").isin(*(status.value for status in CLAIMING_STATUSES)))
        .where(F.col("ont_version") == F.lit(ont_version))
        .selectExpr(
            "explode(from_json(article_ids_json, "
            "'array<struct<request_key:string,article_id:string,"
            "dt_ingested_at:timestamp>>')) AS manifest"
        )
        .select(
            F.col("manifest.article_id").alias("claimed_article_id"),
            F.col("manifest.dt_ingested_at").alias("claimed_dt_ingested_at"),
        )
        .dropDuplicates(["claimed_article_id", "claimed_dt_ingested_at"])
        .alias("claimed")
    )
    silver = spark.table(silver_table).select(*SILVER_COLUMNS).alias("silver")
    claim_match = (
        F.col("silver.article_id") == F.col("claimed.claimed_article_id")
    ) & (F.col("silver.dt_ingested_at") == F.col("claimed.claimed_dt_ingested_at"))
    return (
        silver.join(processed, on="article_id", how="left_anti")
        .join(claimed, on=claim_match, how="left_anti")
        .orderBy("dt_ingested_at", "article_id")
        .limit(limit)
    )


def load_current_silver_rows(
    spark: SparkSession,
    manifest: tuple[BatchManifestItem, ...],
    *, table: str = SILVER_TABLE,
) -> dict[str, Mapping[str, object]]:
    """Reload only Silver rows whose ingestion version still matches manifest."""
    if not manifest:
        return {}
    spark.catalog.refreshTable(table)
    manifest_rows = [
        (item.request_key, item.article_id, item.dt_ingested_at) for item in manifest
    ]
    manifest_frame = spark.createDataFrame(manifest_rows, schema=MANIFEST_SCHEMA).alias(
        "manifest"
    )
    silver = spark.table(table).select(*SILVER_COLUMNS).alias("silver")
    matches = silver.join(
        manifest_frame,
        on=(F.col("silver.article_id") == F.col("manifest.article_id"))
        & (F.col("silver.dt_ingested_at") == F.col("manifest.dt_ingested_at")),
        how="inner",
    ).select(
        F.col("manifest.request_key").alias("request_key"),
        *(F.col(f"silver.{column}").alias(column) for column in SILVER_COLUMNS),
    )
    result: dict[str, Mapping[str, object]] = {}
    for row in matches.collect():
        values = row.asDict(recursive=True)
        request_key = str(values.pop("request_key"))
        result[request_key] = values
    return result


def upsert_batch_jobs(
    spark: SparkSession,
    jobs: Sequence[BatchJobRecord],
    *, table: str = BATCH_JOB_TABLE,
) -> None:
    """Atomically insert or update one or more Batch attempts by batch key."""
    if not jobs:
        return
    rows = [
        (
            job.batch_key,
            job.google_job_name,
            job.ont_version,
            job.article_ids_json,
            job.status.value,
            job.next_retry_at,
            job.dt_created_at,
            job.dt_submitted_at,
            job.dt_completed_at,
        )
        for job in jobs
    ]
    spark.createDataFrame(rows, schema=BATCH_JOB_SCHEMA).createOrReplaceTempView(
        BATCH_JOB_VIEW
    )
    assignments = ",\n            ".join(
        f"target.{column} = source.{column}" for column in BATCH_JOB_COLUMNS[1:]
    )
    columns = ", ".join(BATCH_JOB_COLUMNS)
    source_columns = ", ".join(f"source.{column}" for column in BATCH_JOB_COLUMNS)
    spark.sql(
        f"""
        MERGE INTO {table} AS target
        USING {BATCH_JOB_VIEW} AS source
        ON target.batch_key = source.batch_key
        WHEN MATCHED THEN UPDATE SET
            {assignments}
        WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({source_columns})
        """
    )
