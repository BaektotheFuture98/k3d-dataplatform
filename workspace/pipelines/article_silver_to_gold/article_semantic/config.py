"""Environment-only settings; ontology assets ship inside the application."""
from pathlib import Path
from pipeline_runtime.settings import SemanticSettings

ROOT = Path(__file__).resolve().parents[1]
Settings = SemanticSettings


def load_settings() -> Settings:
    return Settings()


def create_spark_session():
    from pyspark.sql import SparkSession
    return SparkSession.builder.appName("article-silver-to-gold").getOrCreate()
