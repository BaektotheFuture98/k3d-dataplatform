"""Bounded S3A streaming recovery probe; never touches article tables.

Run inside the Jupyter Pod: python3 - write|resume RUN_ID
Use the same unique RUN_ID across two separate processes. A successful resume
removes only its own platform-validation/spark-sync/RUN_ID directory.
"""
import re
import sys

from pyspark.sql import SparkSession

mode, run_id = sys.argv[1:]
if mode not in {"write", "resume"} or not re.fullmatch(r"[a-f0-9]{32}", run_id):
    raise ValueError("Expected write|resume and a unique 32-character hex run ID")

root = f"s3a://warehouse/platform-validation/spark-sync/{run_id}"
spark = SparkSession.builder.appName("spark-config-sync-smoke").getOrCreate()
spark.sparkContext.setLogLevel("WARN")
try:
    assert spark._jvm.org.apache.hadoop.util.VersionInfo.getVersion() == "3.4.2"
    loader = spark._jvm.java.lang.Thread.currentThread().getContextClassLoader()
    sdk = loader.loadClass("software.amazon.awssdk.services.s3.S3Client")
    print("AWS_SDK_SOURCE", sdk.getProtectionDomain().getCodeSource().getLocation().toString())
    fs = spark._jvm.org.apache.hadoop.fs.FileSystem.get(
        spark._jvm.java.net.URI(root), spark.sparkContext._jsc.hadoopConfiguration()
    )
    path = spark._jvm.org.apache.hadoop.fs.Path(root)
    if mode == "write" and fs.exists(path):
        raise RuntimeError("Probe path already exists; use a fresh run ID")
    if mode == "resume" and not fs.exists(path):
        raise RuntimeError("Missing previous probe checkpoint")

    query = (
        spark.readStream.format("rate-micro-batch")
        .option("rowsPerBatch", 3)
        .option("numPartitions", 1)
        .load()
        .writeStream.format("parquet")
        .option("path", root + "/output")
        .option("checkpointLocation", root + "/checkpoint")
        .trigger(availableNow=True)
        .start()
    )
    query.awaitTermination(90)
    if query.isActive:
        query.stop()
        raise TimeoutError("Bounded streaming probe timed out")
    expected = list(range(3 if mode == "write" else 6))
    actual = [r.value for r in spark.read.parquet(root + "/output").orderBy("value").collect()]
    assert actual == expected, (actual, expected)
    print("CHECKPOINT_" + mode.upper() + "_PASS", "rows=" + str(len(actual)))

    if mode == "resume":
        # Verify Iceberg S3FileIO still works alongside Hadoop S3A dependencies.
        table = "lakehouse.platform_smoke.sync_" + run_id
        spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.platform_smoke")
        spark.sql(f"CREATE TABLE {table} (id BIGINT) USING iceberg")
        try:
            spark.sql(f"INSERT INTO {table} VALUES (17)")
            assert spark.table(table).collect()[0].id == 17
            print("ICEBERG_WITH_S3A_PASS")
        finally:
            spark.sql(f"DROP TABLE {table} PURGE")
        assert fs.delete(path, True), "Probe cleanup failed"
        print("PROBE_CLEANUP_PASS")
finally:
    spark.stop()
