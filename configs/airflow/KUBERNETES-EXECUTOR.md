# KubernetesExecutor 전환

이 문서는 2026-11-13 `finance-platform`의 전환 기록이다. 2026-11-27부터 Airflow와
worker는 `pipelines`에 배포하며, 재배포 기준은 [Airflow 운영 안내](README.md)에 있다.

2026-11-13 Airflow 3.0.2 / chart 1.18.0 / Kubernetes provider 10.24.0의
LocalExecutor를 KubernetesExecutor로 전환했다. 태스크마다 worker Pod를 생성한다.
이미지와 PostgreSQL 및 기존 Secret을 재사용하며 동시 실행 한도는 2개다.

## 구성

- Scheduler만 `finance-platform`의 Pod 생성·조회·감시·수정·삭제 권한을 가진다.
  Secret 조회 권한과 클러스터 범위 역할은 추가하지 않았다.
- API 서버는 해당 namespace의 Pod/log를 읽을 수 있다.
- Worker는 `airflow-executor-worker` ServiceAccount를 사용하며 별도 RBAC가 없다.
  API 토큰 자동 마운트도 껐다.
- DAG: `airflow-executor-dags`, 1Gi, `local-path`, ReadWriteOnce.
- 로그: `airflow-executor-logs`, 2Gi, 동일 storage class/access mode.
- 현재 단일 노드 개발 환경을 위한 공유 저장소다. 다중 노드로 확장할 때에는
  공유 DAG 배포와 로그 저장 방식을 다시 검토한다.
- Worker 요청은 CPU 100m / 메모리 256Mi, 한도는 CPU 1 / 메모리 1Gi다.
- 성공한 worker Pod는 정리하며, 로그는 PVC에 보존한다. 실패 Pod는 조사용으로 남긴다.
- 로그 보존 기간과 자동 삭제는 아직 설정하지 않았다. `local-path`의 2Gi 요청은
  디스크 사용량 제한을 보장하지 않으므로, 장기 운영 전 로그 보존 정책을 정해야 한다.
  이번 변경에서는 보존 중인 로그를 자동 삭제하는 작업을 추가하지 않았다.
- Worker 환경에는 기존 Airflow Secret 참조가 포함된다. API 토큰 자동 마운트 해제는
  Kubernetes API 권한을 제한하며, 작업 코드로부터 Airflow 자격증명을 격리하는
  설정은 아니다. 서로 신뢰하지 않는 DAG 실행 환경으로 사용하지 않는다.

## 실제 검증

업무 DAG 대신 `kubernetes-executor-smoke.py`만 DAG PVC에 복사해 수동 실행했다.

- Scheduler의 effective executor: `KubernetesExecutor`.
- API server / DAG processor / scheduler rollout 성공, 각 Pod Ready 1/1.
- `airflow jobs check --job-type SchedulerJob --local`: 살아 있는 scheduler 1개.
- 검증 run: `manual__kubernetes_executor_validation_20261113`.
- 생성 Pod: `airflow-kubernetes-executor-smoke-verify-worker-3wdcz3vg`.
- `verify_worker` task가 worker Pod에서 실행돼 `success`로 종료했다.
- 성공 Pod 자동 삭제 후 API 서버에서 PVC의 성공 로그를 읽었다.
- 검증 DAG `airflow_kubernetes_executor_smoke`는 완료 후 다시 paused 상태로 뒀다.
- Scheduler pods/create 허용, secrets/get 거부, worker pods/create 거부를 확인했다.

## 배포와 Helm 동기화

기존 Airflow 이미지에는 업무 DAG가 없다. 공유 DAG PVC는 이제 연결돼 있지만,
업무 DAG/Job template 업로드나 수집 작업 실행은 별도 절차다.
KubernetesJobOperator를 업무 DAG에 추가할 때에는 해당 worker의
`executor_config`에 Job 실행용 ServiceAccount와 API 토큰 마운트를 별도로
지정해야 한다. 기본 worker에는 Job/Pod 실행 권한을 부여하지 않았다.

이번 적용은 Helm CLI 부재와 다운로드 불가로 kubectl을 사용했다. 기존 Helm
release 기록은 LocalExecutor 설정이므로, 다음 upgrade 때 반드시 변경된
values를 렌더링해 사용한다. Helm release Secret을 수동 편집하지 않았다.

```sh
kubectl --context k3d-dev -n finance-platform apply \
  -f deploy/k8s/helm/airflow/executor-resources.yaml
# scripts/render-manifests.py로 AIRFLOW_IMAGE 등을 실제 이미지로 치환한 뒤:
helm upgrade airflow airflow --repo https://airflow.apache.org --version 1.18.0 \
  --kube-context k3d-dev --namespace finance-platform \
  -f <rendered-airflow-values.yaml> --wait --timeout 3m
```

namespace resources와 worker template의 server dry-run, 실제 Pod 실행 및 로그
보존은 검증했다. Helm CLI가 없어 전체 차트 렌더링은 이번 전환에서 실행하지 못했다.

## 복구

전환 전 ConfigMap과 Deployment 스냅샷, 실제 적용 패치는 Git에서 제외된
`deploy/rendered-runtime/airflow-kubernetes-executor/`에 보관했다.
진행 중 태스크가 없음을 확인한 뒤 `config-before.json`과
`deployments-before.json`의 data 및 Pod template을 사용해 복구할 수 있다.
저장소 전체를 `apply`하는 대신 해당 필드만 patch하고 rollout을 검증한다.
스모크 DAG를 paused로 유지하며 DAG/log PVC나 기존 Secret을 삭제하지 않는다.
