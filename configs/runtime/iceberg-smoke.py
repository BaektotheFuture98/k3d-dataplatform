"""Synthetic infrastructure smoke; run via stdin inside the Jupyter Pod.

Creates an isolated namespace/table, verifies committed writes from another
Spark session invocation, and purges only that owned smoke table on success.
No article pipelines or business datasets are created.
"""
import sys
from pyspark.sql import SparkSession

mode = sys.argv[1]
spark = SparkSession.builder.appName("infrastructure-iceberg-smoke").getOrCreate()
table = "lakehouse.platform_smoke.catalog_roundtrip"
try:
    if mode == "write":
        spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.platform_smoke")
        spark.sql(f"CREATE TABLE IF NOT EXISTS {table} (id BIGINT, message STRING) USING iceberg")
        spark.sql(f"INSERT OVERWRITE {table} SELECT 17L, 'infrastructure-only'")
        assert spark.table(table).collect()[0].id == 17
        print("SMOKE_WRITE_PASS")
    elif mode == "read":
        rows = spark.table(table).collect()
        assert len(rows) == 1 and rows[0].id == 17
        assert rows[0].message == "infrastructure-only"
        spark.sql(f"DROP TABLE {table} PURGE")
        print("SMOKE_READ_AND_CLEANUP_PASS")
    else:
        raise ValueError("mode must be write or read")
finally:
    spark.stop()
