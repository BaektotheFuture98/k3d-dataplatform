CREATE TABLE IF NOT EXISTS lakehouse.gold.graph_article (
    article_id STRING NOT NULL COMMENT '기사 식별자',
    au_url STRING NOT NULL COMMENT '실제 기사 URL',
    ar_title STRING NOT NULL COMMENT '정규화된 기사 제목',
    ar_content STRING NOT NULL COMMENT '정규화된 기사 본문',
    language STRING COMMENT '정규화된 기사 언어 코드',
    dt_created_at TIMESTAMP NOT NULL COMMENT '기사 최초 생성 시각',
    dt_ingested_at TIMESTAMP NOT NULL COMMENT '기사 수집 시각',
    ont_version STRING NOT NULL COMMENT '적용한 온톨로지 분석 버전',
    ont_analyzed_at TIMESTAMP NOT NULL COMMENT '온톨로지 분석 완료 시각',
    ont_candidate_json STRING NOT NULL COMMENT '정규화·엔터티 해소·검증을 통과한 그래프 후보 JSON'
  )
  USING iceberg
  PARTITIONED BY (days(ont_analyzed_at))
  COMMENT '성공한 온톨로지 분석 결과를 보관하는 Gold 테이블'
  TBLPROPERTIES (
      'format-version' = '2',
      'write.format.default' = 'parquet',
      'write.parquet.compression-codec' = 'zstd'
  );
