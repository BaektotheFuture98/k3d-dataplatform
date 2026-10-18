# 기반 서비스 실제 실행 검증 — 2026-10-18

## 범위와 현재 결과

최초 실행 범위는 **데이터 파이프라인 생성을 제외한 기반 서비스**였다.
후속 요청으로 테이블·UI 접속·Spark 설정·두 기사 파이프라인을 구성했다.
최신 상태는 문서 하단의 파이프라인 검증 기록을 따른다. 실제 Gemini 호출은 제외했다.
기존 dev 클러스터/finance-platform Namespace/local-path StorageClass/PVC를 보존했다.
6.1-sol/low 서브에이전트 3개가 독립적으로 이미지와 고정 chart를 준비했고,
주 에이전트가 변경을 검토하고 배포·연결·인증 테스트를 수행했다.

| 구성 | 실제 관측 | 검증 범위 |
| --- | --- | --- |
| PostgreSQL 17.11 | StatefulSet 1/1, PVC 10Gi Bound | 이전 전용 계정/TCP/권한/Pod 교체 보존 검증 유지, Airflow migration 및 JDBC catalog 사용 성공 |
| Garage 2.4.1 | StatefulSet 1/1, PVC 10Gi Bound | 이전 S3/multipart/보존 검증 유지, Iceberg 파일 I/O 성공 |
| Iceberg REST 1.11.0 fixture | Deployment 1/1 | Service DNS `/v1/config`, JDBC `iceberg_tables` 행, 테이블 생성, 재시작 후 재조회 |
| Spark 4.1.2 / Iceberg 1.11.0 | Jupyter Deployment 1/1 | Local range count, 합성 Iceberg write/read, 새 Spark 프로세스 read/cleanup |
| JupyterLab 4.4.9 | PVC 2Gi Bound | 무토큰·잘못된 토큰 HTTP403, 올바른 토큰 HTTP200 |
| Airflow 3.0.2 / chart 1.18.0 | API/scheduler/dag-processor 각각 1/1 | metadata/scheduler/dag_processor healthy, FAB login HTTP201, 인증된 DAG API HTTP200, DAG 0개 |
| Neo4j Community 5.26.32 | StatefulSet 1/1, PVC 10Gi Bound | 내부 `bolt://neo4j:7687` 인증, RETURN 1, 합성 노드 create/read/delete TRUE |
| Kafka / Strimzi | 미설치 | 공식 chart 0.51.0 렌더링 완료, 클러스터 리소스 사전 승인 대기 |
| Kafka Connect | 미기동 | ARM64 이미지 빌드·import·Neo4j 플러그인 클래스 확인만 완료 |

최종 관측에서 장기 실행 Pod 8개 모두 Ready, 총 restartCount=0이었다.
서비스별 EndpointSlice 주소가 존재한다. 최초 관측 당시 CronJob 및 업무 Deployment는 없었다.
완료/실패한 과거 PostgreSQL/Garage smoke Pod는 TTL 정리 대상이며 실행 중인 서비스 오류와 구분한다.
기존 검증 실패·수정 기록은 각 서비스 VALIDATION 문서에 보존했다.

## 실제 실행한 핵심 명령

모든 namespaced kubectl 작업은 `--context k3d-dev -n finance-platform`을 사용했다.
아래는 실행 순서의 핵심 명령이며 rollout/get/log/exec 관측을 추가 수행했다.
임시 도구/렌더링 디렉터리는 영속 설치 소스가 아니므로 사라지면 고정 버전으로 다시 준비한다.

