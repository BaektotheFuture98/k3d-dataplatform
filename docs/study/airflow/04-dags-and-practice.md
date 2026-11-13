# Airflow 4: DAG를 올리고 한 번만 실행해 보기

## 학습 목표

DAG 코드, DAG processor, paused 상태, 수동 실행, worker 생성의 관계를 체험한다.

## 현재 DAG 전달 방식

Airflow 이미지에는 업무 DAG를 넣지 않는다. DAG processor와 scheduler, worker가
`airflow-executor-dags` PVC를 `/opt/airflow/dags`에 연결한다.
worker는 읽기 전용이고 DAG processor는 파일을 복사할 수 있도록 쓰기 mount다.
Git sync는 현재 꺼져 있다. 파일을 로컬에서 만들었다고 자동 업로드되지는 않는다.

검증용 원본은 `configs/airflow/kubernetes-executor-smoke.py`다.
현재 DAG ID는 `airflow_kubernetes_executor_smoke`, task는 `verify_worker`,
`schedule=None`, `catchup=False`, 최초 paused, task retry=0이다.
이 학습 문서 PR이 검증 코드 원본까지 게시하는 것은 아니므로 실습 전 로컬에
해당 파일이 존재하는지 확인한다. 아래 명령은 설정된 smoke DAG가 있는 현재 환경용이다.

파일이 없는 새 학습 환경에서는 다음 코드를 로컬의
`configs/airflow/kubernetes-executor-smoke.py`로 저장할 수 있다.
현재 환경에는 같은 DAG ID의 코드가 이미 있으므로 덮어쓰기 전 내용을 비교한다.

```python
from datetime import datetime, timezone
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def verify_worker():
    import os
    import socket
    import time

    hostname = socket.gethostname()
    assert not hostname.startswith("airflow-scheduler-"), hostname
    assert os.environ["AIRFLOW__CORE__EXECUTOR"] == "KubernetesExecutor"
    print(f"KUBERNETES_EXECUTOR_SMOKE_OK worker={hostname}", flush=True)
    time.sleep(15)
    return hostname


with DAG(
    dag_id="airflow_kubernetes_executor_smoke",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    tags=["infrastructure", "smoke"],
) as dag:
    PythonOperator(task_id="verify_worker", python_callable=verify_worker, retries=0)
```

## 1. 읽기 실습

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags list --output json
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-dag-processor \
  -c dag-processor -- airflow dags list --local --output json
```

첫 명령은 DB에 반영된 DAG, `--local`은 파일을 직접 읽어 본 결과를 확인하는 데
사용한다. 파일은 있는데 UI에 안 보이면 DAG 탐색 주기와 import error를 확인한다.
관측한 기본 bundle 새 파일 탐색 주기는 300초, 파일 재처리 최소 간격은 30초였다.

## 2. 파일 업로드 — 상태를 변경하는 예시

```sh
# 현재 Pod 이름은 고정하지 않는다.
AIRFLOW_DAG_POD=$(kubectl --context k3d-dev -n finance-platform get pod \
  -l component=dag-processor,release=airflow -o jsonpath='{.items[0].metadata.name}')

# 덮어쓸 대상 파일이 없는지 먼저 확인한 뒤, 새 파일명으로 복사한다.
kubectl --context k3d-dev -n finance-platform cp \
  configs/airflow/kubernetes-executor-smoke.py \
  "$AIRFLOW_DAG_POD":/opt/airflow/dags/kubernetes_executor_smoke.py \
  -c dag-processor
```

위 복사는 이미 배치된 파일을 덮어쓸 수 있다. 현재 smoke DAG는 업로드된 상태이므로
단순 조회 학습을 위해 다시 복사할 필요는 없다. 실제 DAG는 Git sync나 이미지 배포
등 버전 관리 방식을 정해서 전달하는 것이 재현에 유리하다.

## 3. 한 번 수동 실행 — 태스크를 실제로 생성한다

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags unpause airflow_kubernetes_executor_smoke

# 기존 run ID와 충돌하지 않도록 UTC 시각을 붙인다.
SMOKE_RUN_ID="manual__study_$(date -u +%Y%m%dT%H%M%SZ)"
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags trigger airflow_kubernetes_executor_smoke \
  --run-id "$SMOKE_RUN_ID"
```

다른 터미널에서 worker를 관찰한다.

```sh
kubectl --context k3d-dev -n finance-platform get pods -l component=worker --watch
```

성공 여부를 확인하고 종료한다.

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow tasks states-for-dag-run \
  airflow_kubernetes_executor_smoke "$SMOKE_RUN_ID" --output json
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags pause airflow_kubernetes_executor_smoke
```

실습 run은 DB에 기록된다. 과거 성공 기록을 지우거나 임의로 DB를 수정하지 않는다.
`schedule=None`은 주기적 실행이 없다는 뜻이다. paused와는 다른 설정이다.

## 업무 DAG로 확장하기 전에

수집 DAG는 저장소의 `workspace/airflow/dags/article_collection.py`에 있지만
현재 플랫폼에서 업무 수집을 가동한 것은 아니다. Job template, 실제 collector
이미지, 환경변수와 Job 실행 SA/RBAC를 연결해야 한다.
기본 worker는 API 토큰과 Job 생성 권한이 없으므로 KJO를 넣는 것만으로 실행되지 않는다.

## 확인 문제

1. `dags_are_paused_at_creation=True`가 이미 존재하는 DAG를 다시 pause하는가?
2. `schedule=None`인 DAG를 수동 trigger할 수 있는가?

**해설:** 기존 상태는 자동으로 재설정되지 않는다. 주기 실행이 없어도 수동
trigger는 가능하며 현재 smoke 실습이 그 사례다.
