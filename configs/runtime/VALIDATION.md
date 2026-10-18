# 기반 서비스 실제 실행 검증 — 2026-10-18

## 범위와 현재 결과

사용자의 최신 요청은 **데이터 파이프라인 생성만 제외하고 실행**하는 것이다.
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
서비스별 EndpointSlice 주소가 존재한다. CronJob 및 업무 Deployment는 없다.
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
업무 Bronze/Silver/Gold 테이블이나 기사 그래프를 만들지 않았다.

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

외부 포트는 공개하지 않았다. 필요한 UI만 별도 터미널에서 로컬로 전달한다.

```sh
kubectl --context k3d-dev -n finance-platform port-forward service/airflow-api-server 8080:8080
kubectl --context k3d-dev -n finance-platform port-forward service/jupyter 8888:8888
kubectl --context k3d-dev -n finance-platform logs deployment/iceberg-rest --tail=100
kubectl --context k3d-dev -n finance-platform logs deployment/airflow-scheduler -c scheduler --tail=100
kubectl --context k3d-dev -n finance-platform logs deployment/jupyter --tail=100
kubectl --context k3d-dev -n finance-platform logs neo4j-0 --tail=100
```

UI는 Airflow `http://127.0.0.1:8080`, Jupyter `http://127.0.0.1:8888`이다.
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