```sh
# 컨테이너만 중지, 삭제 및 볼륨 정리 없음
docker stop --time 30 minio spark-iceberg mc iceberg-postgres finbridge-qdrant finbridge-neo4j postgresql
python3 configs/prepare-secrets.py --apply

docker build --platform linux/arm64 -f docker/spark/Dockerfile -t finance-platform/spark:4.1.2-iceberg1.11.0 .
docker build --platform linux/arm64 -f docker/iceberg-rest/Dockerfile -t finance-platform/iceberg-rest:1.11.0-pg42.7.8 .
docker build --platform linux/arm64 -f docker/airflow/Dockerfile -t finance-platform/airflow:3.0.2-kubernetes-10.24.0-infra .
docker build --platform linux/arm64 -f docker/kafka-connect/Dockerfile -t finance-platform/kafka-connect-neo4j:0.51.0-kafka4.2.0-neo4j5.1.16 .
k3d image import finance-platform/spark:4.1.2-iceberg1.11.0 --cluster dev
k3d image import finance-platform/iceberg-rest:1.11.0-pg42.7.8 --cluster dev
k3d image import finance-platform/airflow:3.0.2-kubernetes-10.24.0-infra --cluster dev
k3d image import finance-platform/kafka-connect-neo4j:0.51.0-kafka4.2.0-neo4j5.1.16 --cluster dev

/private/tmp/finance-platform-tools/helm upgrade --install neo4j /private/tmp/finance-neo4j5/neo4j --kube-context k3d-dev -n finance-platform -f deploy/k8s/helm/neo4j/values.yaml --hide-notes --wait --timeout 5m
/private/tmp/finance-platform-tools/helm upgrade --install airflow /private/tmp/finance-platform-tools/airflow --kube-context k3d-dev -n finance-platform -f deploy/k8s/helm/airflow/values.yaml --set defaultAirflowRepository=finance-platform/airflow --set defaultAirflowTag=3.0.2-kubernetes-10.24.0-infra --hide-notes --timeout 5m
python3 configs/runtime/provision-airflow-admin.py --pod airflow-api-server-7fc68bcf78-hmvkb

# 초기 배포 후 checksum 호환 설정을 반영한 최종 렌더링/적용
python3 scripts/render-manifests.py --source deploy/k8s/manifests/iceberg-rest --values configs/platform-images.env --output deploy/rendered-runtime/iceberg-rest-checksum
python3 scripts/render-manifests.py --source deploy/k8s/manifests/spark --values configs/platform-images.env --output deploy/rendered-runtime/spark-checksum
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/rendered-runtime/iceberg-rest-checksum -f deploy/rendered-runtime/spark-checksum
kubectl --context k3d-dev -n finance-platform apply -f deploy/rendered-runtime/iceberg-rest-checksum -f deploy/rendered-runtime/spark-checksum
kubectl --context k3d-dev -n finance-platform rollout status deployment/iceberg-rest --timeout=45s
kubectl --context k3d-dev -n finance-platform rollout status deployment/jupyter --timeout=45s

kubectl --context k3d-dev -n finance-platform exec -i deployment/jupyter -- python3 - write < configs/runtime/iceberg-smoke.py
kubectl --context k3d-dev -n finance-platform rollout restart deployment/iceberg-rest
kubectl --context k3d-dev -n finance-platform rollout status deployment/iceberg-rest --timeout=45s
kubectl --context k3d-dev -n finance-platform exec -i deployment/jupyter -- python3 - read < configs/runtime/iceberg-smoke.py
kubectl --context k3d-dev -n finance-platform get pods,pvc
kubectl --context k3d-dev -n finance-platform get deployments,statefulsets,cronjobs,endpointslices
kubectl --context k3d-dev -n finance-platform top nodes
kubectl --context k3d-dev -n finance-platform top pods
ruby scripts/check-configs.rb
python3 -m unittest discover -s tests -v
git diff --check
```

Airflow 설치는 `--wait` 없이 post-install migration hook을 완료한 후 각 Deployment Ready를 확인했다.
실제 두 번째 upgrade에서 API workers=1, SQLAlchemy pool=3/overflow=2를 반영했다.
위 admin provisioning의 Pod 이름은 실행 당시 값이다. 재실행 전 현재 API Pod 이름을 확인한다.
이미지 태그/ID와 빌드 시행착오는 같은 디렉터리의 agent별 notes에 기록했다.

## 확인한 실패와 수정

