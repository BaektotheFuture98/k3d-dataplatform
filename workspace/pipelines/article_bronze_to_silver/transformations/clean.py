"""Quality filters and whitespace cleanup for Bronze article records."""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def trim_outer_whitespace(column):
    """Remove leading and trailing spaces, tabs, and line breaks."""
    return F.regexp_replace(column, r"(?s)^\s+|\s+$", "")


def has_non_whitespace(column):
    """Return true when a string contains at least one non-whitespace character."""
    return F.length(F.regexp_replace(column, r"\s+", "")) > 0


def filter_valid_article_quality(df: DataFrame) -> DataFrame:
    """Keep successful records with required, non-blank fields."""
    required_columns = (
        "ingest_key",
        "job_id",
        "start_url",
        "source_url",
        "ar_title",
        "ar_content",
        "metadata_json",
    )
    required_timestamps = ("collected_at", "ingested_at", "ar_published_at")

    filtered_df = df.filter(F.col("http_status_code") == 200)

    for column_name in required_columns:
        filtered_df = filtered_df.filter(F.col(column_name).isNotNull())
        filtered_df = filtered_df.filter(has_non_whitespace(F.col(column_name)))

    for column_name in required_timestamps:
        filtered_df = filtered_df.filter(F.col(column_name).isNotNull())

    return filtered_df


def validate_metadata_json(df: DataFrame) -> DataFrame:
    """Keep rows whose metadata_json is syntactically valid JSON."""
    return (
        df.withColumn(
            "_metadata_json_valid",
            F.get_json_object(F.col("metadata_json"), "$"),
        )
        .filter(F.col("_metadata_json_valid").isNotNull())
        .drop("_metadata_json_valid")
    )


def filter_non_empty_normalized_article(df: DataFrame) -> DataFrame:
    """Reject articles whose title or content is blank after normalization."""
    return df.filter(has_non_whitespace(F.col("ar_title"))).filter(
        has_non_whitespace(F.col("ar_content"))
    )
