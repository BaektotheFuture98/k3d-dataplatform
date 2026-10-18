# 파이프라인 이미지 및 실행 계약

파일만 작성한 상태다. 수집, 정제, Gold 변환, 발행 업무 애플리케이션은 **미구현**이며 사용자가 Docker Hub 이미지를 제공해야 한다. 배포 성공/업무 처리/중복 방지 보장은 검증하지 않았다.

| 리소스 | 이미지 토큰 | 프로세스 계약 |
| --- | --- | --- |
| article-collector manual Job | `__ARTICLE_COLLECTOR_IMAGE__` | 이미지 ENTRYPOINT가 한 번 수집 후 0으로 종료, 실패는 비영(非零) 종료 |
| bronze-to-silver Deployment | `__BRONZE_TO_SILVER_IMAGE__` | 이미지 ENTRYPOINT가 독립 Spark local[2] streaming 프로세스 시작 |
| silver-to-gold Deployment | `__SILVER_TO_GOLD_IMAGE__` | 이미지 ENTRYPOINT가 별도 Spark local[2] streaming 프로세스 시작 |
| gold-publisher CronJob | `__GOLD_PUBLISHER_IMAGE__` | 이미지 ENTRYPOINT가 한 번 durable 변경 발행 후 종료 |

각 토큰은 immutable digest 또는 사용자 게시 tag를 포함하는 전체 이미지 참조로 치환한다. `command`/`args`를 지정하지 않았으므로 위 ENTRYPOINT를 이미지가 제공해야 한다. 저장소에 존재하지 않는 Python module/script를 실행하도록 가정하지 않는다. Spark 이미지 기반 애플리케이션은 Spark 4.1.2/Iceberg 1.11.0 및 필요한 S3 dependencies를 제공해야 하며 `SPARK_MASTER`와 아래 환경변수를 실제 Spark/Iceberg 설정에 연결해야 한다. 환경변수만으로 라이브러리 설정이 자동 생성되지는 않는다.

모든 워크로드는 `finance-platform`. 공통 환경변수는 `AWS_ENDPOINT_URL=http://garage.finance-platform.svc.cluster.local:3900`, `AWS_REGION=garage`, `S3_PATH_STYLE_ACCESS=true`, `S3_SIGNATURE_VERSION=s3v4`, `WAREHOUSE_URI=s3://warehouse/`, `ICEBERG_CATALOG_URI=http://iceberg-rest:8181`이다. AWS 자격증명은 `garage-credentials`의 `s3-access-key-id`/`s3-secret-access-key`에서 가져온다. 수집은 `BRONZE_URI=s3://warehouse/bronze/articles/`를 사용한다. 외부 API가 필요한 경우에만 사용자가 collector Pod에 `collector-api` Secret의 합의한 키를 명시적으로 추가한다. 현재 API key를 요구하거나 plaintext로 저장하지 않는다.

스트리밍 Deployment는 각각 `replicas: 0`, 전략 `Recreate`이고 별도의 `CHECKPOINT_URI=s3://warehouse/checkpoints/bronze-to-silver/` 또는 `.../silver-to-gold/`를 사용한다. 동일 query checkpoint를 여러 프로세스가 공유하면 안 된다. 애플리케이션이 SIGTERM을 받아 신규 batch를 멈추고 120초 안에 진행 중 batch/checkpoint를 안전하게 마친 뒤 종료해야 한다. 재시작 때 동일 checkpoint를 재사용한다. 가짜 HTTP port/probe는 넣지 않았다. 이미지가 준비되면 실제 batch 진행/heartbeat, dependency 장애와 startup 지연을 구분하는 app-specific startup/readiness/liveness 계약을 구현·검증한 후 probe를 추가해야 한다. 프로세스 실행만으로 streaming의 정상 진행을 보장하지 않는다.

Publisher는 `KAFKA_BOOTSTRAP_SERVERS=finance-kafka-kafka-bootstrap:9092`, `KAFKA_TOPIC=article-gold`, `PUBLISHER_STATE_URI=s3://warehouse/checkpoints/gold-publisher/`를 받는다. CronJob은 `suspend: true`, `concurrencyPolicy: Forbid`, 성공 1/실패 2개 history, 24시간 TTL이다. 5분 schedule은 검토용 기본값이다. 실행 시간 제한은 240초다. 수동 collector Job은 apply하면 바로 실행되므로 일반 구성 apply 묶음에 포함하지 말고 사용자가 명시적으로 수집을 시작할 때 고유 Job 이름으로 제출한다. 같은 이름의 완료 Job은 재실행되지 않는다.

안전한 재처리는 별도 업무 구현이 필요하다. 문서/이벤트는 안정적인 `article_id`, 기사별 단조 증가하는 `source_version`, 재발행에도 동일한 `event_id`를 사용한다. Publisher는 durable outbox 또는 durable change watermark로 변경을 추적하고 Kafka ack 이후 진척을 저장해야 한다. 전송 성공과 watermark 저장 사이 장애로 중복이 생길 수 있다. Consumer/Neo4j sink는 `article_id` 기준 MERGE와 원자적인 version 비교를 결합하여 이전/동일 `source_version` 이벤트가 최신 상태를 덮어쓰지 않게 해야 한다. 이벤트 dedup과 watermark, version ordering은 여기서 구현되지 않았으며 exactly-once를 주장하지 않는다.

나중에 이미지/ENTRYPOINT/env와 schema/checkpoint 호환성을 확인하고 Secret·Catalog·Kafka가 준비된 후 수동 Job부터 검증한다. 각 streaming Deployment를 독립적으로 1 replica로 올리고 재시작/복구/중복·역순 이벤트 검증을 마친 뒤 publisher schedule을 정해 suspend를 해제한다. Airflow 수집 설정은 [Airflow 계약](../airflow/README.md)을 따른다.

공식 근거: [Kubernetes Job](https://kubernetes.io/docs/concepts/workloads/controllers/job/), [CronJob concurrency/suspend/history](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/), [KubernetesJobOperator](https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/10.24.0/_api/airflow/providers/cncf/kubernetes/operators/job/index.html).