- 기존 REST 이미지의 1.11.0 태그가 main snapshot이어서 사용하지 않았다. 공식 release tag 소스 빌드로 교체했다.
- upstream checkout 버전이 1.12.0-SNAPSHOT으로 계산되어 fixture 복사가 실패했다. version.txt=1.11.0을 명시해 재빌드했다.
- PostgreSQL JDBC Maven `.sha256`/`.sha512`는 HTTP404였다. 공식 jar의 고정 SHA256으로 검증한다.
- Airflow 이미지의 cryptography/cffi 충돌은 고정 버전으로 해결했고 `pip check`가 통과했다.
- 첫 admin helper는 FAB provider configuration 초기화 누락으로 실패했다. 공식 CLI와 동일한 초기화 후 생성·로그인이 성공했다. 진단은 stage/예외 클래스만 표시한다.
- Jupyter 컨테이너에는 `python` 별칭이 없어 첫 exec가 실패했다. 설치된 `python3`로 실행했다.
- 최초 Iceberg 테이블 생성은 Garage `Invalid payload signature`로 실패했다.
  Catalog와 Jupyter에 `AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED`,
  `AWS_RESPONSE_CHECKSUM_VALIDATION=WHEN_REQUIRED`를 적용한 후 동일 smoke가 성공했다.
  설정 근거: [AWS Java SDK 문서](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/s3-checksums.html).
- API 서버 기본 worker 4개는 메모리 약936Mi였다. worker 1개로 변경 후 약216Mi로 감소했다.

## 데이터와 보안

합성 `platform_smoke.catalog_roundtrip`에 id=17 한 행을 저장하고 같은 세션과 재시작 후 새 세션에서 읽었다.
PostgreSQL `iceberg_tables`에 `rest_backend/platform_smoke/catalog_roundtrip` 행을 확인했다.
마지막 read 성공 후 해당 테스트 테이블만 `DROP TABLE ... PURGE`했다. 테스트 namespace는 남겨두었다.
최초 인프라 검증에서는 업무 Bronze/Silver/Gold 테이블이나 기사 그래프를 만들지 않았다.
후속 테이블 생성은 이 문서의 Article 테이블 구성 항목에 기록했다.

DB/S3 Secret 값과 Catalog 로그를 메모리에서 비교해 로그에 해당 값이 없음을 확인했다.
REST fixture의 catalog 속성 INFO logger는 OFF를 유지한다. 이 서버는 인증/TLS 없는 테스트 fixture이므로
개발 클러스터 내부 전용이며 운영 배포용이라고 간주하지 않는다.
비밀번호·토큰은 출력하거나 Git에 저장하지 않았다. Airflow admin은 `airflow-admin`,
Jupyter token은 `jupyter-auth`, Neo4j 인증은 `neo4j-auth` Secret에 있다.

기존 PVC를 삭제/재초기화하지 않았다. 새 PVC는 Neo4j10Gi와 Jupyter2Gi이며 둘 다 local-path Bound다.
local-path의 ReclaimPolicy=Delete, volume expansion=false를 유지했다. PVC 또는 클러스터 삭제 시 데이터가
소실될 수 있으므로 PostgreSQL dump, Garage 데이터, Neo4j dump와 노트북을 별도로 백업해야 한다.
원래 외부 Docker 컨테이너 7개는 Exited 상태이고 컨테이너·볼륨은 보존했다.
`mc`는 정상 종료 대기 후 exit137이 관측되었으며 저장 서비스는 아니다.

## 자원, 접속과 로그

관측 시 노드 CPU513m(25%), 메모리3133Mi(39%). 이는 Kafka/Connect가 없는 시점의 표본이다.
각 서비스는 Ready였고 Pod 메모리는 API216Mi, scheduler287Mi, DAG processor172Mi,
Catalog145Mi, Jupyter90Mi, Neo4j791Mi, PostgreSQL44Mi, Garage19Mi였다.
노트북에서 Spark를 실행하면 별도 JVM 메모리가 추가된다. 향후 두 streaming을 추가하기 전 자원을 재평가한다.

최초 기반 서비스 검증 시에는 port-forward만 사용했다. 후속 Ingress 설정으로 현재는
Mac에서 `http://jupyter.localhost:8080`, `http://airflow.localhost:8080`에 직접 접속한다.
아래 port-forward는 대체 접속 방법이며 Airflow는 Ingress와 충돌하지 않는 18080을 사용한다.

```sh
kubectl --context k3d-dev -n finance-platform port-forward service/airflow-api-server 18080:8080
kubectl --context k3d-dev -n finance-platform port-forward service/jupyter 8888:8888
kubectl --context k3d-dev -n finance-platform logs deployment/iceberg-rest --tail=100
kubectl --context k3d-dev -n finance-platform logs deployment/airflow-scheduler -c scheduler --tail=100
kubectl --context k3d-dev -n finance-platform logs deployment/jupyter --tail=100
kubectl --context k3d-dev -n finance-platform logs neo4j-0 --tail=100
```

