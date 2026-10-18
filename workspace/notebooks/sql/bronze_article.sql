CREATE TABLE IF NOT EXISTS lakehouse.bronze.article (
    ingest_key       STRING    NOT NULL COMMENT '수집 작업 내 중복 판별 키',
    job_id           STRING    NOT NULL COMMENT '기사 수집 작업 ID',
    start_url        STRING    NOT NULL COMMENT '크롤링 시작 URL',
    source_url       STRING    NOT NULL COMMENT '수집한 기사 URL',
    canonical_url    STRING             COMMENT '정규화에 사용할 canonical URL',
    ar_title         STRING    NOT NULL COMMENT '수집한 기사 제목',
    ar_content       STRING    NOT NULL COMMENT '수집한 기사 본문',
    metadata_json    STRING    NOT NULL COMMENT '가변 기사 메타데이터 JSON',
    meta_description STRING             COMMENT 'HTML meta description',
    language         STRING             COMMENT '기사 언어 코드',
    http_status_code INT                COMMENT '수집 시점의 HTTP 상태 코드',
    collected_at     TIMESTAMP NOT NULL COMMENT '기사 수집 시각',
    ingested_at      TIMESTAMP NOT NULL COMMENT 'Bronze 적재 시각',
    ar_published_at  TIMESTAMP          COMMENT '기사 작성 또는 발행 시각'
)
USING iceberg
PARTITIONED BY (days(collected_at))
COMMENT '기사 수집 원본과 이력을 보존하는 Bronze 테이블'
TBLPROPERTIES (
    'format-version' = '2',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd'
);
