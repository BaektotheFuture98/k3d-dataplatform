# 후속 플랫폼 구성 계획

## 현재 작업 범위

사용자 변경 지시: 후속 워크로드를 실행하거나 배포하지 않고 저장소 파일만 구축한다.
서브에이전트는 gpt-6.1-sol / low, 병렬 가능한 작업을 병렬화하고 최종 검토는 주 에이전트가 한다.
파이프라인 컨테이너는 사용자가 이후 Docker Hub에 올릴 예정이다.
기존 PostgreSQL/Garage 배포는 이번 작업에서 변경하거나 중지하지 않는다.

## 공통 계약

- context `k3d-dev`, namespace `finance-platform`; 클러스터 범위 변경 금지.
- DB Service `postgres:5432`, DB `airflow_meta`/`iceberg_catalog`.
- DB Secret `postgres-credentials`: `airflow-password`, `iceberg-password`.
- S3 endpoint `http://garage.finance-platform.svc.cluster.local:3900`.
- S3 region `garage`, private bucket `warehouse`, path-style/SigV4.
- S3 Secret `garage-credentials`: `s3-access-key-id`, `s3-secret-access-key`.
- Catalog Service `iceberg-rest:8181`, Spark 4.1.2, Iceberg 1.11.0.
- Kafka `finance-kafka-kafka-bootstrap:9092`, topic `article-gold`, one broker KRaft.
- Neo4j Service `neo4j:7687`, credential Secret `neo4j-auth`.
- 이미지 미확정 값은 `__UPPER_SNAKE_CASE__` 토큰을 사용하고 실제 이미지로 간주하지 않는다.
- 업무 파이프라인 코드가 없으면 구현 완료로 표시하지 않는다.
- pipeline Deployment replicas=0, CronJob suspend=true, collection Job은 명시적 실행용.
- CPU/메모리는 단일 노드 개발용. 영속 데이터 local-path PVC, 삭제/재초기화 금지.
- 버전/Helm values/CRD는 공식 근거를 확인하며 확인 불가 부분은 한계를 문서화한다.
- Secret 실제 값은 생성/출력/저장 금지. 이번 작업에서 helper도 실행하지 않는다.

## 병렬 구현 단위와 소유 경로

1. Catalog/Spark: `docker/iceberg-rest`, `docker/spark`, `configs/spark`,
   `deploy/k8s/manifests/iceberg-rest`, `deploy/k8s/manifests/spark`.
   JDBC Catalog와 Garage S3FileIO 연결, 버전 호환성, 인증 Jupyter, 독립 local Spark 실행 기반.
2. Kafka/Neo4j: `deploy/k8s/helm/{strimzi,neo4j}`, `deploy/k8s/manifests/kafka`,
   `docker/kafka-connect`, `configs/kafka`, `configs/neo4j`.
   버전 고정 Operator/CRD/플러그인, 단일 KRaft, 내부 토픽 설정, Neo4j idempotent sink 계약.
3. Airflow/파이프라인: `deploy/k8s/helm/airflow`, `workspace/airflow`,
   `deploy/k8s/manifests/pipelines`, `configs/airflow`, `configs/pipelines`.
   LocalExecutor + 외부 DB, KubernetesJobOperator/RBAC, 사용자 이미지 참조, suspended workload.
4. 주 에이전트: README, 렌더링/정적 검증 도구, 버전/서비스/Secret 계약 검토,
   누락된 이미지 및 업무 코드·실행 검증 상태를 문서화.

## 검증과 완료 기준

- 모든 파일을 검토하고 충돌 없는 서비스명/Secret 키/이미지 토큰을 확인한다.
- YAML 파싱, Python AST, shell 문법, 가능하면 다운로드한 Chart의 로컬 template 등 정적 검증.
- kubectl/helm 배포, 서버 dry-run, Docker build/run, k3d import, Job 실행은 하지 않는다.
- CI/검증 도구가 토큰 누락을 식별하고 실행 가능한 설정과 예제를 구분하도록 한다.
- 실행 검증이 필요한 사항과 사용자가 나중에 입력할 값을 README에 명시한다.

## 최종 검토 결과

- [x] 세 구현 단위를 지정 모델로 병렬 작성하고 주 에이전트가 검토했다.
- [x] 서비스명/Secret 키/이벤트 스키마를 통일했다.
- [x] 미확정 이미지는 공통 env 입력과 원자적 파일 renderer로 처리했다.
- [x] YAML 35개 문서, 전체 파일 렌더링 29개 파일, 단위 검사 12개를 정적으로 검증했다.
- [x] 알려진 Spark/Iceberg 이슈, fixture 한계, 미제공 업무 코드와 자원 한계를 문서화했다.
- [x] 후속 배포/빌드/워크로드/Secret 생성은 실행하지 않았다.
