# k3d-dataplatform

Mac/Colima/k3d 단일 노드 개발 환경. 모든 앱은 `finance-platform`에서 실행한다.
기존 `dev` 클러스터, Namespace, `local-path` StorageClass를 그대로 사용한다.

이전 작업에서 **Phase 1 PostgreSQL과 Phase 2 Garage(S3)를 실제 배포·검증**했다.
이후 사용자 지시에 따라 **후속 서비스는 파일만 구성하고 배포·실행하지 않는다**.
MinIO는 요청에 따라 Garage로 대체했다. 파이프라인 이미지는 사용자가 나중에 Docker Hub에 게시한다.
아래 배포·빌드 명령은 과거 기록 또는 향후 수동 실행 절차이며 이번 파일 구성 작업에서 실행하지 않았다.
기존 PostgreSQL/Garage를 이번 작업에서 중지하거나 변경하지 않았다.

## 목표 아키텍처와 설치 순서

```text
Airflow → Article Collector Job → Iceberg Bronze
  → Spark Bronze→Silver → Iceberg Silver
  → Spark Silver→Gold → Iceberg Gold
  → Gold Publisher → Kafka article-gold → Kafka Connect → Neo4j → Service API

PostgreSQL: Airflow 메타데이터 + Iceberg JDBC Catalog 메타데이터
Iceberg REST: 수집기/Spark의 Catalog API → PostgreSQL
Garage: Iceberg 데이터 파일, 메타데이터 JSON, Streaming Checkpoint
```

Iceberg는 테이블 포맷이다. PostgreSQL에 실제 Iceberg 데이터 파일을 저장하지 않는다.

| Phase | 서비스 및 역할 | 선행 조건 | 현재 상태 |
| --- | --- | --- | --- |
| 1 | PostgreSQL: 두 메타데이터 DB | 기존 Namespace/StorageClass | 검증 완료 |
| 2 | Garage: 비공개 `warehouse` 버킷 | 공식 ARM64 이미지 | S3 객체 및 multipart 검증 완료 |
| 3 | Iceberg REST: Catalog API | PostgreSQL + Garage | Dockerfile/Manifest 준비, 실행 미검증 |
| 4 | Spark/Jupyter와 독립 streaming 배포 설정 | Spark 4.1.2/Iceberg 1.11.0 + Catalog | 설정 준비, 알려진 호환성 이슈 기록, 실행 미검증 |
| 5 | Airflow/Collector: Kubernetes Job 오케스트레이션 | DB + Catalog + 사용자 이미지 + RBAC | values/DAG/Job/RBAC 준비, 수집 앱 외부 제공 |
| 6 | Strimzi/Kafka/Connect: 이벤트 전달 | 관리자 설치 CRD/RBAC + Sink 이미지 | values/CR/Dockerfile 준비, 실행 미검증 |
| 7 | Neo4j: 그래프 저장 | 공식 Chart + 인증/PVC | values/내부 Service/constraint 준비, 실행 미검증 |
| 8 | Publisher/전체 연동 | 사용자 업무 이미지 + 변경 추적/중복 제어 | 중지된 CronJob·이벤트 계약 준비, 업무 처리 미구현 |

2026-10-18 관측: ARM64, 노드 CPU 2개, 메모리 `8112900Ki`(약 7.7GiB).
전체 서비스를 동시에 실행할 수 있는 자원은 아직 검증하지 않았다. 이후 단계마다
requests 합계, 실제 사용량, Pending/OOM/CPU throttling을 확인한다. 단일 노드는 HA가 아니다.
현재 Helm 실행 파일은 PATH에 없으며 후속 Helm 단계 전에 설치가 필요하다.

## PostgreSQL 파일과 리소스

