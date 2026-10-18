"""Validated environment settings; credentials never come from image files."""
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", env_file=None, populate_by_name=True, hide_input_in_errors=True
    )
    silver_table: str = Field(default="lakehouse.silver.article", validation_alias="SILVER_TABLE")
    trigger_interval: str = Field(default="1 minute", validation_alias="TRIGGER_INTERVAL")
    run_mode: Literal["stream", "available_now", "validate"] = Field(
        default="stream", validation_alias="PIPELINE_RUN_MODE"
    )

    @field_validator("bronze_table", "silver_table", "gold_table", "batch_job_table", check_fields=False)
    @classmethod
    def qualified_table(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*\.[A-Za-z_]\w*", value):
            raise ValueError("expected catalog.namespace.table identifier")
        return value

    @field_validator("checkpoint_uri", check_fields=False)
    @classmethod
    def s3a_checkpoint(cls, value: str) -> str:
        uri = urlsplit(value)
        if (uri.scheme != "s3a" or not uri.netloc or uri.path in {"", "/"}
                or uri.query or uri.fragment or re.search(r"\s", value)
                or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", uri.netloc)):
            raise ValueError("expected s3a://bucket/unique-checkpoint-prefix")
        return value.rstrip("/")

    @field_validator("trigger_interval")
    @classmethod
    def processing_interval(cls, value: str) -> str:
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(ms|milliseconds?|s|seconds?|m|minutes?|h|hours?)", value)
        if not match or float(match.group(1)) <= 0:
            raise ValueError("expected a positive Spark processing interval")
        return value


class BronzeSettings(PipelineSettings):
    bronze_table: str = Field(default="lakehouse.bronze.article", validation_alias="BRONZE_TABLE")
    checkpoint_uri: str = Field(
        default="s3a://warehouse/checkpoints/article-bronze-to-silver-v2", validation_alias="CHECKPOINT_URI"
    )
    max_files_per_micro_batch: int = Field(default=100, ge=1, validation_alias="MAX_FILES_PER_MICRO_BATCH")


class SemanticSettings(PipelineSettings):
    run_mode: Literal["stream", "validate"] = Field(default="stream", validation_alias="PIPELINE_RUN_MODE")
    gold_table: str = Field(default="lakehouse.gold.graph_article", validation_alias="GOLD_TABLE")
    batch_job_table: str = Field(default="lakehouse.ops.ontology_batch_job", validation_alias="BATCH_JOB_TABLE")
    checkpoint_uri: str = Field(
        default="s3a://warehouse/checkpoints/article-silver-to-gold", validation_alias="CHECKPOINT_URI"
    )
    google_api_key: SecretStr = Field(validation_alias="GOOGLE_API_KEY", repr=False)
    semantic_llm_model: str = Field(min_length=1, validation_alias="SEMANTIC_LLM_MODEL")
    ontology_version: str = Field(min_length=1, validation_alias="ONT_VERSION")
    semantic_batch_size: int = Field(default=100, ge=1, le=100, validation_alias="SEMANTIC_BATCH_SIZE")
    semantic_batch_max_bytes: int = Field(default=18_874_368, ge=1, le=20_000_000, validation_alias="SEMANTIC_BATCH_MAX_BYTES")
    semantic_batch_poll_seconds: int = Field(default=300, ge=1, validation_alias="SEMANTIC_BATCH_POLL_SECONDS")
    semantic_quota_pause_seconds: int = Field(default=3600, ge=1, validation_alias="SEMANTIC_QUOTA_PAUSE_SECONDS")

    @field_validator("google_api_key", "semantic_llm_model", "ontology_version", mode="before")
    @classmethod
    def nonblank(cls, value):
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                raise ValueError("required setting must not be blank")
        return raw
