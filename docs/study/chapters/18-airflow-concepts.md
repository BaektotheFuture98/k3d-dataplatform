# 18장. Airflow의 DAG·Task·실행 기록

## 왜 필요한가

“기사 수집 → 제목 정제 → 저장”을 매일 실행한다고 하자. 수집이 실패하면 정제는
기다려야 하고, 어느 날 실패했는지 기록해야 한다. 프로그램 실행뿐 아니라
**작업 순서·실행 시점·상태·재시도**를 관리할 필요가 있다.

## 어떻게 동작하는가

Airflow는 작업 흐름을 정의하고 실행을 관리하는 오케스트레이션 도구다.
**DAG**는 방향이 있고 순환하지 않는 작업 그래프다. A 뒤에 B를 실행한다면
`A → B` 의존성을 정의한다. B가 끝나야 A를 시작하도록 원을 만들 수는 없다.

| 개념 | 의미 | 예 |
| --- | --- | --- |
| DAG | 작업과 의존성의 정의 | article_pipeline |
| Task | DAG에 정의한 작업 하나 | collect, normalize, store |
| Operator | 작업 수행 방식을 정의하는 구성 요소 | PythonOperator |
| DAG Run | DAG 전체를 한 번 실행한 기록 | 특정 수동 실행 |
| Task Instance | 특정 실행에 속한 태스크의 실행 상태 | 그 실행의 collect |

같은 DAG를 두 번 실행하면 보통 두 DAG Run과 각각의 Task Instance가 생긴다.
정의와 실행 기록을 나누어야 “어제 collect는 성공했는데 오늘 collect는 실패했다”를
정확히 말할 수 있다. 동적 매핑 같은 확장 기능은 이후 학습 대상이다.

일반적인 기본 의존성에서는 선행 태스크가 성공해야 후행 태스크를 실행할 수 있다.
실패·재시도·건너뛰기·trigger rule에 따라 흐름이 달라질 수 있다.
Task 상태와 DAG Run 상태도 별개다. “하나 성공”만으로 전체 성공을 판단하지 않는다.

**schedule**은 자동 실행 일정을 정한다. **paused**는 DAG의 스케줄링 활성 상태다.
`schedule=None`이어도 수동 실행할 수 있다. **catchup**은 주기 스케줄의 과거 구간
실행을 따라잡을지에 관계한다. `start_date`를 쓰는 것 자체가 즉시 실행 명령은 아니다.

## 우리 프로젝트에서는

[업무 DAG](../../../workspace/airflow/dags/article_collection.py)는 소스가 있지만
현재 운영 업무가 가동 중이라는 뜻은 아니다. 검증 DAG(로컬 파일 `configs/airflow/kubernetes-executor-smoke.py`)는
worker 실행 확인용이다. 두 목적을 구분하고, 다음 장에서는 더 작은 학습용 DAG를 읽는다.

Airflow가 작업 순서를 결정하고 Kubernetes는 그 작업을 실행할 공간을 관리한다.
태스크가 Python 코드를 실행한다고 그 코드가 반드시 scheduler Pod에서 도는 것은 아니다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow dags list --output json
```

kubectl이 scheduler 컨테이너 안에서 `airflow dags list`를 실행한다.
`--output json`은 기계가 읽기 쉬운 형식이다. DAG ID와 파일 경로 등을 확인한다.
목록은 등록된 DAG에 관한 정보이며 “이 DAG가 현재 실행 중”이라는 뜻이 아니다.
등록된 DAG가 없는 환경이라면 그것도 유효한 관측이다.

## 이해 확인

1. 같은 DAG를 두 번 실행하면 Task 정의도 두 벌 만드는가?
2. schedule=None은 수동 실행도 금지한다는 뜻인가?

**해설:** 정의는 같고 실행 기록이 따로 생긴다. schedule=None은 주기 실행이
없다는 뜻이며 수동 실행은 가능하다.

근거: [Airflow 3.0.2 구조](https://airflow.apache.org/docs/apache-airflow/3.0.2/core-concepts/overview.html),
[DAG Run](https://airflow.apache.org/docs/apache-airflow/3.0.2/core-concepts/dag-run.html).

---

[전체 목차](../README.md) · [이전: 17장. 단일 노드의 장애와 데이터 복구](17-failure-and-recovery.md) · [다음: 19장. 두 작업을 연결하는 첫 DAG](19-first-dag.md)