| 파일 | 역할과 설계 근거 |
| --- | --- |
| `deploy/k8s/manifests/postgres/initdb-configmap.yaml` | 최초 DB/역할 생성. 오류 즉시 종료, 완료 마커, 명시적 복구를 위한 누락 객체 생성 |
| `deploy/k8s/manifests/postgres/service.yaml` | 내부 TCP 접속용 `postgres`, StatefulSet governing Service인 `postgres-headless` |
| `deploy/k8s/manifests/postgres/statefulset.yaml` | PostgreSQL 17 단일 Pod와 `local-path` 10Gi PVC, Secret 마운트, probes, PVC Retain |
| `deploy/k8s/manifests/postgres/verify-job.yaml` | 별도 Pod에서 DNS/TCP/인증/권한/DDL/DML/보존 토큰 검증. 매번 새 Job 생성 |
| `configs/postgres/create-secret.py` | 비밀번호를 메모리에서 생성해 stdin으로 Secret 생성. 기존 Secret 보존 |
| `configs/postgres/PLAN.md` | 의존성, 실행 순서, 검토 조건 |
| `configs/postgres/VALIDATION.md` | 실제 실행 명령과 성공/실패 증거 |
| `.gitignore` | 로컬 인증 파일과 DB 백업의 실수 커밋 방지 |

실제 리소스: `StatefulSet/postgres`, `Pod/postgres-0`, `PVC/data-postgres-0`,
`ConfigMap/postgres-initdb`, `Secret/postgres-credentials`, Service 2개, 검증 Job들.
애플리케이션 포트는 ClusterIP 5432이며 NodePort/LoadBalancer를 만들지 않는다.

이미지는 ARM64 manifest digest로 고정했다. 실제 실행 버전은 PostgreSQL **17.11**이다.
다른 아키텍처에서는 해당 아키텍처를 검증한 manifest 또는 multi-arch index digest로 바꿔야 한다.
requests는 100m CPU/256Mi, limits는 1 CPU/512Mi다. `shared_buffers=128MB`,
`max_connections=60`; 후속 서비스 연결 풀의 총 연결 수를 이 범위에 맞춘다.

## 설치 및 배포

프로젝트 루트에서 실행한다. 기존 Namespace와 StorageClass를 재적용하지 않는다.

```bash
kubectl --context k3d-dev -n finance-platform get pods,svc,statefulsets,pvc
kubectl --context k3d-dev get nodes -o wide
kubectl --context k3d-dev get storageclass local-path
python3 configs/postgres/create-secret.py

kubectl --context k3d-dev -n finance-platform apply --dry-run=server \
  -f deploy/k8s/manifests/postgres/initdb-configmap.yaml \
  -f deploy/k8s/manifests/postgres/service.yaml \
  -f deploy/k8s/manifests/postgres/statefulset.yaml

kubectl --context k3d-dev -n finance-platform apply \
  -f deploy/k8s/manifests/postgres/initdb-configmap.yaml \
  -f deploy/k8s/manifests/postgres/service.yaml \
  -f deploy/k8s/manifests/postgres/statefulset.yaml
kubectl --context k3d-dev -n finance-platform rollout status statefulset/postgres --timeout=180s
```

검증 Job은 `generateName`을 사용하므로 `apply` 대상에 포함하지 않는다.
`kubectl apply -f deploy/k8s/manifests/postgres/`처럼 디렉터리 전체를 적용하지 않는다.

Secret 이름은 `postgres-credentials`, 키는 `postgres-password`, `airflow-password`,
`iceberg-password`다. 실제 Secret YAML, 비밀번호, URI를 Git에 저장하거나 출력하지 않는다.
생성 스크립트는 기존 Secret을 교체하지 않고, PVC만 남은 상황에서는 새 인증 정보 생성을 거부한다.
다른 서비스에서는 필요한 키만 `secretKeyRef`로 참조한다.

| 사용자 | 접속 DB | 권한 |
| --- | --- | --- |
| `postgres` | 관리용 | bootstrap 관리자, 앱에서 사용 금지 |
| `airflow_user` | `airflow_meta` | CONNECT/TEMP, public 스키마 USAGE/CREATE, 자신이 만든 객체 관리 |
| `iceberg_user` | `iceberg_catalog` | CONNECT/TEMP, public 스키마 USAGE/CREATE, 자신이 만든 객체 관리 |