대체 port-forward UI는 Airflow `http://127.0.0.1:18080`, Jupyter `http://127.0.0.1:8888`이다.
인증 정보는 Kubernetes Secret을 안전하게 조회해 사용하며 공유 터미널이나 기록에 출력하지 않는다.
재배포는 원본을 수정하고 새 디렉터리에 렌더링한 후 선택 파일만 dry-run/apply한다.
Helm은 동일 release/고정 chart/values로 upgrade한다. Secret과 PVC를 재사용하고 DB 업그레이드 전 백업한다.
manifest 전체를 재귀 apply하면 제외한 업무 리소스가 생성되므로 사용하지 않는다.

## 미완료와 다음 작업

Strimzi cluster 리소스 승인 대기: `strimzi-cluster-resources.yaml`은 공식 chart에서 추출한
CRD10개/ClusterRole7개/ClusterRoleBinding3개이며 Secret은 없다. 승인 없이 적용하지 않았다.
승인 후 CRD Established → namespaced operator(`--skip-crds`) → NodePool/Kafka →
Connect worker 순으로 기동하고 PVC/브로커 produce-consume/plugin API를 검증한다.
업무 article-gold topic/KafkaConnector는 계속 제외한다.

기사 수집·변환·발행 코드, DAG, pipeline RBAC, streaming checkpoint/replay,
Kafka→Neo4j 기사 적재 및 Service API는 현재 실행 범위에서 제외되어 미검증이다.
브라우저 노트북 UI/kernel 상호작용, Neo4j 신규 PVC의 Pod 교체 보존 테스트도 수행하지 않았다.
합성 Spark smoke에서 알려진 선택적 Flink 클래스 오류는 재현되지 않았지만 모든 연산의 호환성을 증명하지 않는다.

## Mac 로컬 UI Ingress 적용 — 2026-10-18

기존 `kube-system/traefik` Deployment 1/1과 `traefik` IngressClass를 재사용했다.
설정 전 `k3d-dev-serverlb`에는 API용 `59772:6443`만 있었고,
Mac의 `http://jupyter.localhost:8080/login` 연결은 거부되었다.

```sh
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/k8s/manifests/ingress/platform-ui.yaml
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/ingress/platform-ui.yaml
k3d node edit k3d-dev-serverlb --port-add 127.0.0.1:8080:80
```

Ingress `platform-ui`는 `jupyter.localhost`를 `jupyter:8888`,
`airflow.localhost`를 `airflow-api-server:8080`으로 연결한다.
k3d 명령은 로드밸런서 컨테이너만 교체했으며 기존 API 포트와 노드·Pod·PVC를 유지했다.
Docker inspect에서 HTTP 매핑 `HostIp=127.0.0.1, HostPort=8080`을 확인했다.
클러스터 재생성이나 `/etc/hosts` 수정은 하지 않았다.

| 검증 | 실제 결과 |
| --- | --- |
| Mac → Jupyter `/login` | HTTP 200 |
| Mac → Airflow `/` | HTTP 200 |
| 미등록 host `localhost:8080` | HTTP 404 |
| Jupyter 잘못된 토큰 → `/api/contents` | HTTP 403 |
| Jupyter 기존 토큰 → `/api/contents` | HTTP 200, directory 응답 |
| Jupyter `/api/events/subscribe` WebSocket | HTTP 101 Switching Protocols |
| Airflow 기존 Admin → `/auth/token` → `/api/v2/dags` | 로그인 성공, DAG API HTTP 200, DAG 0개 |
| 기존 서비스·저장소 | 상시 실행 Pod 8개 Ready, PVC 4개 Bound, 앱 재시작 0 |

인증 검증은 로컬 Python에서 kubectl 결과를 capture하고 자격증명을 메모리에만 유지했다.
기존 Secret을 변경하거나 비밀번호·토큰을 출력하지 않았다.
WebSocket 검증은 이벤트 구독 경로이며 노트북 커널 생성·실행은 하지 않았다.
브라우저에서의 직접 조작은 미검증이다.
접속·재적용 절차는 [로컬 UI 접속 설정](../ingress/README.md)에 있다.

## Article 테이블 구성 — 2026-10-18

