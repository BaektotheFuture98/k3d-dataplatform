"""Spark-submit entrypoint for environment-configured ontology processing."""
import logging

from pipeline_runtime.lifecycle import stop_on_signal
from article_semantic.config import create_spark_session, load_settings
from article_semantic.infrastructure.gold_repository import validate_gold_table
from article_semantic.infrastructure.batch_job_repository import validate_batch_job_table
from article_semantic.stream import start_stream

LOGGER = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    spark = None
    try:
        settings = load_settings()
        spark = create_spark_session()
        spark.sparkContext.setLogLevel("WARN")
        if not spark.catalog.tableExists(settings.silver_table):
            raise RuntimeError("Required Silver table is missing")
        validate_gold_table(spark, table=settings.gold_table)
        validate_batch_job_table(spark, table=settings.batch_job_table)
        if settings.run_mode == "validate":
            print("SEMANTIC_PIPELINE_VALIDATED")
            return 0
        query = start_stream(spark, settings)
        with stop_on_signal(query):
            query.awaitTermination()
        return 0
    except Exception as error:
        LOGGER.error("stage=stream exception=%s", type(error).__name__)
        return 1
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