DB 소유자는 `postgres`다. 전용 계정은 superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS를
갖지 않는다. PUBLIC의 기본 CONNECT와 public 스키마 권한을 제거했다.
네트워크 인증은 SCRAM-SHA-256이며, 관리용 Unix socket만 컨테이너 내부 trust다.
Secret은 비밀번호 관리 수단이며 기본 Kubernetes Secret 자체가 암호화 저장을 보장하지는 않는다.

## 검증과 데이터 보존 테스트

반드시 rollout 완료 후 Job을 생성한다. 아래 명령은 bash/zsh에서 사용 가능하다.

```bash
VERIFY_JOB=$(kubectl --context k3d-dev -n finance-platform create \
  -f deploy/k8s/manifests/postgres/verify-job.yaml -o jsonpath='{.metadata.name}')
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete "job/$VERIFY_JOB" --timeout=120s
kubectl --context k3d-dev -n finance-platform logs "job/$VERIFY_JOB"
PERSIST_TOKEN=$(kubectl --context k3d-dev -n finance-platform get pods \
  -l "batch.kubernetes.io/job-name=$VERIFY_JOB" -o jsonpath='{.items[0].metadata.name}')

kubectl --context k3d-dev -n finance-platform get pvc data-postgres-0 \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,PV:.spec.volumeName,STATUS:.status.phase
kubectl --context k3d-dev -n finance-platform get pod postgres-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid
kubectl --context k3d-dev -n finance-platform rollout restart statefulset/postgres
kubectl --context k3d-dev -n finance-platform rollout status statefulset/postgres --timeout=180s

# 이전 Job의 토큰을 새 Job에 전달한다. 이 토큰은 비밀번호가 아닌 테스트 데이터다.
PERSIST_JOB=$(kubectl --context k3d-dev -n finance-platform create --dry-run=client \
  -f deploy/k8s/manifests/postgres/verify-job.yaml -o json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); env=d["spec"]["template"]["spec"]["containers"][0]["env"]; next(e for e in env if e["name"]=="EXPECT_TOKEN")["value"]=sys.argv[1]; print(json.dumps(d))' "$PERSIST_TOKEN" \
  | kubectl --context k3d-dev -n finance-platform create -f - -o jsonpath='{.metadata.name}')
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete "job/$PERSIST_JOB" --timeout=120s
kubectl --context k3d-dev -n finance-platform logs "job/$PERSIST_JOB"
kubectl --context k3d-dev -n finance-platform get pvc data-postgres-0 \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,PV:.spec.volumeName,STATUS:.status.phase
kubectl --context k3d-dev -n finance-platform get pod postgres-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid
```

두 DB의 `public.platform_validation_persistence_probe`에 테스트 토큰을 유지한다.
임시 DML 테이블은 같은 트랜잭션 안에서 삭제한다. 보존 토큰은 다음 검증에 사용한다.
Job은 성공·실패 모두 24시간 뒤 TTL로 정리된다. 병렬 실행하지 말고 순서대로 실행한다.
이는 인프라 검증이며 실제 기사 파이프라인 검증이 아니다.

## 상태·로그·초기화 실패

```bash
kubectl --context k3d-dev -n finance-platform get pods,pvc,svc,endpointslices
kubectl --context k3d-dev -n finance-platform describe pod postgres-0
kubectl --context k3d-dev -n finance-platform logs postgres-0 --tail=100
kubectl --context k3d-dev -n finance-platform logs postgres-0 --previous
kubectl --context k3d-dev -n finance-platform get events --sort-by=.lastTimestamp
kubectl --context k3d-dev -n finance-platform exec postgres-0 -- \
  psql -X -U postgres -d postgres -c "SELECT datname FROM pg_database WHERE datname IN ('airflow_meta','iceberg_catalog');"
```

초기화 스크립트는 빈 PGDATA에서만 자동 실행된다. `PG_VERSION`이 있으면 컨테이너
재시작 시 자동 재실행하지 않는다. 실패하면 로그의 행 번호와 DB/role 상태부터 확인한다.
완료 마커가 없으면 Ready가 되지 않고 Service의 Ready endpoint에 포함되지 않는다.
PVC를 삭제해서 해결하지 않는다. `--previous` 로그는 이전 컨테이너가 있을 때만 조회된다.

