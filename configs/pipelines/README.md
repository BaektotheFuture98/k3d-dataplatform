# Article 데이터 파이프라인

기존 `data_platform` 프로젝트의 Bronze→Silver, Silver→Gold 코드를 현재 k3d 환경으로 이식했다.
실제 Gemini 호출은 하지 않으며 두 Deployment는 `replicas: 0`으로 배포 준비한다.
기사 수집기·Gold Publisher·Kafka/Neo4j 업무 적재는 이번 구현 범위에 포함하지 않는다.

## 처리 흐름

```text
lakehouse.bronze.article
  → 품질 검사·문자열 정규화·기사 ID·최신 상태 MERGE
lakehouse.silver.article
  → 미처리 기사 선택 → Gemini Batch → 엔터티 해소·RDF·SHACL
lakehouse.gold.graph_article

lakehouse.ops.ontology_batch_job: 제출·쿼터 대기·재시도·완료 상태
```

| 작업 | 코드 | 이미지 |
| --- | --- | --- |
| Bronze→Silver | `workspace/pipelines/article_bronze_to_silver/` | `finance-platform/article-bronze-to-silver:v1` |
| Silver→Gold | `workspace/pipelines/article_silver_to_gold/` | `finance-platform/article-silver-to-gold:v1` |

두 이미지 모두 검증한 Spark 4.1.2 / Iceberg 1.11.0 / Hadoop S3A 기반 이미지를 사용한다.
원본의 `datetime.UTC`·`StrEnum`과 의존성에 맞춰 별도 Python 3.13.14 환경을 사용한다.
`workspace/pipelines/uv.lock`으로 Python 의존성을 고정하며 PySpark는 기반 Spark 배포판에서 제공한다.
원본의 `.env`, 인증정보, 불필요한 전체 프로젝트 의존성은 복사하지 않는다.

## 환경변수의 소유권

| 위치 | 설정 |
| --- | --- |
| `spark-config` ConfigMap → `/etc/spark` | Spark local[2], Catalog, Garage S3FileIO·S3A, UTC, 로그 |
| `bronze-to-silver-config` ConfigMap → 환경변수 | Bronze/Silver 테이블, 체크포인트, 처리 주기, 파일 제한 |
| `silver-to-gold-config` ConfigMap → 환경변수 | Silver/Gold/Ops 테이블, 체크포인트, 모델·온톨로지·배치 제한 |
| `garage-credentials` Secret | 두 작업의 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| `gemini-credentials` Secret의 `api-key` | Silver→Gold의 `GOOGLE_API_KEY` |

애플리케이션은 `.env`를 자동으로 읽지 않는다. 필수값, 3단계 테이블 식별자,
S3A 체크포인트와 양수 처리 주기를 시작 시 검증한다. 오류 로그에는 자격증명이나 입력값을 출력하지 않는다.
공통 설정은 `SPARK_CONF_DIR=/etc/spark`로 읽고 Garage 호환 checksum 환경변수도 주입한다.

| 변수 | Bronze→Silver 기본값 | Silver→Gold 기본값 |
| --- | --- | --- |
| `BRONZE_TABLE` | `lakehouse.bronze.article` | 사용 안 함 |
| `SILVER_TABLE` | `lakehouse.silver.article` | `lakehouse.silver.article` |
| `GOLD_TABLE` | 사용 안 함 | `lakehouse.gold.graph_article` |
| `BATCH_JOB_TABLE` | 사용 안 함 | `lakehouse.ops.ontology_batch_job` |
| `CHECKPOINT_URI` | `s3a://warehouse/checkpoints/article-bronze-to-silver-v2` | `s3a://warehouse/checkpoints/article-silver-to-gold` |
| `TRIGGER_INTERVAL` | `1 minute` | `1 minute` |
| `MAX_FILES_PER_MICRO_BATCH` | `100` | 사용 안 함 |
| `PIPELINE_RUN_MODE` | `stream` | `stream` |

Gold ConfigMap은 원본의 비민감 설정인 `SEMANTIC_LLM_MODEL=gemini-3.1-flash-lite`,
`ONT_VERSION=v1`을 지정한다. 코드에서는 모델·버전·API 키가 필수다.
`SEMANTIC_BATCH_SIZE=100`, `SEMANTIC_BATCH_MAX_BYTES=18874368`,
`SEMANTIC_BATCH_POLL_SECONDS=300`, `SEMANTIC_QUOTA_PAUSE_SECONDS=3600`도 환경변수로 제어한다.

`PIPELINE_RUN_MODE=validate`는 설정과 테이블을 검사하고 종료하며 Gemini 클라이언트를 생성하지 않는다.
Bronze는 `available_now`도 지원하여 현재까지 들어온 데이터를 유한한 실행으로 처리할 수 있다.
SIGTERM/SIGINT는 활성 streaming query를 중지하고 Spark 자원을 반환한다.

## 데이터 처리 계약

Bronze는 HTTP 200, 필수값·발행 시각·JSON 유효성을 검사한다. canonical URL이 없으면 source URL을 사용하고
URL의 SHA-256 앞 16자리로 `AR` 접두 기사 ID를 만든다. 제목·본문 공백과 언어 대소문자를 정리한다.
배치 내 후보 선택은 원본의 수집 시각→적재 시각→내용 해시 순서를 유지한다.
Silver MERGE는 적재 시각이 더 최신일 때만 갱신하며 최초 발행 시각은 유지한다.

