# Airflow 6: 설치·재배포·로그·복구

## 학습 목표

설치가 된 상태, 설정 파일, Helm release 기록을 대조하고 변경을 검증하는 습관을 익힌다.

## 현재 관리 상태

최초 설치는 공식 chart 1.18.0을 사용했다. 2026-11-13 executor 전환은 Helm CLI가
없고 다운로드도 불가해 ConfigMap과 Deployment를 kubectl로 변경했다.
**실행 중인 executor는 KubernetesExecutor지만 Helm release 기록은 이전
LocalExecutor 설정이다.** Headlamp도 같은 종류의 차이가 있다.
이 문서 PR은 실행 설정을 바꾸거나 Helm 기록을 몰래 수정하지 않는다.

## 이미지부터 실행까지

```text
Dockerfile → docker build → k3d image import
  → 이미지 변수 렌더링 → namespace 리소스 검증
  → Helm upgrade → rollout → effective config → 작은 태스크 검증
```

실제 이미지 주소는 로컬 `configs/platform-images.env`로 관리한다.
예제 파일을 기존 설정 위에 덮어쓰지 않는다. renderer는 새로운 출력 디렉터리를
요구하고 파일만 생성하며 배포하지 않는다.

```sh
# 파일 생성 예시. 해당 출력 디렉터리가 없는 경우에만 사용한다.
python3 scripts/render-manifests.py --source deploy/k8s/helm/airflow \
  --values configs/platform-images.env --output deploy/rendered-airflow-study
```

다음은 **현재 로컬 설정 전체를 검토한 후** 사용하는 변경 예시다.
원본의 `__AIRFLOW_REPOSITORY__` 같은 미치환 토큰을 그대로 배포하면 안 된다.

```sh
kubectl --context k3d-dev -n finance-platform apply --dry-run=server \
  -f deploy/rendered-airflow-study/executor-resources.yaml
kubectl --context k3d-dev -n finance-platform apply \
  -f deploy/rendered-airflow-study/executor-resources.yaml

helm upgrade --install airflow airflow --repo https://airflow.apache.org \
  --version 1.18.0 --kube-context k3d-dev --namespace finance-platform \
  -f deploy/rendered-airflow-study/values.yaml --wait --timeout 5m
```

기존 Secret을 보존해야 한다. 신규 설치에서는 DB·metadata 연결 Secret이 먼저
필요하고 migration hook이 완료돼야 한다. chart를 `helm template`으로 출력하면
생성될 Secret 값이 포함될 수 있으므로 stdout·GitHub에 원문을 게시하지 않는다.
위 명령은 재배포 방법이며 학습 문서 작성 중 실행한 것이 아니다.

## 인증정보의 역할

| Secret 이름 | 역할 |
| --- | --- |
| airflow-metadata | 외부 PostgreSQL 연결 URI |
| airflow-admin | FAB 관리자 계정의 인증정보 |
| airflow-fernet-key | Airflow의 암호화 키 |
| airflow-api-secret-key | API 인증 관련 비밀키 |
| airflow-jwt-secret | Execution API JWT 서명 비밀키 |

값을 문서·이미지·명령행 인자에 넣지 않는다. 기존 키를 임의로 새로 만들면
암호화된 데이터나 실행 중 토큰의 연속성에 영향을 줄 수 있다.
관리자 provisioning 도구는 `configs/runtime/provision-airflow-admin.py`이며
기존 Secret/사용자를 재사용하도록 작성돼 있다.

## 상태 확인

```sh
kubectl --context k3d-dev -n finance-platform get pods -l release=airflow
kubectl --context k3d-dev -n finance-platform rollout status deployment/airflow-scheduler
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow jobs check --job-type SchedulerJob --local
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow config get-value core executor
```

DB 연결, scheduler heartbeat, DAG import, task 실행은 각각 별도로 확인한다.
Pod Ready만으로 실제 태스크 실행이 검증됐다고 말하지 않는다.

## 로그와 디스크

현재 worker 로그는 `/opt/airflow/logs`의 공유 PVC에 쓴다.
성공 Pod가 삭제된 뒤에도 API server가 같은 PVC에서 읽는다.
원격 로깅은 False이고 로그 자동 보존 기간·groomer는 아직 설정하지 않았다.
local-path의 2Gi 요청은 실제 디스크 quota가 아니므로 장기 실행 전 보존 정책과
디스크 사용량 관찰이 필요하다. 로그 정리 정책을 정하지 않은 상태에서 임의 삭제하지 않는다.

## 복구를 생각하는 순서

1. 진행 중·queued task가 있는지 확인한다.
2. 현재 ConfigMap과 Deployment의 필요한 비밀값 없는 설정을 별도로 보관한다.
3. 앱 이미지, executor, Pod template, RBAC, DAG/log mount의 조합을 맞춘다.
4. 설정을 되돌린 뒤 rollout과 effective config를 확인한다.
5. 작은 smoke task로 다시 검증한다.

기존 Helm 기록이 최신 실행 상태와 다르므로 `helm rollback`을 현재 구성 복원
버튼으로 생각하면 안 된다. DB Secret·Fernet key·PVC를 지우는 것은 executor
복구 절차가 아니다. PostgreSQL 백업·복원은 별도로 준비하고 검증해야 한다.

## 확인 문제

1. source values와 실행값이 맞는데 Helm rollback 후 달라질 수 있는 이유는?
2. 성공 worker Pod를 남기는 것이 로그 영속화와 같은가?

**해설:** Helm에 저장된 이전 release가 다른 값을 가질 수 있다. Pod 보존은
조사 편의일 뿐이고 장기 로그 보존은 PVC/원격 저장소와 보존 정책으로 관리한다.