원인을 수정하고 기존 데이터와 인증 정보의 일치를 확인한 뒤, 명시적으로 복구할 때만:

```bash
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/postgres/initdb-configmap.yaml
# 변경한 ConfigMap이 마운트 경로에 반영된 것을 확인한 뒤 실행한다.
kubectl --context k3d-dev -n finance-platform exec postgres-0 -- bash /docker-entrypoint-initdb.d/10-platform-init.sh
```

복구 스크립트는 누락된 DB/role을 생성하고 정의된 권한을 설정한다. 기존 role의 비밀번호와
기존 DB의 소유자는 변경하지 않는다. 기존의 추가 권한을 모두 감사·제거하는 기능은 아니다.
기존 데이터에 마커가 없어도 자동으로 안전하다고 간주하지 않고 같은 확인 절차를 따른다.
Secret 갱신만으로 기존 role의 SQL 비밀번호가 바뀌지는 않는다. 비밀번호 교체 시 SQL과 Secret을
일치시키고, 관련 앱을 재시작하여 인증을 검증한다.

민감한 SQL의 오류 로그 출력을 막기 위해 `log_statement=none`,
`log_min_error_statement=panic`을 사용한다. 오류 본문과 스크립트 행 번호는 남지만 실패 SQL
전체는 기록하지 않는다. SQL echo와 shell의 `set -x`를 활성화하지 않는다.

## 백업·재배포·업그레이드

local-path의 PV reclaimPolicy는 **Delete**다. StatefulSet의 PVC retention은 Retain이지만,
PVC를 직접 삭제하면 PV와 데이터도 삭제될 수 있다. PVC 자동 확장은 지원하지 않는다.
Pod 재생성 시 보존은 확인했으나 클러스터/Colima VM/호스트 디스크 유실에서의 복구는 보장하지 않는다.

논리 백업 예시(안전한 로컬 경로에서 실행하고 별도 저장장치에도 보관):

```bash
umask 077
mkdir -p /private/tmp/finance-platform-backup
kubectl --context k3d-dev -n finance-platform exec postgres-0 -- pg_dump -U postgres -d airflow_meta -Fc > /private/tmp/finance-platform-backup/airflow_meta.dump
kubectl --context k3d-dev -n finance-platform exec postgres-0 -- pg_dump -U postgres -d iceberg_catalog -Fc > /private/tmp/finance-platform-backup/iceberg_catalog.dump
```

백업·복원 실행 및 복원 테스트는 아직 수행하지 않았다. 위 명령은 절차 예시다.
역할과 Secret은 별도로 안전한 비밀 관리 저장소에 보관한다. 백업에는 내부 데이터가 들어갈 수 있다.
복원은 별도 DB에서 검증한 뒤 기존 DB에 적용한다.

재배포는 동일한 3개 Manifest를 dry-run/apply한다. ConfigMap 변경은 기존 DB의 migration이
아니다. SQL migration은 별도로 검토하여 적용한다. minor 업데이트도 백업 → ARM64
manifest/version 확인 → digest 수정 → rollout → 동일 검증 Job 순서로 진행한다.
major 업데이트는 이미지 변경만으로 수행하지 않고 pg_upgrade/논리 이관을 별도 계획한다.

## 다음 작업과 확인된 의존성 문제

2026-10-18 다음 공식 태그를 `docker manifest inspect`로 조회했으나 확보하지 못했다.

- Docker Hub: `minio/minio:RELEASE.2025-09-07T16-13-09Z`, `minio/mc:RELEASE.2025-08-13T08-35-41Z` → denied/unauthorized
- Quay: 동일 태그의 `quay.io/minio/minio`, `quay.io/minio/mc` → no such manifest

