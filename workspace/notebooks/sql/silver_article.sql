CREATE TABLE IF NOT EXISTS lakehouse.silver.article (
    article_id     STRING    NOT NULL COMMENT 'canonical URL 해시 기반 기사 ID',
    au_url         STRING    NOT NULL COMMENT '정규화된 기사 URL',
    ar_title       STRING    NOT NULL COMMENT '정규화된 기사 제목',
    ar_content     STRING    NOT NULL COMMENT '정규화된 기사 본문',
    language       STRING             COMMENT '정규화된 기사 언어 코드',
    dt_created_at  TIMESTAMP NOT NULL COMMENT '기사 작성 또는 발행 시각',
    dt_ingested_at TIMESTAMP NOT NULL COMMENT 'Bronze 적재 시각'
)
USING iceberg
PARTITIONED BY (
    bucket(32, article_id),
    days(dt_created_at)
)
COMMENT 'article_id별 최신 정상 기사를 제공하는 Silver 테이블'
TBLPROPERTIES (
    'format-version' = '2',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.merge.mode' = 'copy-on-write',
    'write.distribution-mode' = 'hash'
);