사용자의 후속 요청에 따라 기존 `/Users/baektothefuture/Project/data_platform/`의
`workspace/notebooks/pipelines/price_medallion/medallion.ipynb`에서 생성 정의를 가져왔다.
사전 조회에서 Catalog에는 `platform_smoke`만 있었고 업무 테이블은 없었다.

`workspace/notebooks/article_medallion.ipynb`와 `sql/`의 SQL 파일 4개를
Jupyter PVC의 `/workspace/notebooks/`에 저장했다. `nbformat.validate`로 형식을 검증하고,
`NotebookClient(..., kernel_name='python3', timeout=180)`를 사용해 노트북 디렉터리를
작업 경로로 지정하여 전체 셀을 실행했다. 실행 출력이 저장된 노트북을 저장소에도 보관했다.

| 테이블 | 컬럼 수 | 생성 직후·재실행 후 행 수 |
| --- | --- | --- |
| `lakehouse.bronze.article` | 14 | 0 |
| `lakehouse.silver.article` | 7 | 0 |
| `lakehouse.gold.graph_article` | 10 | 0 |
| `lakehouse.ops.ontology_batch_job` | 9 | 0 |

실제 검사한 항목은 컬럼 순서·타입·nullable, Iceberg provider, 각 파티션 표현식,
format-version=2, Parquet·Zstd, warehouse 위치, Silver의 copy-on-write·hash 설정이다.
새 커널에서 전체 재실행 시 기존 네 테이블의 계약이 일치했고,
`ARTICLE_TABLES_VALIDATED 4`, `IDEMPOTENT_RERUN_PASS`를 확인했다. 코드 셀 9개 모두 성공했다.

Bronze의 `ar_published_at`은 최초 CREATE에 포함했다. 언어 변경 UPDATE는 제외했고,
기존 테이블의 자동 변경·삭제, 테스트 데이터 삽입, 업무 파이프라인 실행은 하지 않았다.
`ops.article_pipeline_state`는 원본에 생성 정의가 없어 만들지 않았다.
파이프라인을 연결할 때 생산자와 스키마 계약을 먼저 확정한다.

최초 실행의 Spark 종료 과정에서 임시 경로 native 삭제 실패 후 Java IO fallback 경고가 있었으나
노트북 실행 결과는 성공했고 재실행에서도 네 테이블이 정상 검증되었다.
브라우저 화면 검수는 수행하지 않았다. 현재 노트북은
`http://jupyter.localhost:8080/lab/tree/notebooks/article_medallion.ipynb`에서 확인한다.

## 원본 Spark 설정 동기화 및 S3A 복구 검증 — 2026-10-18

기존 프로젝트의 `configs/spark/spark-defaults.conf`, `log4j2.properties`, Spark Dockerfile,
Compose 마운트와 두 streaming 코드의 checkpoint 경로를 비교했다.
수정 전 실제 Spark 실행에서는 Hadoop 3.4.2를 사용하면서 S3A jar와 Garage용 fs.s3a 설정이 없었다.
`spark-checkpoint-smoke.py write`가 `ClassNotFoundException: S3AFileSystem`으로 실패하는 것을 재현했다.

### 적용 내용

- Hadoop 3.4.2와 동일한 hadoop-aws 3.4.2, 공식 POM에 지정된 AWS SDK bundle 2.29.52를 이미지에 추가했다.
- 공식 Maven artifact의 SHA-256을 Dockerfile에 고정하고 빌드 중 검증했다.
- S3A endpoint·region·path-style·HTTP·환경변수 credentials provider를 Garage에 맞췄다.
- 원본 log4j2 설정과 Spark 이벤트 로그를 반영했다. 로그 디렉터리는 이미지가 생성하는 `/tmp/spark-events`다.
- root WARN·Iceberg INFO, UTC를 공통 설정으로 지정했다. driver 1GiB, shuffle 4, Java 21, UI 비활성화는 현재 노드 기준으로 유지했다.
- 두 미배포 streaming 템플릿에 `/etc/spark` ConfigMap 마운트와 SPARK_CONF_DIR·checksum 환경변수를 연결했다.
- checkpoint URI는 원본 코드와 동일한 `s3a://warehouse/checkpoints/article-bronze-to-silver-v2`,
  `s3a://warehouse/checkpoints/article-silver-to-gold`로 맞추고 Silver→Gold Warehouse URI의 공백을 수정했다.

