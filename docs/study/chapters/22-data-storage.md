# 22장. PostgreSQL·Garage·Iceberg의 저장 책임

## 왜 필요한가

모두 데이터를 다룬다고 같은 저장소는 아니다. 기사 테이블을 복원할 때 PostgreSQL만
백업하면 되는지 판단하려면 등록 정보와 실제 파일을 구분해야 한다.

## 어떻게 동작하는가

**관계형 DB**는 테이블·행·제약·트랜잭션 같은 기능으로 데이터를 관리한다.
**오브젝트 저장소**는 bucket 안의 key로 객체를 저장하고 API로 읽고 쓴다.
**테이블 포맷**은 데이터 파일과 메타데이터를 연결해 테이블로 관리하는 규칙이다.
**카탈로그**는 테이블 이름과 현재 메타데이터 위치 등을 찾고 관리하는 접점이다.

| 도구 | 이 프로젝트에서 맡은 일 | 실제 대상 |
| --- | --- | --- |
| PostgreSQL airflow_meta | Airflow 메타데이터 | DAG·태스크 실행 상태 등 |
| PostgreSQL iceberg_catalog | JDBC catalog 등록 정보 | 테이블 이름과 메타데이터 위치 등 |
| Garage | S3 호환 객체 저장 | 데이터 파일, Iceberg 메타데이터 파일 |
| Iceberg | 파일을 테이블로 관리하는 포맷 | snapshot·schema·manifest 등 |
| Iceberg REST 서버 | 클라이언트의 catalog API 제공 | PostgreSQL과 객체 저장소에 연결 |

```text
Spark → Iceberg REST catalog → PostgreSQL iceberg_catalog
Spark → Garage warehouse    → Parquet 등 데이터 파일과 Iceberg 메타데이터
```

Spark가 행 데이터를 전부 REST catalog를 경유해 전송하는 구조로 읽지 않는다.
catalog 조회와 파일 입출력은 다른 경로다. `s3://warehouse/`는 Mac 폴더가 아니라
bucket과 객체 경로를 표현하는 주소다. 여기서는 AWS 대신 Garage endpoint를 사용한다.

## 우리 프로젝트에서는

[Spark 설정](../../../configs/spark/spark-defaults.conf)은 catalog `lakehouse`를
`http://iceberg-rest:8181`에 연결하고 warehouse를 `s3://warehouse/`로 지정한다.
[Garage 설정](../../../configs/garage/garage.toml)과
[PostgreSQL 초기화](../../../deploy/k8s/manifests/postgres/initdb-configmap.yaml)를
각각 읽어 서비스와 DB 역할을 비교한다.

REST 서버는 [Iceberg test fixture 기반 이미지](../../../docker/iceberg-rest/Dockerfile)다.
현재의 개발용 구성을 인증·권한 분리·고가용성이 갖춰진 운영 catalog로 간주하지 않는다.
백업도 catalog 등록 정보와 실제 객체 파일의 일관성을 함께 고려해야 한다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform get service postgres garage iceberg-rest
kubectl --context k3d-dev -n finance-platform get statefulset postgres garage
```

각 포트는 PostgreSQL 5432, Garage S3 API 3900, REST catalog 8181이 선언돼 있다.
Service 조회만으로 실제 테이블 데이터가 존재한다고 말할 수는 없다.
기존 Jupyter Spark 세션이 있다면 아래 읽기 SQL로 등록된 namespace를 조회한다.

```python
spark.sql("SHOW NAMESPACES IN lakehouse").show()
```

이 코드는 이미 `spark` 세션이 준비된 노트북용이다. 결과는 현재 catalog의
namespace 목록이며 과거 기록과 다를 수 있다. 새 업무 테이블을 만들지는 않는다.

## 이해 확인

1. Airflow 메타데이터 DB에 기사 Parquet 파일도 저장되는가?
2. PostgreSQL만 복원하면 Garage에 있던 파일도 돌아오는가?

**해설:** 현재 행 데이터 파일은 Garage에 있다. DB 등록 정보와 객체 파일은 다른
저장소이므로 전체 복원에는 둘의 데이터와 일관성을 함께 검증해야 한다.

더 읽기: [Iceberg 신뢰성 개념](https://iceberg.apache.org/docs/latest/reliability/),
[Garage 문서](https://garagehq.deuxfleurs.fr/documentation/).

---

[전체 목차](../README.md) · [이전: 21장. DAG 배포·로그·동시성·대기](21-airflow-operations.md) · [다음: 23장. Jupyter·Spark·Neo4j의 실행 위치](23-data-processing.md)
