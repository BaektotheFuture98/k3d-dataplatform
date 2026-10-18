# k3d-dataplatform

기사 데이터를 수집·정제하고 Neo4j 그래프로 제공하기 위한 로컬 데이터 플랫폼이다.
Mac의 Colima 위에서 k3d 단일 노드 클러스터를 사용한다.

**현재는 기반 서비스가 실행 중이며, 실제 기사 처리 파이프라인은 연결하지 않았다.**
아래 상태는 2026-10-18 확인 기준이다. 실제 실행 명령과 검증 결과는
[인프라 실행 기록](configs/runtime/VALIDATION.md)에 정리했다.

## 현재 구축 상태

| 구성 | 버전 | 역할 | 상태 |
| --- | --- | --- | --- |
| PostgreSQL | 17.11 | Airflow 메타데이터와 Iceberg 카탈로그 DB | Ready |
| Garage | 2.4.1 | S3 호환 객체 저장소, `warehouse` 버킷 | Ready |
| Iceberg REST | 1.11.0 | PostgreSQL JDBC 기반 카탈로그 API | Ready |
| Spark / JupyterLab | 4.1.2 / 4.4.9 | 데이터 처리와 노트북 개발 | Jupyter Ready, Spark Local 실행 검증 |
| Airflow | 3.0.2, chart 1.18.0 | 작업 스케줄링과 오케스트레이션 | API·Scheduler·DAG Processor Ready, DAG 0개 |
| Neo4j Community | 5.26.32 | 기사·이벤트 그래프 저장 | Ready, 인증·합성 데이터 쿼리 검증 |
| Strimzi / Kafka | 0.51.0 / 4.2.0 예정 | 이벤트 브로커 관리와 메시지 전달 | 미설치, 클러스터 리소스 승인 대기 |
| Kafka Connect | Kafka 4.2.0, Neo4j 플러그인 5.1.16 예정 | Kafka 이벤트를 Neo4j에 반영 | 이미지 빌드·k3d 반입 완료, 미기동 |

상시 실행 Pod는 총 8개이며 모두 Ready다. 과거 검증 Job의 Completed/Error Pod는
실행 중인 서비스와 별개이며 TTL 정리 대상이다.
MinIO는 Garage로 대체했다. 저장소에 남아 있는 MinIO manifest는 현재 사용하지 않는다.

## 아키텍처

현재 연결하고 검증한 기반 서비스의 관계는 다음과 같다.

```text
Airflow ───────────────────────────→ PostgreSQL / airflow_meta

Jupyter / Spark Local ──→ Iceberg REST ──→ PostgreSQL / iceberg_catalog
         │                     │
         └─────────────────────┴───────→ Garage / warehouse

Neo4j: 독립 실행 중, 기사 데이터 적재는 아직 연결하지 않음
```

Iceberg는 테이블 포맷이다. 데이터 파일과 Iceberg 메타데이터 JSON은 Garage에 저장하고,
테이블의 메타데이터 위치 등 JDBC 카탈로그 정보는 PostgreSQL에 저장한다.
Spark는 Jupyter 환경에서 `local[2]`로 실행하며, 별도 Spark 클러스터는 구성하지 않았다.
Airflow는 LocalExecutor를 사용한다.

목표 업무 흐름은 다음과 같다. **아래 파이프라인은 아직 동작하지 않는다.**

```text
Airflow → Article Collector Job → Iceberg Bronze
  → Spark Bronze→Silver → Iceberg Silver
  → Spark Silver→Gold → Iceberg Gold
  → Gold Publisher → Kafka article-gold → Kafka Connect → Neo4j → Service API
```

기사 수집·변환·발행 코드와 Service API는 미구현이다.
수집 DAG와 Job 템플릿 등 일부 설정 파일은 준비되어 있으나 클러스터에 배포하지 않았다.

## 실행 환경과 저장소

| 항목 | 구성 |
| --- | --- |
| 실행 기반 | Mac → Colima → k3d |
| 클러스터 / kubectl context | `dev` / `k3d-dev` |
| 노드 | `k3d-dev-server-0` 단일 노드, ARM64 |
| Kubernetes | K3s `v1.35.5+k3s1` |
| 노드 자원 | CPU 2개, 메모리 약 7.7GiB |
| Namespace | `finance-platform` |
| StorageClass | `local-path`, RWO |
| 네트워크 | 내부 ClusterIP Service, UI는 로컬 port-forward로 접속 |

