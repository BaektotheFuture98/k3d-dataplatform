# PostgreSQL 실제 검증 기록 — 2026-10-18

대상: `kubectl --context k3d-dev -n finance-platform`.
비밀번호/Secret 값은 출력하거나 파일로 저장하지 않았다.

## 실행한 주요 명령

```bash
git status --short
git log -3 --oneline
rg --files --hidden -g '!.git/**'
kubectl --context k3d-dev -n finance-platform get pods,svc,statefulsets,deployments,pvc,jobs
kubectl --context k3d-dev get nodes -o wide
kubectl --context k3d-dev get storageclass local-path -o yaml
kubectl --context k3d-dev describe node k3d-dev-server-0
kubectl --context k3d-dev top nodes
docker info --format 'server={{.ServerVersion}} arch={{.Architecture}} cpu={{.NCPU}} memory={{.MemTotal}}'
colima status
k3d cluster list
docker manifest inspect postgres:17-bookworm
python3 configs/postgres/create-secret.py
kubectl --context k3d-dev -n finance-platform create --dry-run=server -f deploy/k8s/manifests/postgres/verify-job.yaml
kubectl --context k3d-dev -n finance-platform create -f deploy/k8s/manifests/postgres/verify-job.yaml
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/k8s/manifests/postgres/initdb-configmap.yaml -f deploy/k8s/manifests/postgres/service.yaml -f deploy/k8s/manifests/postgres/statefulset.yaml
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/postgres/initdb-configmap.yaml -f deploy/k8s/manifests/postgres/service.yaml -f deploy/k8s/manifests/postgres/statefulset.yaml
kubectl --context k3d-dev -n finance-platform rollout status statefulset/postgres --timeout=45s
kubectl --context k3d-dev -n finance-platform logs postgres-0 --tail=70
kubectl --context k3d-dev -n finance-platform create -f deploy/k8s/manifests/postgres/verify-job.yaml
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete job/postgres-verify-tfl7m --timeout=45s
kubectl --context k3d-dev -n finance-platform logs job/postgres-verify-tfl7m
kubectl --context k3d-dev -n finance-platform rollout restart statefulset/postgres
kubectl --context k3d-dev -n finance-platform rollout status statefulset/postgres --timeout=45s
kubectl --context k3d-dev -n finance-platform create --dry-run=client -f deploy/k8s/manifests/postgres/verify-job.yaml -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); env=d["spec"]["template"]["spec"]["containers"][0]["env"]; next(e for e in env if e["name"]=="EXPECT_TOKEN")["value"]="postgres-verify-tfl7m-rnpbd"; print(json.dumps(d))' | kubectl --context k3d-dev -n finance-platform create -f -
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete job/postgres-verify-llfcv --timeout=45s
kubectl --context k3d-dev -n finance-platform logs job/postgres-verify-llfcv
kubectl --context k3d-dev -n finance-platform exec postgres-0 -- bash /docker-entrypoint-initdb.d/10-platform-init.sh
kubectl --context k3d-dev -n finance-platform create -f deploy/k8s/manifests/postgres/verify-job.yaml
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete job/postgres-verify-7lgrt --timeout=30s
python3 configs/postgres/create-secret.py
git diff --check
```

Ruby `YAML.load_stream`으로 5개 리소스 문서(ConfigMap, Service 2개,
StatefulSet, Job)를 파싱하고 내장 shell 두 개를 `bash -n`으로 검증했다.
Python 기본 환경에는 PyYAML이 없어 설치 대신 기존 Ruby YAML 파서를 사용했다.

## 결과

| 항목 | 실제 결과 |
| --- | --- |
| 이미지 | PostgreSQL 17.11, linux/arm64, ARM64 manifest digest 고정 |
| Pod | `postgres-0` 1/1 Ready |
| PVC | `data-postgres-0` 10Gi local-path Bound |
| DB | `airflow_meta`, `iceberg_catalog`; 소유자 postgres |
| 전용 계정 | 양쪽 모두 Service DNS/TCP/SCRAM 인증과 DDL/DML 성공 |
| 제한 권한 | superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS 모두 false |
| 부정 검증 | 다른 앱 DB 접속과 잘못된 비밀번호 모두 거부 |
| 재시작 | Pod UID 변경, 동일 PVC/PV, 이전 토큰 두 DB 모두 확인 |
| 복구 스크립트 | 명시적 재실행 성공, 뒤이은 두 사용자 검증 Job 성공 |
| Secret 재실행 | 기존 Secret 보존 메시지, 비밀번호 교체 없음 |
| Endpoint | Ready=true, 재시작 후 `10.42.0.14:5432` |

Pod UID:
`b5680242-5c93-4bc2-b7e9-2f5255ce99af` → `d90a64ad-e7e3-4a1d-997a-0ec1f216d8a7`.

PVC UID는 재시작 전후 `6a3ff8a4-395a-4497-ab90-6737ec8005d8`로 동일하며,
PV는 `pvc-6a3ff8a4-395a-4497-ab90-6737ec8005d8`로 동일했다.

## 실패와 한계

- `postgres-verify-zzlqs`: 배포 전 의도한 실패. Service DNS가 아직 없음.
- `postgres-verify-hw2vr`: Ready 전에 실행하여 connection refused로 실패.
  이후 rollout 완료를 기다린 `postgres-verify-tfl7m`은 Complete 1/1.
- `postgres-verify-llfcv`: 재시작 후 이전 토큰 검증 Complete 1/1.
- `postgres-verify-7lgrt`: 복구 스크립트 재실행 후 Complete 1/1.
- 샌드박스의 로컬 API/소켓 접근 거부는 승인된 외부 실행으로 해결했다.
- zsh의 따옴표 없는 `[0]` JSON 필드 경로 조회는 glob 오류가 발생했다.
  인자를 작은따옴표로 감싸 재조회했고 Ready와 새 UID를 확인했다.
- backup/restore, 노드 장애, 디스크 유실 복구, 강제 초기화 실패 주입은 미검증.
- 업무 기사 데이터 파이프라인과 후속 서비스는 이 검증의 대상이 아니다.
- 독립 정적 리뷰에서 Critical/Important 없음. 부정 접속 테스트가 정확한
  서버 오류 대신 모든 접속 실패를 수용한다는 Minor 한계가 있다.