새 이미지 `finance-platform/spark:4.1.2-iceberg1.11.0-s3a-v1`의 로컬 image ID는 `b4f4ed42612c`다.
기존 태그를 덮어쓰지 않고 새 태그를 k3d에 반입했다. 로컬 `configs/platform-images.env`의 SPARK_IMAGE를
갱신한 뒤 새로운 렌더링 디렉터리의 Spark 리소스만 dry-run/apply했다.

```sh
docker build --platform linux/arm64 -f docker/spark/Dockerfile -t finance-platform/spark:4.1.2-iceberg1.11.0-s3a-v1 .
k3d image import finance-platform/spark:4.1.2-iceberg1.11.0-s3a-v1 --cluster dev
python3 scripts/render-manifests.py --source deploy/k8s/manifests/spark --values configs/platform-images.env --output deploy/rendered-runtime/spark-s3a-v1
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/rendered-runtime/spark-s3a-v1
kubectl --context k3d-dev -n finance-platform apply -f deploy/rendered-runtime/spark-s3a-v1
kubectl --context k3d-dev -n finance-platform rollout status deployment/jupyter --timeout=60s
```

### 실제 복구 검증

`configs/runtime/spark-checkpoint-smoke.py`의 두 모드를 **별도 Spark 프로세스**로 실행했다.
검증 prefix는 `platform-validation/spark-sync/60fa5e0c61d542f887b36cddcc524679`이며 업무 경로와 분리했다.
재실행 시에는 새 32자리 hex run ID를 만들어 두 모드에 동일하게 전달한다.

```sh
kubectl --context k3d-dev -n finance-platform exec -i deployment/jupyter -- python3 -u - write 60fa5e0c61d542f887b36cddcc524679 < configs/runtime/spark-checkpoint-smoke.py
kubectl --context k3d-dev -n finance-platform exec -i deployment/jupyter -- python3 -u - resume 60fa5e0c61d542f887b36cddcc524679 < configs/runtime/spark-checkpoint-smoke.py
```

| 검사 | 실제 결과 |
| --- | --- |
| S3A 스트리밍 최초 저장 | `CHECKPOINT_WRITE_PASS rows=3` |
| 별도 프로세스 checkpoint 복구 | `CHECKPOINT_RESUME_PASS rows=6`, 값 0~5 중복·누락 없음 |
| 실제 AWS SDK 클래스 위치 | `/opt/spark/jars/bundle-2.29.52.jar` |
| 같은 이미지의 Iceberg 쓰기·읽기 | `ICEBERG_WITH_S3A_PASS` |
| 검증 prefix와 합성 Iceberg 테이블 정리 | `PROBE_CLEANUP_PASS` |

SLF4J NOP binding 경고와 streaming에서 adaptive execution을 끄는 Spark 경고가 출력됐다.
Iceberg INFO에는 선택적 Flink FormatModel 등록 불가 메시지도 있었지만 이번 쓰기·읽기·복구 검증은 성공했다.
이는 전체 업무 변환의 호환성을 보장하는 검증은 아니다.

ConfigMap과 저장소의 두 설정 파일은 내용이 일치하며 실행 Pod의 SHA-256도 비교했다.
기존 업무 테이블·노트북 PVC를 재사용했고 두 streaming Deployment는 배포하지 않았다.
이벤트 로그는 로컬 파일로 생성되며 Pod 교체 시 사라진다. History Server·로그 영속 볼륨은 구성하지 않았다.
기존 원본 폴더는 수정하지 않았다. Docker Hub에는 이미지를 게시하지 않았다.

## 미사용 폴더 정리 — 2026-10-18

사용자 요청에 따라 Garage로 대체된 `configs/minio`, `configs/mc`,
`deploy/k8s/manifests/minio`를 삭제했다. 해당 파일은 모두 0바이트 scaffold였다.
업무 코드가 없고 `.gitkeep`만 있던 `workspace/pipelines`의 5개 하위 폴더도 제거했다.
실제 파이프라인 구현 시 필요한 경로만 새로 생성한다.

실제 파일이 있는 폴더의 중복 `.gitkeep`과 재생성 가능한 `deploy/rendered-runtime`의
YAML 출력물 10개(22,932바이트)도 정리했다. 위 실행 기록의 렌더링 경로는 당시 실행 이력이며,
재배포 시에는 renderer로 새 출력 디렉터리를 생성한다.

