"""Iceberg persistence adapter for the platform-owned Gold article table."""

from __future__ import annotations

import re

from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

from ..application.contracts import SILVER_COLUMNS

SILVER_TABLE = "lakehouse.silver.article"
GOLD_TABLE = "lakehouse.gold.graph_article"
GOLD_VIEW = "incoming_graph_article"
GOLD_COLUMNS = (
    *SILVER_COLUMNS,
    "ont_version",
    "ont_analyzed_at",
    "ont_candidate_json",
)
GOLD_SCHEMA = StructType(
    [
        StructField("article_id", StringType(), nullable=False),
        StructField("au_url", StringType(), nullable=False),
        StructField("ar_title", StringType(), nullable=False),
        StructField("ar_content", StringType(), nullable=False),
        StructField("language", StringType(), nullable=True),
        StructField("dt_created_at", TimestampType(), nullable=False),
        StructField("dt_ingested_at", TimestampType(), nullable=False),
        StructField("ont_version", StringType(), nullable=False),
        StructField("ont_analyzed_at", TimestampType(), nullable=False),
        StructField("ont_candidate_json", StringType(), nullable=False),
    ]
)


def validate_gold_table(spark: SparkSession, *, table: str = GOLD_TABLE) -> None:
    """Fail fast when the existing Gold table violates its schema contract."""
    actual_schema = spark.table(table).schema
    actual_by_name = {field.name: field for field in actual_schema.fields}
    expected_names = {field.name for field in GOLD_SCHEMA.fields}
    problems: list[str] = []

    for expected in GOLD_SCHEMA.fields:
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
            expected_nullability = "nullable" if expected.nullable else "required"
            actual_nullability = "nullable" if actual.nullable else "required"
            problems.append(
                f"{expected.name}: expected {expected_nullability}, "
                f"found {actual_nullability}"
            )

    problems.extend(
        f"{field.name}: unexpected"
        for field in actual_schema.fields
        if field.name not in expected_names
    )

    ddl = "\n".join(
        str(row[0]) for row in spark.sql(f"SHOW CREATE TABLE {table}").collect()
    )
    compact_ddl = re.sub(r"[`\s]+", "", ddl.lower())
    if "usingiceberg" not in compact_ddl:
        problems.append("provider: expected iceberg")
    if "partitionedby(days(ont_analyzed_at))" not in compact_ddl:
        problems.append("partition: expected days(ont_analyzed_at)")

    if problems:
        raise RuntimeError("invalid Gold schema: " + "; ".join(problems))


def merge_gold_rows(spark: SparkSession, rows: list[dict[str, object]], *, table: str = GOLD_TABLE) -> None:
    """Insert unseen article/version pairs while retaining every older version."""
    if not rows:
        return
    spark.createDataFrame(rows, schema=GOLD_SCHEMA).createOrReplaceTempView(GOLD_VIEW)
    columns = ", ".join(GOLD_COLUMNS)
    source_columns = ", ".join(f"source.{column}" for column in GOLD_COLUMNS)
    spark.sql(
        f"""
        MERGE INTO {table} AS target
        USING {GOLD_VIEW} AS source
        ON target.article_id = source.article_id
           AND target.ont_version = source.ont_version
        WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({source_columns})
        """
    )
