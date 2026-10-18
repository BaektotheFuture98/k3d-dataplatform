import hashlib
import unittest
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from article_bronze_to_silver.main import transform_batch


SOURCE_SCHEMA = StructType(
    [
        StructField("ingest_key", StringType(), nullable=True),
        StructField("job_id", StringType(), nullable=True),
        StructField("start_url", StringType(), nullable=True),
        StructField("source_url", StringType(), nullable=True),
        StructField("canonical_url", StringType(), nullable=True),
        StructField("ar_title", StringType(), nullable=True),
        StructField("ar_content", StringType(), nullable=True),
        StructField("metadata_json", StringType(), nullable=True),
        StructField("meta_description", StringType(), nullable=True),
        StructField("language", StringType(), nullable=True),
        StructField("http_status_code", IntegerType(), nullable=True),
        StructField("collected_at", TimestampType(), nullable=True),
        StructField("ingested_at", TimestampType(), nullable=True),
        StructField("ar_published_at", TimestampType(), nullable=True),
    ]
)


def article_row(
    ingest_key,
    job_id,
    source_url,
    canonical_url,
    title,
    content,
    collected_at,
    ingested_at,
    published_at,
    *,
    metadata_json="{}",
    language="ko",
    http_status_code=200,
    meta_description=None,
):
    return (
        ingest_key,
        job_id,
        "https://example.com/start",
        source_url,
        canonical_url,
        title,
        content,
        metadata_json,
        meta_description,
        language,
        http_status_code,
        collected_at,
        ingested_at,
        published_at,
    )


class ArticleTransformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (
            SparkSession.builder
            .master("local[2]")
            .appName("article-transform-tests")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def make_df(self, rows):
        return self.spark.createDataFrame(rows, schema=SOURCE_SCHEMA)

    def test_transform_builds_new_silver_contract_and_stable_article_id(self):
        canonical_url = "https://example.com/article-1"
        published_at = datetime(2026, 1, 1, 0, 0, 0)
        ingested_at = datetime(2026, 1, 2, 0, 1, 0)
        source_df = self.make_df(
            [
                article_row(
                    "ingest-1",
                    "job-1",
                    " https://example.com/article-1?utm_source=test ",
                    f"  {canonical_url}  ",
                    "  Hello   world\n",
                    "First\r\n\r\n\r\nSecond\t  line",
                    datetime(2026, 1, 2, 0, 0, 0),
                    ingested_at,
                    published_at,
                    meta_description=" description ",
                    language=" EN ",
                )
            ]
        )

        result = transform_batch(source_df).collect()

        self.assertEqual(len(result), 1)
        row = result[0]
        expected_id = "AR" + hashlib.sha256(canonical_url.encode()).hexdigest()[:16].upper()
        self.assertEqual(
            set(row.asDict()),
            {
                "article_id",
                "au_url",
                "ar_title",
                "ar_content",
                "language",
                "dt_created_at",
                "dt_ingested_at",
            },
        )
        self.assertEqual(row.article_id, expected_id)
        self.assertEqual(len(row.article_id), 18)
        self.assertEqual(row.au_url, canonical_url)
        self.assertEqual(row.ar_title, "Hello world")
        self.assertEqual(row.ar_content, "First\n\nSecond line")
        self.assertEqual(row.language, "en")
        self.assertEqual(row.dt_created_at, published_at)
        self.assertEqual(row.dt_ingested_at, ingested_at)

    def test_transform_upserts_same_canonical_url_from_different_source_urls_as_one_row(self):
        canonical_url = "https://example.com/article-2"
        source_df = self.make_df(
            [
                article_row(
                    "ingest-old",
                    "job-old",
                    "https://example.com/article-2?utm_source=old",
                    canonical_url,
                    "Old title",
                    "old body",
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2025, 12, 1, 0, 0, 0),
                ),
                article_row(
                    "ingest-new",
                    "job-new",
                    "https://m.example.com/article-2",
                    canonical_url,
                    "New title",
                    "new body",
                    datetime(2026, 1, 2, 0, 0, 0),
                    datetime(2026, 1, 2, 0, 0, 0),
                    datetime(2025, 12, 1, 0, 0, 0),
                ),
            ]
        )

        result = transform_batch(source_df).collect()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].article_id, "AR" + hashlib.sha256(canonical_url.encode()).hexdigest()[:16].upper())
        self.assertEqual(result[0].au_url, canonical_url)
        self.assertEqual(result[0].ar_title, "New title")
        self.assertEqual(result[0].ar_content, "new body")

    def test_transform_uses_trimmed_source_url_when_canonical_url_is_blank(self):
        source_url = "https://example.com/article-3"
        source_df = self.make_df(
            [
                article_row(
                    "ingest-3",
                    "job-3",
                    f"  {source_url}  ",
                    " \t ",
                    "Valid title",
                    "Valid content",
                    datetime(2026, 1, 3, 0, 0, 0),
                    datetime(2026, 1, 3, 0, 0, 0),
                    datetime(2026, 1, 3, 0, 0, 0),
                )
            ]
        )

        result = transform_batch(source_df).collect()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].au_url, source_url)
        self.assertEqual(
            result[0].article_id,
            "AR" + hashlib.sha256(source_url.encode()).hexdigest()[:16].upper(),
        )

    def test_transform_rejects_invalid_status_json_blank_fields_and_missing_published_at(self):
        source_df = self.make_df(
            [
                article_row(
                    "valid",
                    "job-valid",
                    "https://example.com/valid",
                    None,
                    "Valid title",
                    "Valid content",
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                ),
                article_row(
                    "invalid-status",
                    "job-status",
                    "https://example.com/invalid-status",
                    None,
                    "Ignored",
                    "body",
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    http_status_code=404,
                ),
                article_row(
                    "invalid-json",
                    "job-json",
                    "https://example.com/invalid-json",
                    None,
                    "Ignored",
                    "body",
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    metadata_json="{not-json}",
                ),
                article_row(
                    "blank-title",
                    "job-title",
                    "https://example.com/blank-title",
                    None,
                    " \t ",
                    "body",
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                ),
                article_row(
                    "missing-published",
                    "job-published",
                    "https://example.com/missing-published",
                    None,
                    "Ignored",
                    "body",
                    datetime(2026, 1, 1, 0, 0, 0),
                    datetime(2026, 1, 1, 0, 0, 0),
                    None,
                ),
            ]
        )

        result = transform_batch(source_df).collect()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].au_url, "https://example.com/valid")


if __name__ == "__main__":
    unittest.main()
