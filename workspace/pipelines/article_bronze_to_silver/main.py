"""Stream valid Bronze articles into the latest-state Silver Iceberg table."""

from pyspark.sql import DataFrame, SparkSession

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_runtime.settings import BronzeSettings
from pipeline_runtime.lifecycle import stop_on_signal

from article_bronze_to_silver.transformations.clean import (
    filter_non_empty_normalized_article,
    filter_valid_article_quality,
    validate_metadata_json,
)
from article_bronze_to_silver.transformations.normalize import (
    add_canonical_url,
    add_article_identity,
    add_article_timestamps,
    add_record_hash,
    deduplicate_latest,
    normalize_article_fields,
    select_article_columns,
    select_silver_columns,
)

APP_NAME = "article-bronze-to-silver"
SILVER_TABLE = "lakehouse.silver.article"


def transform_batch(batch_df: DataFrame) -> DataFrame:
    """Apply the Silver transformation pipeline to one static micro-batch.

    Each helper has the Spark Transform Pattern contract:
    ``DataFrame -> DataFrame``.  Keeping the chain inside ``foreachBatch``
    allows the final ``row_number``-based deduplication to run on a static
    DataFrame, which Spark Structured Streaming supports.
    """
    return (
        batch_df.transform(select_article_columns)
        .transform(filter_valid_article_quality)
        .transform(validate_metadata_json)
        .transform(normalize_article_fields)
        .transform(add_canonical_url)
        .transform(filter_non_empty_normalized_article)
        .transform(add_article_identity)
        .transform(add_record_hash)
        .transform(add_article_timestamps)
        .transform(deduplicate_latest)
        .transform(select_silver_columns)
    )


def merge_into_silver(batch_df: DataFrame, batch_id: int, target_table: str = SILVER_TABLE) -> None:
    """Transform one Bronze micro-batch and merge its latest records into Silver."""
    print(f"[{APP_NAME}] micro-batch={batch_id} started")

    # Spark 4.x may wrap foreachBatch in a distinct SparkSession.  The temp
    # view and MERGE must therefore use the session attached to this batch.
    batch_spark = batch_df.sparkSession

    if batch_df.isEmpty():
        print(f"[{APP_NAME}] micro-batch={batch_id} source is empty")
        return

    updates_df = transform_batch(batch_df)
    updates_df.createOrReplaceTempView("article_silver_updates")

    batch_spark.sql(
        f"""
        MERGE INTO {target_table} AS target
        USING article_silver_updates AS source
        ON target.article_id = source.article_id

        WHEN MATCHED
        AND source.dt_ingested_at > target.dt_ingested_at
        THEN UPDATE SET
            target.au_url = source.au_url,
            target.ar_title = source.ar_title,
            target.ar_content = source.ar_content,
            target.language = source.language,
            target.dt_ingested_at = source.dt_ingested_at

        WHEN NOT MATCHED THEN INSERT (
            article_id,
            au_url,
            ar_title,
            ar_content,
            language,
            dt_created_at,
            dt_ingested_at
        ) VALUES (
            source.article_id,
            source.au_url,
            source.ar_title,
            source.ar_content,
            source.language,
            source.dt_created_at,
            source.dt_ingested_at
        )
        """
    )

    print(f"[{APP_NAME}] micro-batch={batch_id} completed")


def build_bronze_stream(spark: SparkSession, settings: BronzeSettings | None = None) -> DataFrame:
    """Create the Iceberg Structured Streaming source."""
    settings = settings or BronzeSettings()
    return (
        spark.readStream.format("iceberg")
        .option(
            "streaming-max-files-per-micro-batch",
            str(settings.max_files_per_micro_batch),
        )
        .load(settings.bronze_table)
    )


def start_stream(spark: SparkSession, settings: BronzeSettings | None = None):
    settings = settings or BronzeSettings()
    stream = build_bronze_stream(spark, settings)
    writer = (
        stream.writeStream.foreachBatch(
            lambda frame, batch_id: merge_into_silver(frame, batch_id, settings.silver_table)
        )
        .option("checkpointLocation", settings.checkpoint_uri)
        .queryName(APP_NAME)
    )
    if settings.run_mode == "available_now":
        return writer.trigger(availableNow=True).start()
    return writer.trigger(processingTime=settings.trigger_interval).start()


def main() -> int:
    spark = None
    try:
        settings = BronzeSettings()
        spark = SparkSession.builder.appName(APP_NAME).getOrCreate()
        spark.sparkContext.setLogLevel("WARN")
        for table in (settings.bronze_table, settings.silver_table):
            if not spark.catalog.tableExists(table):
                raise RuntimeError("Required article table is missing")
        if settings.run_mode == "validate":
            print("BRONZE_PIPELINE_VALIDATED")
            return 0
        query = start_stream(spark, settings)
        with stop_on_signal(query):
            query.awaitTermination()
        return 0
    except Exception as error:
        # Avoid arbitrary exception text containing input or credentials.
        print(f"[{APP_NAME}] failed exception={type(error).__name__}", file=sys.stderr)
        return 1
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
