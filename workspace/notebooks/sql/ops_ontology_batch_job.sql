CREATE TABLE IF NOT EXISTS lakehouse.ops.ontology_batch_job (
    batch_key       STRING    NOT NULL COMMENT '비동기 분석 배치 식별 키',
    google_job_name STRING             COMMENT '외부 Batch 작업 이름',
    ont_version     STRING    NOT NULL COMMENT '적용한 온톨로지 버전',
    article_ids_json STRING   NOT NULL COMMENT '배치에 포함된 기사 manifest JSON',
    status          STRING    NOT NULL COMMENT '배치 처리 상태',
    next_retry_at   TIMESTAMP          COMMENT '다음 재시도 가능 시각',
    dt_created_at   TIMESTAMP NOT NULL COMMENT '배치 상태 생성 시각',
    dt_submitted_at TIMESTAMP          COMMENT '외부 Batch 제출 시각',
    dt_completed_at TIMESTAMP          COMMENT '배치 완료 시각'
)
USING iceberg
PARTITIONED BY (days(dt_created_at))
COMMENT 'Silver-to-Gold 비동기 온톨로지 분석 작업 상태'
TBLPROPERTIES (
    'format-version' = '2',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd'
);
