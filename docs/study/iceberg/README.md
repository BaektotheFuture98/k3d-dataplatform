# Iceberg: 파일을 테이블로 관리하는 계층

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [22장](../chapters/22-data-storage.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

## 학습 목표

Iceberg 테이블 포맷, REST catalog, 파일 저장소를 하나의 DB로 혼동하지 않는다.

## 현재 데이터의 위치

```text
Spark
  → Iceberg REST Catalog: 테이블 이름과 메타데이터 위치 조회
      → PostgreSQL iceberg_catalog: JDBC catalog의 등록 정보
  → Garage warehouse: 데이터 파일과 Iceberg 메타데이터 JSON
```

Iceberg **1.11.0**은 테이블 포맷이다. `iceberg-rest:8181`은 이름·metadata 위치
등을 관리하는 REST catalog 서버다. 실제 행 데이터 파일을 REST 서버의 Pod에
전부 저장하는 방식이 아니다.

## 현재 구현의 중요한 한계

이 프로젝트는 Apache Iceberg의 REST **test fixture**를 이미지로 빌드해 사용한다.
인증·TLS·권한 분리·고가용성을 갖춘 운영 catalog 제품으로 간주하지 않는다.
신뢰하는 개발 클러스터 내부 용도이며 외부 공개 대상으로 만들지 않는다.
해당 fixture의 catalog 속성 로거는 인증값 노출을 막기 위해 OFF로 유지했다.

| 항목 | 현재 설정 |
| --- | --- |
| 버전 | Iceberg 1.11.0, PostgreSQL JDBC 42.7.8 |
| REST Service | iceberg-rest:8181 |
| catalog DB | PostgreSQL iceberg_catalog |
| warehouse | s3://warehouse/ |
| S3 endpoint | http://garage:3900, path-style |
| 자원 request / limit | 100m·256Mi / CPU 1·1Gi |

## 파일과 설정 위치

서버 이미지는 `docker/iceberg-rest/Dockerfile`, 배포는
`deploy/k8s/manifests/iceberg-rest/`, Spark 연결은
`configs/spark/spark-defaults.conf`다. JDBC/S3 인증값은 Secret에서 주입한다.

Spark 쪽 핵심 설정은 다음과 같다.

```text
spark.sql.defaultCatalog lakehouse
spark.sql.catalog.lakehouse org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.lakehouse.type rest
spark.sql.catalog.lakehouse.uri http://iceberg-rest:8181
spark.sql.catalog.lakehouse.warehouse s3://warehouse/
```

위는 일부 항목이다. 실제 설정에는 Iceberg extension, S3FileIO, endpoint,
region, path-style과 인증 provider가 함께 필요하다.

## 조회 실습

Jupyter의 기존 Spark 세션에서 읽기 전용 SQL로 구조를 살핀다.

```python
spark.sql("SHOW NAMESPACES IN lakehouse").show()
spark.sql("SHOW TABLES IN lakehouse.bronze").show()
```

과거 생성된 Article 테이블은 bronze.article, silver.article,
gold.graph_article, ops.ontology_batch_job이다. 과거 0행 검증 기록이
현재 행 수를 보장하지 않으므로 실제 수량은 필요한 시점에 별도 조회한다.

## 확인 문제

1. REST catalog Pod를 재시작해도 테이블 등록이 유지될 수 있는 이유는?
2. PostgreSQL 등록 정보만 백업하면 전체 Iceberg 데이터가 복구되는가?

**해설:** catalog 상태를 외부 DB와 파일 저장소에 둔다. 전체 복구에는 실제
객체 파일·메타데이터와 catalog 등록 정보의 일관성도 필요하다.

참고: [Iceberg 문서](https://iceberg.apache.org/docs/latest/),
[고정 REST fixture 소스](https://github.com/apache/iceberg/tree/apache-iceberg-1.11.0/open-api/src/testFixtures).
