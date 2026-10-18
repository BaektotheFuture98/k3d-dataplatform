"""Article field normalization and Silver-contract projection."""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from article_bronze_to_silver.transformations.clean import (
    has_non_whitespace,
    trim_outer_whitespace,
)


BRONZE_ARTICLE_COLUMNS = (
    "ingest_key",
    "job_id",
    "start_url",
    "source_url",
    "canonical_url",
    "ar_title",
    "ar_content",
    "metadata_json",
    "meta_description",
    "language",
    "http_status_code",
    "collected_at",
    "ingested_at",
    "ar_published_at",
)

SILVER_ARTICLE_COLUMNS = (
    "article_id",
    "au_url",
    "ar_title",
    "ar_content",
    "language",
    "dt_created_at",
    "dt_ingested_at",
)


def select_article_columns(df: DataFrame) -> DataFrame:
    """Select the Bronze columns supported by this pipeline."""
    return df.select(*BRONZE_ARTICLE_COLUMNS)


def normalize_title(column):
    """Trim a title and collapse all whitespace runs to one space."""
    return trim_outer_whitespace(F.regexp_replace(column, r"\s+", " "))


def normalize_content(column):
    """Normalize article body whitespace while preserving paragraph breaks."""
    normalized = F.regexp_replace(column, r"\r\n?", "\n")
    normalized = F.regexp_replace(normalized, r"[ \t]+", " ")
    normalized = F.regexp_replace(normalized, r"\n{3,}", "\n\n")
    return trim_outer_whitespace(normalized)


def normalize_article_fields(df: DataFrame) -> DataFrame:
    """Normalize identifiers, URLs, article text, and optional metadata fields."""
    return (
        df.withColumn("ingest_key", trim_outer_whitespace(F.col("ingest_key")))
        .withColumn("job_id", trim_outer_whitespace(F.col("job_id")))
        .withColumn("start_url", trim_outer_whitespace(F.col("start_url")))
        .withColumn("source_url", trim_outer_whitespace(F.col("source_url")))
        .withColumn("ar_title", normalize_title(F.col("ar_title")))
        .withColumn("ar_content", normalize_content(F.col("ar_content")))
        .withColumn(
            "language",
            F.when(
                F.col("language").isNotNull(),
                F.lower(trim_outer_whitespace(F.col("language"))),
            ),
        )
        .withColumn(
            "meta_description",
            F.when(
                F.col("meta_description").isNotNull(),
                trim_outer_whitespace(F.col("meta_description")),
            ),
        )
    )


def add_canonical_url(df: DataFrame) -> DataFrame:
    """Use source_url when canonical_url is absent or all whitespace."""
    return df.withColumn(
        "canonical_url",
        F.when(
            F.col("canonical_url").isNotNull()
            & has_non_whitespace(F.col("canonical_url")),
            trim_outer_whitespace(F.col("canonical_url")),
        ).otherwise(F.col("source_url")),
    )


def add_article_identity(df: DataFrame) -> DataFrame:
    """Create one stable article identity URL and ID for the Silver table."""
    return (
        df.withColumn("au_url", F.col("canonical_url"))
        .withColumn(
            "article_id",
            F.concat(
                F.lit("AR"),
                F.upper(F.substring(F.sha2(F.col("au_url"), 256), 1, 16)),
            ),
        )
    )


def add_article_timestamps(df: DataFrame) -> DataFrame:
    """Map Bronze article and ingestion timestamps to the Silver contract."""
    return df.withColumn("dt_created_at", F.col("ar_published_at").cast("timestamp")).withColumn(
        "dt_ingested_at", F.col("ingested_at").cast("timestamp")
    )


def add_record_hash(df: DataFrame) -> DataFrame:
    """Add a SHA-256 hash derived from normalized article content fields."""
    record_struct = F.struct(
        F.col("canonical_url"),
        F.col("ar_title"),
        F.col("ar_content"),
        F.col("metadata_json"),
        F.col("meta_description"),
        F.col("language"),
        F.col("http_status_code"),
    )
    return df.withColumn("record_hash", F.sha2(F.to_json(record_struct), 256))


def deduplicate_latest(df: DataFrame) -> DataFrame:
    """Keep the latest record for each article_id in one batch."""
    latest_window = Window.partitionBy("article_id").orderBy(
        F.col("collected_at").desc(),
        F.col("ingested_at").desc(),
        F.col("record_hash").desc(),
    )

    return (
        df.withColumn("_row_number", F.row_number().over(latest_window))
        .filter(F.col("_row_number") == 1)
        .drop("_row_number")
    )


def select_silver_columns(df: DataFrame) -> DataFrame:
    """Return columns in the order expected by the Silver table DDL."""
    return df.select(*SILVER_ARTICLE_COLUMNS)
