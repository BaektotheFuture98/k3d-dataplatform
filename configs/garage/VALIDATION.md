# Garage 실제 검증 기록 — 2026-10-18

사용자가 MinIO를 Garage로 대체하도록 지시했다. 기존 클러스터/Namespace/
StorageClass 및 PostgreSQL은 보존했다. MinIO 워크로드는 배포하지 않았다.

## 실제 실행한 주요 명령

```bash
docker manifest inspect dxflrs/garage:v2.4.1
docker manifest inspect python:3.12-slim-bookworm
ruby configs/garage/render-configmaps.rb
python3 configs/garage/create-secret.py
docker build --platform linux/arm64 -t finance-platform/s3-check:boto3-1.40.59-v1 docker/s3-check
k3d image import finance-platform/s3-check:boto3-1.40.59-v1 --cluster dev
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/k8s/manifests/garage/configmap.yaml -f deploy/k8s/manifests/garage/check-configmap.yaml -f deploy/k8s/manifests/garage/service.yaml -f deploy/k8s/manifests/garage/statefulset.yaml
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/garage/configmap.yaml -f deploy/k8s/manifests/garage/check-configmap.yaml
kubectl --context k3d-dev -n finance-platform create --dry-run=server -f deploy/k8s/manifests/garage/init-bucket-job.yaml
kubectl --context k3d-dev -n finance-platform create -f deploy/k8s/manifests/garage/init-bucket-job.yaml
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/garage/service.yaml -f deploy/k8s/manifests/garage/statefulset.yaml
kubectl --context k3d-dev -n finance-platform rollout status statefulset/garage --timeout=45s
kubectl --context k3d-dev -n finance-platform get events --field-selector involvedObject.name=garage-0 --sort-by=.lastTimestamp
kubectl --context k3d-dev -n finance-platform logs garage-0 --tail=20
# 시작 실패 수정본 적용. 실패한 Pod 때문에 갱신이 대기하여 Pod만 재생성했다.
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/garage/configmap.yaml -f deploy/k8s/manifests/garage/statefulset.yaml
kubectl --context k3d-dev -n finance-platform delete pod garage-0 --wait=true
kubectl --context k3d-dev -n finance-platform rollout status statefulset/garage --timeout=45s
kubectl --context k3d-dev -n finance-platform exec garage-0 -- /garage status
kubectl --context k3d-dev -n finance-platform create -f deploy/k8s/manifests/garage/init-bucket-job.yaml
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete job/garage-s3-check-l46hf --timeout=45s
kubectl --context k3d-dev -n finance-platform logs job/garage-s3-check-l46hf
python3 configs/garage/create-secret.py
kubectl --context k3d-dev -n finance-platform rollout restart statefulset/garage
kubectl --context k3d-dev -n finance-platform rollout status statefulset/garage --timeout=45s
kubectl --context k3d-dev -n finance-platform create --dry-run=client -f deploy/k8s/manifests/garage/init-bucket-job.yaml -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); env=d["spec"]["template"]["spec"]["containers"][0]["env"]; next(e for e in env if e["name"]=="EXPECT_KEY")["value"]="platform-validation/garage-s3-check-l46hf-26lsw"; print(json.dumps(d))' | kubectl --context k3d-dev -n finance-platform create -f -
kubectl --context k3d-dev -n finance-platform wait --for=condition=complete job/garage-s3-check-m7sv2 --timeout=45s
kubectl --context k3d-dev -n finance-platform logs job/garage-s3-check-m7sv2
kubectl --context k3d-dev -n finance-platform get pvc data-garage-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,PV:.spec.volumeName
kubectl --context k3d-dev -n finance-platform get pod garage-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid
kubectl --context k3d-dev -n finance-platform top pods -l app.kubernetes.io/part-of=finance-platform
git diff --check
```

위 명령은 실행 기록이다. 신규 설치는 README의 정상 순서를 사용한다.
초기 오류 수정 과정에서 `apply`, Pod 재생성, rollout 검사를 반복했다.
Ruby YAML 파싱 및 Python AST 문법 검사도 수행했다.

## 결과

| 검증 | 관측 결과 |
| --- | --- |
| 공식 이미지 | `dxflrs/garage:v2.4.1`, ARM64 digest 고정 |
| Garage 상태 | `garage-0` 1/1 Ready, `/garage status` healthy, layout 1, 단일 노드 |
| 스토리지 | `data-garage-0` 10Gi local-path Bound |
| 통신 | 별도 Job → `garage.finance-platform.svc.cluster.local:3900` ClusterIP |
| 버킷 초기화 | `warehouse` 존재, 두 성공 Job을 반복 실행해도 기존 버킷 보존 |
| PUT/GET/HEAD/LIST | 업로드/다운로드 내용·길이·목록 검증 통과 |
| multipart | 5MiB + 마지막 part 업로드/complete, 다운로드 SHA256 일치 |
| DELETE | 임시 multipart 객체 삭제 후 HEAD 404 |
| private | 인증 없는 실제 객체 GET이 HTTP 403 |
| Secret helper 재실행 | 기존 Secret 보존, 값 미출력 |
| 재시작 | Pod UID 변경, PVC/PV 동일, 이전 객체 내용을 새 Job에서 읽음 |

Pod UID:
`3a850bb4-19c0-4027-a9df-c2473fd97110` → `b2e0492e-d4c7-4a8d-942d-f6b7845fe76e`.

PVC UID는 전후 `31d7b676-a219-4ac9-86a1-6e5cfbbc6338`,
PV는 `pvc-31d7b676-a219-4ac9-86a1-6e5cfbbc6338`로 동일했다.

재시작 후 Job `garage-s3-check-m7sv2`는 기존 객체
`platform-validation/garage-s3-check-l46hf-26lsw`가
`finance-platform-persistence-v1` 내용을 보존했는지 확인한 후 전체 S3 검사를 다시 수행했다.

## 실패와 수정

- `garage-s3-check-lfznh`: Service 배포 전 의도한 EndpointConnectionError.
- 첫 StatefulSet은 args만 지정하여 `exec: server: executable file not found`.
  공식 이미지에 ENTRYPOINT가 없으므로 `command: [/garage]`를 명시했다.
- 다음 시작에서는 Garage가 Secret 파일 mode 0440을 거부했다.
  검사를 비활성화하지 않고 공식 환경변수 GARAGE_RPC_SECRET/GARAGE_ADMIN_TOKEN의
  secretKeyRef 주입으로 수정했다. 비밀번호/키 값을 출력하지 않았다.
- 실패한 기존 Pod가 Ready가 아니어서 StatefulSet 갱신이 대기했다.
  수정 적용 후 Pod만 재생성했고 기존 PVC를 그대로 사용했다.
- `garage-s3-check-5bxjq`: 시작 실패 중 먼저 생성된 Job으로 접속 실패.
- 수정 후 `garage-s3-check-l46hf`, 재시작 후 `garage-s3-check-m7sv2` 모두 Complete 1/1.

## 남은 범위

이 결과는 기본 S3 인프라 검증이다. Iceberg S3FileIO/REST Catalog,
Spark checkpoint, 실제 기사 데이터 파이프라인 검증은 아직 하지 않았다.
bucket policy/ACL/versioning 같은 S3 기능은 Garage와 차이가 있다.
단일 replica이므로 HA가 아니며 노드/디스크 유실이나 백업 복원은 검증하지 않았다.
로컬 import 검증 이미지의 핵심 SDK는 고정했지만 transitive dependencies 전체의
해시 잠금은 아직 적용하지 않았다.
