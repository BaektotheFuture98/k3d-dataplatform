# 기반 서비스 실행 계획 — 사용자 변경 지시 반영

사용자는 이전 파일 전용 제한을 변경하여 데이터 파이프라인 생성을 제외한 기반 서비스
기동을 허용했고, k3d 밖의 다른 Docker 컨테이너도 중지할 수 있도록 했다.
기존 클러스터/Namespace/StorageClass/PVC는 보존한다.

## 포함

PostgreSQL, Garage, PostgreSQL JDBC 기반 Iceberg REST, Spark/Jupyter,
업무 DAG 없는 Airflow, Kafka broker와 Connect worker, Neo4j Community.
기동/인증/내부 연결과 합성 인프라 smoke만 검증한다.

## 제외

Article collector Job, Bronze/Silver streaming Deployment, Gold Publisher CronJob,
기사 DAG와 pipeline RBAC, article-gold KafkaTopic, KafkaConnector 및 기사 그래프/업무 데이터.
기존 파일은 유지하지만 배포하지 않는다. 이미지의 업무 DAG/Job template COPY도 제거한다.

## 실행 순서

1. [x] 클러스터/자원/기존 리소스·이미지 확인.
2. [x] k3d 외부의 기존 컨테이너 7개 정상 중지, 컨테이너·볼륨 보존.
3. [x] 기존 DB 비밀번호를 재사용한 Airflow metadata 및 Jupyter/Neo4j Secret 생성, 값 미출력.
4. [x] 6.1-sol/low 에이전트 3개로 Catalog/Spark 이미지, Airflow/Connect 이미지,
   고정 Helm chart/CRD·RBAC 검증을 병렬 준비. 주 에이전트가 검토·배포.
5. [x] Namespaced Neo4j/Airflow/Spark/Jupyter/Catalog를 이미지 준비 순서대로 적용.
6. [ ] Strimzi CRD/ClusterRole/ClusterRoleBinding은 별도 구체적 사용자 승인 후에만 적용.
7. [ ] Kafka broker, Connect worker 기동. 비즈니스 Topic/Connector는 생성하지 않음.
8. [x] 기동된 서비스의 Ready, PVC, 인증, 내부 API/네트워크와 infrastructure smoke 검증 기록.
   Kafka/Connect 검증은 6·7번 완료 후 별도로 필요하다.

## 자원

노드는 2 CPU/약7.7GiB. 별도 Docker 서비스 중지로 실제 메모리 여유를 확보했다.
Neo4j chart는 500m CPU 최소값을 강제하므로 유지한다. Airflow scheduler request=150m,
Kafka request=150m, Jupyter request=100m로 조정하고 CPU limits는 유지한다.
업무 workload 없이 전체 기본 CPU requests는 기존 시스템 포함 약1900m로 계획했다.
Chart 렌더링 및 실제 Pending/OOM 상황에 따라 다시 확인한다.
