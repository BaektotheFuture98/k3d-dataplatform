# 19장. 두 작업을 연결하는 첫 DAG

## 왜 필요한가

먼저 외부 API나 DB 없이 “앞 작업의 결과를 다음 작업이 받는다”를 확인한다.
업무 데이터 대신 메모리에 만든 기사 두 건을 사용한다.

## 어떻게 동작하는가

아래 코드는 **학습용 예시**다. 문서 작성 중 업로드하거나 실행하지 않았다.
Airflow 3.0.2의 TaskFlow API로 Python 함수를 태스크로 정의한다.

```python
from datetime import datetime, timezone

from airflow.sdk import dag, task


@dag(
    dag_id="study_two_tasks",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    default_args={"retries": 0},
    tags=["study"],
)
def study_two_tasks():
    @task
    def make_articles():
        return ["  First article  ", "  Second article  "]

    @task
    def normalize_titles(articles):
        titles = [title.strip().lower() for title in articles]
        print(f"NORMALIZED_TITLES={titles}", flush=True)
        return len(titles)

    normalize_titles(make_articles())


study_two_tasks()
```

`@dag`는 아래 함수를 DAG 정의로 만드는 장식자이고, `@task`는 함수를 태스크로 만든다.
`dag_id`는 UI에서 찾을 이름이다. `schedule=None`으로 자동 일정을 두지 않으며,
처음 등록되면 paused다. retries=0으로 이 예제의 태스크 자동 재시도를 끈다.

중요한 줄은 `normalize_titles(make_articles())`다. DAG를 읽는 시점에는 일반 Python
함수처럼 기사를 생성하고 정제하지 않는다. 태스크 정의와 결과 참조를 연결한다.
실제 실행에서 첫 태스크가 성공하면 작은 반환값을 **XCom**이라는 태스크 간 값 전달
기능으로 다음 태스크가 받는다. 두 태스크가 같은 Python 메모리를 공유해서 받는 것이 아니다.
큰 데이터는 XCom에 넣지 않고 외부 저장소에 쓴 뒤 위치를 전달하는 편이 적합하다.

```text
make_articles → normalize_titles
```

첫 태스크는 문자열 두 개를 반환한다. 둘째는 양끝 공백을 지우고 소문자로 바꾼 뒤
로그를 남기며 숫자 2를 반환한다. 파일 맨 아래 호출은 DAG를 등록할 객체를 구성하는
단계이지, 이 파일을 읽자마자 두 작업을 실제 수행한다는 뜻은 아니다.

## 우리 프로젝트에서는

현재 DAG는 공유 PVC를 사용한다. Mac에서 파일을 저장해도 자동 전달되지 않는다.
worker 이미지에는 Airflow SDK가 필요하며 DAG processor와 worker가 같은 코드를
읽어야 한다. 자세한 배포 연결은 20–21장에서 다룬다.

## 직접 확인하기

먼저 실행 없이 결과를 예상한다. UI에는 태스크 두 개와 화살표 하나가 보여야 한다.
성공한 normalize_titles 로그의 예상 내용은 다음과 같다.

```text
NORMALIZED_TITLES=['first article', 'second article']
```

### 선택 실습 — 파일 업로드와 태스크 실행으로 상태가 바뀐다

위 Python을 Mac의 `/tmp/platform-study-dag.py`에 저장한다. 기존 업무 DAG는 수정하지 않는다.
공유 DAG PVC가 연결된 현재 환경용 절차다. 새 환경에서는 먼저 배포 구성을 준비해야 한다.

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags list --output json
```

**study_two_tasks가 이미 있으면 새로 복사하지 말고 기존 파일을 먼저 확인한다.**
없다면 다음으로 대상 파일이 없는지 검사한다. 확인이 성공한 경우에만 복사한다.

```sh
DAG_POD=$(kubectl --context k3d-dev -n finance-platform get pods \
  -l component=dag-processor,release=airflow -o jsonpath='{.items[0].metadata.name}')
if kubectl --context k3d-dev -n finance-platform exec "$DAG_POD" -c dag-processor \
  -- test ! -e /opt/airflow/dags/study_two_tasks.py; then
  kubectl --context k3d-dev -n finance-platform cp /tmp/platform-study-dag.py \
    "$DAG_POD":/opt/airflow/dags/study_two_tasks.py -c dag-processor
else
  echo '대상 확인에 실패해 복사하지 않았습니다. 기존 파일과 연결 상태를 확인하세요.'
fi
```

`DAG_POD`는 바뀔 수 있는 Pod 이름을 조회해 저장한다. cp는 로컬 파일을 PVC 경로로
복사한다. DAG 탐색은 즉시 끝나지 않을 수 있다. UI에 등록됐는지 확인하고, 보이지
않으면 DAG processor 로그를 확인한다. 다른 터미널에서 먼저 worker 관찰을 시작한다.

```sh
kubectl --context k3d-dev -n finance-platform get pods -l component=worker --watch
```

원래 터미널에서 **학습 DAG만** 활성화하고 한 번 실행한다.

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags unpause study_two_tasks
STUDY_RUN_ID="manual__study_$(date -u +%Y%m%dT%H%M%SZ)"
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags trigger study_two_tasks --run-id "$STUDY_RUN_ID"
```

UI에서 **이 run ID**의 두 태스크가 success인지 확인하고 normalize_titles 로그를
읽는다. 단순 목록은 생성이 빠른 worker를 놓칠 수 있다. 두 태스크의 worker는
순서대로 생성되며 같은 컨테이너에서 이어 실행된다고 가정하지 않는다.
성공 또는 실패 조사를 마친 뒤 학습 DAG를 다시 pause하고 watch는 Ctrl+C로 종료한다.

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags pause study_two_tasks
```

pause는 실행 중인 태스크 취소가 아니다. 완료 뒤 적용한다. 파일·실행 기록은 남으며,
이를 없애려고 PVC나 메타데이터 DB를 삭제할 필요가 없다.

## 이해 확인

1. make_articles가 실패하면 기본 의존성에서 normalize_titles는 성공 실행할 수 있는가?
2. 두 함수의 결과 전달이 같은 프로세스의 변수 공유인가?

**해설:** 선행 성공 조건을 만족하지 못하므로 후행 작업은 정상 실행되지 않는다.
이 예제는 Airflow의 결과 참조·XCom 전달을 사용하므로 별도 worker에서도 연결된다.

근거: [Airflow 3.0.2 TaskFlow](https://airflow.apache.org/docs/apache-airflow/3.0.2/tutorial/taskflow.html).

---

[전체 목차](../README.md) · [이전: 18장. Airflow의 DAG·Task·실행 기록](18-airflow-concepts.md) · [다음: 20장. 두 scheduler와 태스크별 worker Pod](20-airflow-on-kubernetes.md)