Silver는 MERGE 테이블이므로 Gold는 직접 append 스트리밍하지 않고 타이머 trigger에서 미처리 행을 조회한다.
Gemini 제출 전에 Ops 상태를 저장하며 재시작 시 기존 작업을 확인한다. 쿼터 초과는 지연 후 재시도하고,
결과가 도착했을 때 Silver 적재 버전이 바뀌었다면 오래된 결과를 저장하지 않는다.
교차 프로세스에서 변경된 테이블을 읽을 때는 Iceberg 메타데이터를 갱신한다.

Gold는 원본과 동일하게 **`(article_id, ont_version)`별 한 번 저장**한다.
같은 온톨로지 버전으로 Gold가 이미 있으면 Silver 내용이 변경되어도 다시 분석하지 않는다.
재분석에는 새 `ONT_VERSION`이 필요하며 버전 변경 전 진행 중인 배치 상태를 확인해야 한다.
개별 결과의 파싱·참조·SHACL 실패는 Gold에서 제외하며 해당 배치는 완료 처리한다.
이런 개별 실패의 자동 재처리는 구현하지 않았다. 외부 Batch 전체의 실패·만료·취소는 지연 후 재시도한다.

## 빌드와 배포 준비

저장소 루트에서 기반 Spark 이미지를 먼저 빌드한다. 상세 설정은 [Spark 문서](../spark/README.md)를 따른다.

```sh
docker build --platform linux/arm64 -f docker/pipelines/Dockerfile --target bronze-to-silver -t finance-platform/article-bronze-to-silver:v1 .
docker build --platform linux/arm64 -f docker/pipelines/Dockerfile --target silver-to-gold -t finance-platform/article-silver-to-gold:v1 .
k3d image import finance-platform/article-bronze-to-silver:v1 finance-platform/article-silver-to-gold:v1 --cluster dev
```

로컬 `configs/platform-images.env`에서 두 IMAGE 참조를 지정한 뒤 새로운 출력 디렉터리로 렌더링한다.
파일에는 비밀번호를 넣지 않는다. 기존 출력 디렉터리는 renderer가 덮어쓰지 않는다.

```sh
python3 scripts/render-manifests.py --source deploy/k8s/manifests/pipelines/bronze-to-silver --values configs/platform-images.env --output deploy/rendered-runtime/bronze-to-silver-v1
python3 scripts/render-manifests.py --source deploy/k8s/manifests/pipelines/silver-to-gold --values configs/platform-images.env --output deploy/rendered-runtime/silver-to-gold-v1
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/rendered-runtime/bronze-to-silver-v1 -f deploy/rendered-runtime/silver-to-gold-v1
kubectl --context k3d-dev -n finance-platform apply -f deploy/rendered-runtime/bronze-to-silver-v1 -f deploy/rendered-runtime/silver-to-gold-v1
```

디렉터리 전체를 재귀 apply하지 않는다. 수집 Job과 오프라인 검증 Job은 명시적 `create` 대상이다.
ConfigMap 변경 후 이미 실행 중인 프로세스에는 재시작이 필요하다. 체크포인트는 재시작 시 같은 경로를 재사용한다.
이벤트 로그는 `/tmp/spark-events`에 저장되며 Pod 교체 시 사라진다.

## 오프라인 검증

```sh
docker build --platform linux/arm64 -f docker/pipelines/Dockerfile --target test -t finance-platform/article-pipelines-test:v2 .
docker run --rm --network none --hostname localhost -e SPARK_LOCAL_IP=127.0.0.1 finance-platform/article-pipelines-test:v2
k3d image import finance-platform/article-pipelines-test:v2 --cluster dev
kubectl --context k3d-dev -n finance-platform create -f deploy/k8s/manifests/pipelines/offline-smoke-job.yaml
```

컨테이너 테스트는 원본 Bronze 변환, 환경변수 검증, 결정적 ID, 그래프 참조·SHACL 및 요청 크기 제한을 검사한다.
Kubernetes 검증은 고유한 `pipeline_smoke_<UUID>` namespace의 테이블과 전용 S3A prefix를 사용한다.
외부 Batch 서비스만 in-process 클라이언트로 대체하고 실제 Spark·Iceberg·Garage·RDF·SHACL 코드는 실행한다.
검증 종료 시 소유한 테이블과 파일만 정리한다. 실제 Gemini API 키는 전달하지 않는다.
결과와 시행착오는 [실행 기록](../runtime/VALIDATION.md)에 남긴다.

## 추후 실제 활성화

현재는 사용자 지시에 따라 실제 Gemini 호출·업무 상시 실행을 하지 않는다.
활성화할 때는 먼저 키를 안전한 파일로 준비하고, 파일 내용이 실제 API 키만 담도록 한다.
다음은 이후 운영자가 실행할 예시이며 이번 작업에서는 실행하지 않는다.

```sh
kubectl --context k3d-dev -n finance-platform create secret generic gemini-credentials --from-file=api-key=/secure/path/gemini-api-key
# 자원과 입력 데이터·모델·버전을 확인한 뒤 필요한 작업을 하나씩 활성화
kubectl --context k3d-dev -n finance-platform scale deployment/bronze-to-silver --replicas=1
# Silver→Gold 활성화는 실제 Gemini 요청과 비용을 발생시킬 수 있음
kubectl --context k3d-dev -n finance-platform scale deployment/silver-to-gold --replicas=1
```

Secret이 이미 있으면 위 생성 명령으로 교체하지 말고 별도 키 갱신 절차를 사용한다.
2 CPU 노드에서 두 작업 동시 실행의 처리량·장기 메모리 사용은 아직 검증하지 않았다.
수집·Publisher·Airflow DAG 연결은 별도 작업이다.