로컬 Docker에는 두 ARM64 캐시가 있고 바이너리 버전도 확인했다. 다만 MinIO server는
`2025-09-07`로, 이후 [공식 보안 수정 릴리스](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z)
이전 버전이다. [공식 저장소](https://github.com/minio/minio)는 현재 archive 상태이며,
Community Edition은 소스만 배포한다고 안내한다.

사용자 요청에 따라 MinIO를 Garage로 대체했다. 기존 빈 `minio/` 경로는 유지하며 배포하지 않는다.
새 파일은 `configs/garage/`, `deploy/k8s/manifests/garage/`, `docker/s3-check/`에 작성했다.
공식 `dxflrs/garage:v2.4.1`의 ARM64 manifest를 검증해 digest로 고정했고 실제 기동했다.
MinIO 이미지 의존성 문제는 Garage 대체로 해소됐다.

이후에는 처음의 순서를 따른다. 검증하지 않은 Helm values/CRD 필드나 fixture를
실서비스 구현으로 간주하지 않는다.

PostgreSQL 구성에는 [공식 Docker 이미지 초기화 명세](https://hub.docker.com/_/postgres)와
[PostgreSQL 17 GRANT 문서](https://www.postgresql.org/docs/17/sql-grant.html)를 참조했다.


## Garage 구성과 배포

[공식 단일 노드 안내](https://github.com/deuxfleurs-org/garage/blob/v2.4.1/doc/book/quick-start/_index.md)와
[S3 호환성 문서](https://github.com/deuxfleurs-org/garage/blob/v2.4.1/doc/book/reference-manual/s3-compatibility.md)를
기준으로 구성했다. 기본 S3 객체 작업과 멀티파트는 실제 Job으로 검증했다.
Iceberg 테이블 생성과 Spark 체크포인트는 Phase 3/4에서 별도로 검증해야 한다.
Garage는 모든 AWS S3 기능을 지원하지 않으며 IAM 정책/ACL/버전 관리 기능에 의존하지 않는다.

| 파일 | 역할 |
| --- | --- |
| `configs/garage/garage.toml` | 비민감 설정 원본: 단일 노드, region, storage 경로 |
| `configs/garage/create-secret.py` | 최초 RPC/admin/S3 키 생성; 기존 Secret/PVC 보존 |
| `configs/garage/s3-check.py` | 반복 가능한 버킷 초기화와 실제 객체/멀티파트/익명 접근/보존 테스트 |
| `configs/garage/render-configmaps.rb` | 설정과 검증 코드를 Manifest ConfigMap으로 렌더링 |
| `configs/garage/PLAN.md`, `VALIDATION.md` | 설계·실행 계획과 실제 검증 기록 |
| `deploy/k8s/manifests/garage/configmap.yaml`, `check-configmap.yaml` | 원본에서 생성한 비민감 ConfigMap |
| `deploy/k8s/manifests/garage/statefulset.yaml` | Garage 1개, LMDB metadata+objects용 10Gi PVC Retain |
| `deploy/k8s/manifests/garage/service.yaml` | S3용 ClusterIP와 StatefulSet용 Headless Service |
| `deploy/k8s/manifests/garage/init-bucket-job.yaml` | 매번 새 이름으로 실행하는 버킷/S3 검사 Job |
| `docker/s3-check/Dockerfile` | ARM64 Python base digest + boto3/botocore 고정 검증 이미지 |

설정 원본 수정 후 renderer를 실행한다. TOML은 subPath 마운트하므로 ConfigMap을 변경해도
기존 Pod 파일은 자동 갱신되지 않는다. ConfigMap 적용 후 명시적으로 rollout restart한다.

```bash
ruby configs/garage/render-configmaps.rb
python3 configs/garage/create-secret.py

docker build --platform linux/arm64 -t finance-platform/s3-check:boto3-1.40.59-v1 docker/s3-check
k3d image import finance-platform/s3-check:boto3-1.40.59-v1 --cluster dev

kubectl --context k3d-dev -n finance-platform apply --dry-run=server \
  -f deploy/k8s/manifests/garage/configmap.yaml \
  -f deploy/k8s/manifests/garage/check-configmap.yaml \
  -f deploy/k8s/manifests/garage/service.yaml \
  -f deploy/k8s/manifests/garage/statefulset.yaml
kubectl --context k3d-dev -n finance-platform apply \
  -f deploy/k8s/manifests/garage/configmap.yaml \
  -f deploy/k8s/manifests/garage/check-configmap.yaml \
  -f deploy/k8s/manifests/garage/service.yaml \
  -f deploy/k8s/manifests/garage/statefulset.yaml
kubectl --context k3d-dev -n finance-platform rollout status statefulset/garage --timeout=180s
kubectl --context k3d-dev -n finance-platform create --dry-run=server -f deploy/k8s/manifests/garage/init-bucket-job.yaml
GARAGE_JOB=$(kubectl --context k3d-dev -n finance-platform create \
  -f deploy/k8s/manifests/garage/init-bucket-job.yaml -o jsonpath='{.metadata.name}')
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete "job/$GARAGE_JOB" --timeout=180s
kubectl --context k3d-dev -n finance-platform logs "job/$GARAGE_JOB"
```

Job 파일은 `generateName`이므로 apply 대상에 넣지 않는다. 검사 이미지는 `imagePullPolicy: Never`여서
k3d import가 선행되어야 한다. Job의 코드만 변경하면 ConfigMap 재렌더링/적용으로 충분하다.
의존성을 변경할 때는 Dockerfile과 이미지 태그를 함께 갱신해 build/import한다.

S3 endpoint는 `http://garage.finance-platform.svc.cluster.local:3900`, region은 `garage`,
버킷은 `warehouse`다. 이후 S3FileIO/SDK에서 SigV4와 path-style을 사용한다.
`garage-credentials` Secret의 `s3-access-key-id`, `s3-secret-access-key`만 앱에 주입한다.
`rpc-secret`, `admin-token`은 Garage 자체에서만 사용한다. Secret을 직접 출력하지 않는다.
초기 개발용 S3 키에는 warehouse의 read/write/owner 및 bucket 생성 권한이 있다.
공유 개발 환경에서 앱별 권한 격리가 필요하면 Garage Admin API/CLI로 별도 키를 발급한다.

요청 자원은 100m CPU/128Mi, 상한은 500m CPU/512Mi다. replica는 1이며 HA가 아니다.
LMDB와 객체 파일을 모두 같은 PVC에 저장한다. local-path의 10Gi는 PVC 요청량이며 실제
파일시스템 quota를 강제하지 않으므로 디스크 사용량도 확인해야 한다.
관리 포트는 Service로 제공하지 않는다. readiness는 관리 HTTP `/health`, startup/liveness는
S3 TCP로 검사한다. 기본 키 ID가 로그에 남지 않도록 로그 레벨은 warn으로 설정했다.

```bash
kubectl --context k3d-dev -n finance-platform get pods,pvc,svc -l app.kubernetes.io/name=garage
kubectl --context k3d-dev -n finance-platform exec garage-0 -- /garage status
kubectl --context k3d-dev -n finance-platform logs garage-0 --tail=100
kubectl --context k3d-dev -n finance-platform describe pod garage-0
```

재시작 보존 검증은 Job 로그의 `Persistence object` 값을 새 Job의 `EXPECT_KEY` 환경변수에
넣어 수행한다. `kubectl create --dry-run=client -f ... -o json`의 Job 객체에서 해당 env 값을
수정해 `kubectl create -f -`로 생성한다. 실제로 사용한 객체와 명령은
[Garage 검증 기록](configs/garage/VALIDATION.md)에 있다. 검사 객체는 `platform-validation/`에 남긴다.

Secret을 잃으면 신규 키를 생성해 PVC의 기존 키와 불일치시키지 말고 원래 Secret을 복원한다.
`--single-node --default-bucket`은 기존 metadata가 있으면 같은 layout/key/bucket을 재사용하며,
기존 키와 Secret이 다르면 시작을 거부한다. layout을 임의로 재적용하거나 metadata를 지우지 않는다.
업그레이드는 백업, 공식 migration 안내 확인, 이미지 digest 변경, rollout 및 같은 검증 순서다.
Garage 데이터 백업은 metadata와 data를 함께 보존해야 한다. 정지 또는 일관된 snapshot 기반
백업·복원 절차의 실제 복구 테스트는 아직 하지 않았다. PVC/VM/클러스터 삭제는 백업이 아니다.


## 후속 서비스 파일 준비와 사용자 이미지 연결

`configs/IMPLEMENTATION-PLAN.md`에 작업 범위와 서비스 계약을 정리했다.
Catalog·Spark, Kafka·Neo4j, Airflow·파이프라인 설정은 `gpt-6.1-sol / low` 서브에이전트가
병렬 작성했고 주 에이전트가 서비스명·Secret·이미지·스키마와 변경 내용을 검토했다.

| 구성 | 상세 문서 |
| --- | --- |
| JDBC Catalog REST fixture / Spark / 인증 Jupyter | [Catalog·Spark](configs/spark/README.md) |
| 공식 Airflow chart / LocalExecutor / Job RBAC / DAG 전달 | [Airflow](configs/airflow/README.md) |
| 수집·변환·발행 이미지 ENTRYPOINT와 환경변수 계약 | [파이프라인](configs/pipelines/README.md) |
| Strimzi / Kafka / Connect 플러그인과 이벤트 스키마 | [Kafka](configs/kafka/README.md) |
| Community Neo4j / PVC / 내부 Service / 제약 조건 | [Neo4j](configs/neo4j/README.md) |

실제 기사 수집·변환·Gold 변경 발행 코드는 작성된 것으로 간주하지 않는다.
`workspace/pipelines/`의 빈 경로는 그대로 남겼다. 업무 이미지는 위 파이프라인 문서의
ENTRYPOINT/env/schema 계약을 구현해서 Docker Hub에 게시해야 한다.
Service API 또한 이번 범위에서 구현하지 않았다.

이미지 주소는 `configs/platform-images.env.example`을 복사해 작성한다. 비밀번호를 넣는 파일이 아니다.
`__ARTICLE_COLLECTOR_IMAGE__` 등 미확정 값이 하나라도 남으면 renderer는 생성을 거부한다.
Airflow는 전체 `AIRFLOW_IMAGE`에서 chart의 repository와 tag를 자동 분리한다.
해당 chart 매핑에서는 Airflow 이미지에 명시적인 tag가 필요하다.
다른 이미지에는 tag 또는 sha256 digest를 쓸 수 있다. `latest`는 허용하지 않는다.

```bash
# 아래는 나중에 실제 이미지 주소를 작성한 뒤 사용하는 파일 렌더링 예시다.
cp configs/platform-images.env.example configs/platform-images.env
# configs/platform-images.env의 YOUR_DOCKERHUB_ACCOUNT와 tag를 수정한다.
python3 scripts/render-manifests.py --source deploy/k8s \
  --values configs/platform-images.env --output deploy/rendered-review
```

렌더링은 새로운 디렉터리에 YAML만 작성한다. kubectl/helm/Docker를 호출하지 않는다.
기존 출력 디렉터리는 덮어쓰지 않으므로 재검토 시 새 출력 경로를 지정한다.
렌더링 대상에는 Helm values, 명시적 실행용 Job, 기존 Namespace 파일도 포함된다.
**출력 디렉터리 전체를 재귀 apply하지 않는다.** 서비스별 명령을 검토하고 필요한 파일만 선택한다.
이미지 설정 파일과 출력 디렉터리는 Git에서 제외했다.

Secret 준비용 `configs/prepare-secrets.py`도 작성했지만 실제 생성하지 않았다.
기본 모드는 계획 출력만 하며 API에 접근하거나 난수를 생성하지 않는다.
향후 사용자가 `--apply --component airflow|jupyter|neo4j`를 명시할 때만 누락된 Secret을 생성한다.
기존 Secret은 유지한다. Airflow 연결 URL은 기존 PostgreSQL Secret에서 메모리로 읽어 URL-encode하고,
Neo4j는 chart용 `NEO4J_AUTH`와 Connect용 `neo4j-password`를 동일한 비밀번호로 만든다.
Neo4j PVC만 남은 상태에서는 새 인증 정보 생성을 거부한다.

후속 설치 순서는 다음과 같다. 아래 절차는 이번에 수행하지 않았다.

1. 게시된 이미지 주소·아키텍처·태그를 확정하고 YAML을 렌더링한다.
2. 기존 DB/비공개 warehouse와 필요한 Secret을 준비한다.
3. Catalog를 배포하고 namespace/table 생성과 실제 S3 파일 write/read를 검증한다.
4. Spark/Jupyter를 개별 검증한다. 기본 Spark 4.1/Iceberg 1.11.0에는
   [선택적 Flink 클래스 로딩 문제 보고](https://github.com/apache/iceberg/issues/16856)가 있어
   실행 전 확인해야 한다. 임의로 버전을 올리거나 Flink를 섞어 해결한 것으로 처리하지 않았다.
5. Airflow RBAC 및 고정 chart values를 검토하고 설치한다. DB migration은 설치 시 실행될 수 있다.
   DAG는 최초 paused/schedule 없음이며 수집 앱 이미지를 확인한 뒤 수동으로 실행한다.
6. 관리자가 Strimzi CRD와 클러스터 RBAC를 별도 승인·설치한 뒤 namespace operator/Kafka/Topic을 적용한다.
7. Neo4j chart를 설치하고 인증·제약 조건을 검증한 후 Connect를 활성화한다.
8. 개별 pipeline의 실제 코드·checkpoint·재처리 계약을 검증한 뒤 streaming replicas와 publisher suspend를 변경한다.

두 streaming Deployment는 replicas=0, publisher CronJob은 suspend=true, Connect는 replicas=0,
Connector는 stopped 상태다. Jupyter도 필요할 때만 켜도록 replicas=0이다.
Neo4j chart는 이후 설치하면 Community DB를 시작한다. `operations.enableServer=false`는 Enterprise
클러스터 관리 Job 설정이며 Community 서버를 중지하는 값이 아니다.
이 설정은 나중에 적용해도 파이프라인이 자동으로 정상 처리된다는 의미가 아니다.
수집 Job은 명시적으로 생성할 때 실행되므로 일반 인프라 apply 묶음에서 제외한다.

Jupyter와 업무 파이프라인을 제외한 장기 실행 앱의 선언된 CPU requests는 약 1700m이며,
기존 kube-system requests 200m를 더하면 약 1900m다. Helm hook/init/sidecar 및 향후 chart
렌더링 결과에 따라 더 필요할 수 있다. 두 streaming(각 250m)과 Connect(100m)를 켜면
총 약 2500m가 되어 현재 2 CPU를 초과한다. 동시에 켜기 전 자원 또는 실행 방식을 조정해야 한다.
전체 동시 실행은 단일 노드 2 CPU/약 7.7GiB에서 검증하지 않았다. 특히 Jupyter/두 Spark 작업,
Kafka/Connect/Neo4j/Airflow를 모두 켜기 전에 requests 합계와 JVM/Python 메모리 여유를 계산해야 한다.
필요하면 독립 검증 순서를 사용하고 업무 파이프라인 전체 실행 성공을 주장하지 않는다.

## 이번 작업의 정적 검증

실행한 검증은 로컬 파일 검사뿐이다.

```bash
ruby scripts/check-configs.rb
python3 -m unittest discover -s tests -v
git diff --check
```

Python 소스 전체의 AST 구문과 Dockerfile 보조 checksum parser의 형식도 검사했다.
파일 renderer의 누락 이미지 거부·기존 파일 보존·경로 겹침 방지·Airflow repository/tag 변환,
Secret helper의 URL 인코딩·Neo4j 두 인증 키 일치 등을 fixture 값으로 검증했다.
실제 Secret 값은 사용하지 않았다. 상세 결과는 [정적 검증 기록](configs/STATIC-VALIDATION.md)에 있다.

Helm template 실행, CRD 서버 schema 검증, 이미지 빌드와 다운로드 결과, DAG import,
서비스 연결·기사 수집부터 Neo4j까지의 실행은 이번 작업에서 검증하지 않았다.