| PVC | 요청 용량 | 저장 내용 |
| --- | --- | --- |
| `data-postgres-0` | 10Gi | Airflow·Iceberg 카탈로그 DB |
| `data-garage-0` | 10Gi | Garage 메타데이터와 객체 파일 |
| `data-neo4j-0` | 10Gi | Neo4j 데이터 |
| `jupyter-workspace` | 2Gi | 노트북 작업 공간 |

단일 노드 개발 환경으로 고가용성을 제공하지 않는다.
`local-path`의 요청 용량은 실제 디스크 quota를 보장하지 않으며,
PVC 또는 클러스터·Colima VM 삭제 시 데이터가 소실될 수 있다.
백업·복원 테스트는 아직 수행하지 않았다. Airflow 로그는 현재 ephemeral이다.

## 상태 확인과 접속

아래 명령은 저장소 루트에서 실행한다.

```sh
kubectl --context k3d-dev get nodes -o wide
kubectl --context k3d-dev -n finance-platform get deployments,statefulsets
kubectl --context k3d-dev -n finance-platform get pods,svc,pvc
```

UI를 사용할 때 각각 별도 터미널에서 port-forward를 유지한다.

```sh
# Airflow: http://127.0.0.1:8080
kubectl --context k3d-dev -n finance-platform port-forward service/airflow-api-server 8080:8080

# JupyterLab: http://127.0.0.1:8888
kubectl --context k3d-dev -n finance-platform port-forward service/jupyter 8888:8888
```

| 서비스 | 클러스터 내부 주소 |
| --- | --- |
| PostgreSQL | `postgres:5432` |
| Garage S3 | `http://garage:3900`, region `garage`, path-style |
| Iceberg REST | `http://iceberg-rest:8181` |
| Airflow | `http://airflow-api-server:8080` |
| JupyterLab | `http://jupyter:8888` |
| Neo4j | Bolt `neo4j:7687`, HTTP `neo4j:7474` |

Airflow 관리자 계정은 `airflow-admin`, Jupyter 토큰은 `jupyter-auth`의 `token`,
Neo4j 인증은 `neo4j-auth` Secret에서 관리한다.
DB와 S3 인증은 각각 `postgres-credentials`, `garage-credentials`를 사용한다.
실제 비밀번호·토큰·Secret YAML은 Git이나 공유 로그에 남기지 않는다.

## 검증한 범위와 제한

- PostgreSQL: 전용 계정·권한, TCP 접속, Pod 교체 후 데이터 보존, Airflow migration.
- Garage: S3 객체 입출력, multipart, 익명 접근 차단, 재시작 후 객체 보존.
- Spark / Iceberg: 합성 테이블 쓰기·읽기, JDBC 카탈로그 등록, Catalog 재시작 후 새 Spark 세션에서 재조회와 테스트 테이블 정리.
- Jupyter: 올바른 토큰과 잘못된 토큰에 대한 HTTP 인증 동작.
- Airflow: 서비스 health, 관리자 로그인, 인증된 DAG API 응답과 DAG 0개.
- Neo4j: 내부 Bolt 인증과 합성 노드 생성·조회·삭제.

Iceberg REST 서버는 Apache Iceberg의 **테스트 fixture**를 빌드한 것으로,
인증·TLS 없는 개발 클러스터 내부 전용이다. 운영용 카탈로그로 간주하지 않는다.
Garage 호환을 위해 Catalog와 Jupyter에 AWS SDK checksum 설정을 적용했다.
상세 설정과 검증 범위는 [Catalog·Spark 문서](configs/spark/README.md)를 참고한다.

기사 수집부터 Neo4j 적재까지의 전체 처리, streaming 재처리,
브라우저 노트북 UI/kernel 상호작용, Neo4j 신규 PVC의 Pod 교체 후 보존은 미검증이다.
현재 자원은 기반 서비스용으로 조정했으며, 두 streaming 작업을 추가하기 전 자원을 재평가해야 한다.

## 배포 파일과 변경 방법