실행 중인 Kubernetes 리소스·Secret·PVC·Docker 이미지, 노트북·SQL·원본 manifest는 유지했다.

## 기사 파이프라인 구현 및 격리 검증 — 2026-10-18

원본 프로젝트의 Bronze→Silver·Silver→Gold Python 코드와 온톨로지를 이식했다.
테이블·체크포인트·실행 주기·배치 제한은 작업별 ConfigMap으로 분리했고,
Garage 및 Gemini 인증은 Secret 참조로 구성했다. `.env`는 복사하거나 이미지에 포함하지 않았다.
설정 검증 오류에도 API 키가 출력되지 않도록 처리했다.

| ARM64 이미지 | 로컬 이미지 ID | 상태 |
| --- | --- | --- |
| `finance-platform/article-bronze-to-silver:v1` | `0588c5b074bb` | 빌드·k3d 반입 완료 |
| `finance-platform/article-silver-to-gold:v1` | `fd52f9ebc7f0` | 빌드·k3d 반입 완료 |
| `finance-platform/article-pipelines-test:v2` | `660d1b3687c4` | 단위·격리 통합 검증용 |

Python 3.13.14와 잠금 파일의 의존성을 사용했다. 공통 Spark 설정은 Jupyter와 같은
`spark-config`를 마운트한다. 두 Deployment와 ConfigMap은 클러스터에 적용했으며
Deployment는 모두 `replicas: 0`이다. `gemini-credentials` Secret은 생성하지 않았다.
Docker Hub에는 게시하지 않았다.

네트워크를 끈 테스트 이미지에서 13개 테스트와 설정 관련 하위 사례 6개가 통과했다.
저장소 설정 도구 테스트도 12개 통과했다.
격리 Job `article-pipeline-offline-mnpv6`은 33초에 완료되었다.
실제 Spark·Iceberg·Garage를 사용하고 Gemini 전송 계층만 메모리 내 대역으로 교체했다.
실제 API 키나 외부 Gemini 호출은 사용하지 않았다.

| 검증 항목 | 출력 |
| --- | --- |
| Bronze 품질 필터·기사 식별 | `BRONZE_QUALITY_AND_IDENTITY_PASS` |
| S3A 체크포인트 재시작·수정 반영·중복 재처리 | `BRONZE_CHECKPOINT_UPDATE_REPLAY_PASS` |
| Gold RDF/SHACL 검증·재시작·중복 방지 | `GOLD_OFFLINE_VALIDATION_RESTART_REPLAY_PASS` |
| 쿼터 제한 상태 저장·복구 | `GOLD_DURABLE_QUOTA_RECOVERY_PASS` |
| 잘못된 모델 응답 제외 | `GOLD_INVALID_RESULT_REJECTED_PASS` |
| Silver 수정 전의 오래된 응답 제외 | `GOLD_STALE_RESULT_REJECTED_PASS` |
| 실제 호출 제외 | `NO_REAL_GEMINI_CALLS` |
| 소유한 검증 데이터 정리 | `OWNED_PROBE_DATA_CLEANED` |

최초 Job `article-pipeline-offline-dk9sf`은 foreachBatch 세션에서 커밋한 변경을
다른 Spark 세션의 테이블 캐시가 반영하지 않아 실패했다. 검증 코드와 Gold 조회 경로에
테이블 refresh를 추가한 뒤 위 Job으로 재검증했다. 첫 실패에서 남은 검증 디렉터리도 정리했다.
성공 Job의 전용 namespace `lakehouse.pipeline_smoke_8780ffecc1b44a6ab6374355116cc1b7`,
테이블·warehouse 디렉터리·체크포인트도 정리했다. 이후 Jupyter에서 업무 테이블 네 개가
모두 0행임을 다시 확인했다.

Gold는 원본의 `(article_id, ont_version)`별 최초 저장 동작을 유지한다.
이미 저장한 기사는 같은 버전에서 자동 재분석하지 않는다. 개별 잘못된 응답은 제외되고
완료 배치의 개별 응답을 자동 재시도하지 않는다. 실제 모델 응답·비용·서비스 쿼터와
업무 데이터의 장기 실행, 두 Deployment 동시 실행 자원은 검증하지 않았다.
활성화 명령과 환경변수 계약은 [파이프라인 안내](../pipelines/README.md)에 있다.