```text
deploy/k8s/
  helm/             Airflow, Neo4j, Strimzi chart 설정
  manifests/        서비스별 Kubernetes manifest와 업무 템플릿
configs/
  runtime/          실제 실행·검증 기록과 smoke 도구
  postgres/         DB 초기화·인증·검증
  garage/           S3 설정·버킷 초기화·검증
  spark/            Spark·Catalog 설정과 설명
  airflow/          Airflow 설정과 DAG 연결 계약
  kafka/            Kafka·Connect 설정과 이벤트 계약
  neo4j/            Neo4j 설정과 제약 조건
  pipelines/        업무 이미지의 실행·환경변수 계약
docker/             기반 서비스 이미지 Dockerfile
workspace/          업무 코드·DAG 작업 경로
scripts/            manifest 렌더링과 정적 검사
tests/              설정 도구 테스트
```

이미지 설정 예시는 `configs/platform-images.env.example`이다.
실제 이미지 주소를 작성한 로컬 파일을 사용해 새 디렉터리에 렌더링한다.
미확정 이미지 토큰과 `latest`는 허용하지 않는다.

```sh
cp configs/platform-images.env.example configs/platform-images.env
# 실제 repository와 tag/digest를 작성한 뒤 실행
python3 scripts/render-manifests.py --source deploy/k8s \
  --values configs/platform-images.env --output deploy/rendered-review
```

Renderer는 파일만 생성하며 배포하지 않는다. 기존 출력 디렉터리는 덮어쓰지 않는다.
**manifest 또는 렌더링 출력 전체를 재귀 apply하지 않는다.**
검증용 Job과 미배포 업무 리소스가 함께 있으므로 서비스별 파일을 선택해 dry-run 후 적용한다.
Airflow와 Neo4j는 고정 chart·values로 Helm upgrade하며 기존 Secret과 PVC를 재사용한다.
실제로 사용한 빌드·import·배포 명령은 [실행 기록](configs/runtime/VALIDATION.md)에 있다.

정적 설정 검사는 다음과 같다.

```sh
ruby scripts/check-configs.rb
python3 -m unittest discover -s tests -v
git diff --check
```

## 남은 작업

1. Strimzi CRD와 클러스터 RBAC를 검토·승인한 뒤 Operator → Kafka → Connect 순으로 설치하고 개별 검증한다.
2. 기사 수집·변환·발행 코드를 구현하고 이미지 실행 계약에 맞춰 Docker Hub에 게시한다.
3. Airflow에 DAG·Job 템플릿·업무 RBAC를 연결하고 수집 Job부터 수동 검증한다.
4. Bronze → Silver → Gold 처리와 checkpoint·중복·재처리 동작을 검증한다.
5. Kafka topic·Neo4j 제약 조건·Sink Connector를 연결하고 기사 적재를 검증한다.
6. Service API를 구현하고 백업·복원 절차를 검증한다.

업무 streaming 두 Deployment는 템플릿에서 `replicas: 0`, Publisher CronJob은 `suspend: true`,
Connect는 `replicas: 0`, Connector는 `stopped`로 준비되어 있다.
이 업무 리소스들은 현재 클러스터에 생성하지 않았다.

## 상세 문서

현재 실행 상태는 [인프라 실행 기록](configs/runtime/VALIDATION.md)을 기준으로 확인한다.
서비스별 문서에는 최초 파일 준비 단계의 기록도 포함되어 있다.

| 문서 | 내용 |
| --- | --- |
| [PostgreSQL 설계](configs/postgres/PLAN.md) · [검증](configs/postgres/VALIDATION.md) | DB 초기화, 권한, 보존 검증 |
| [Garage 설계](configs/garage/PLAN.md) · [검증](configs/garage/VALIDATION.md) | S3 저장소, 버킷, 객체·multipart 검증 |
| [Catalog·Spark](configs/spark/README.md) | 이미지 빌드, 카탈로그·S3 연결과 제한 |
| [Airflow](configs/airflow/README.md) | Helm 설정, 인증, DAG·Job 연결 |
| [Kafka·Connect](configs/kafka/README.md) | Strimzi 설치 경계와 이벤트 계약 |
| [Neo4j](configs/neo4j/README.md) | Helm 설정, 인증과 그래프 제약 조건 |
| [파이프라인](configs/pipelines/README.md) | 업무 이미지 ENTRYPOINT·환경변수 계약 |
| [구현 계획](configs/IMPLEMENTATION-PLAN.md) | 서비스 간 의존성과 작업 범위 |
| [최초 정적 검증](configs/STATIC-VALIDATION.md) | 파일 준비 단계의 검사 결과 |
