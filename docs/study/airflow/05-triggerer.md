# Triggerer: 설정 참고 자료

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [21장](../chapters/21-airflow-operations.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

## 학습 목표

작업을 실행하는 것과 외부 이벤트를 기다리는 것을 구분한다.

## 현재 상태

현재 Helm values는 `triggerer.enabled: false`다. KubernetesExecutor로 바꾸면서도
이 값을 유지했다. 준비된 collector DAG의 KJO도 `deferrable=False`이며,
현재 사용한 smoke task는 일반 PythonOperator다.
따라서 현재 검증 작업 실행에 triggerer는 필요하지 않았다.

## deferrable 작업의 의미

긴 작업 완료를 기다리느라 worker를 계속 붙잡는 대신, operator가 대기를
triggerer에 넘기고 worker 실행 자원을 반납하는 방식이다. 조건이 충족되면
scheduler가 작업을 다시 배정해 이어서 실행한다.

| 방식 | 기다리는 동안 | 현재 사용 여부 |
| --- | --- | --- |
| 일반 operator | worker가 실행을 유지할 수 있음 | 사용 |
| Sensor reschedule | 일정 간격으로 다시 검사하도록 scheduling | 별도 DAG 설정 필요 |
| Deferrable operator | triggerer가 비동기 대기, worker 슬롯 반납 | 현재 미사용 |

KubernetesExecutor가 triggerer 역할을 대신하지는 않는다.
triggerer를 켠다고 기존 모든 operator가 자동으로 deferrable이 되지도 않는다.
[Airflow 3.0.2 공식 설명](https://airflow.apache.org/docs/apache-airflow/3.0.2/authoring-and-scheduling/deferring.html).

## 추가하는 방법 — 아직 적용하지 않은 변경 예시

1. 해당 provider/operator의 현재 버전이 deferrable을 지원하는지 확인한다.
2. triggerer 1개와 CPU/메모리, 같은 DB/Fernet 설정을 준비한다.
3. chart로 배포하고 `TriggererJob` heartbeat를 확인한다.
4. 선택한 operator에만 `deferrable=True`를 설정한다.
5. 작은 대기 작업에서 deferred → 재개 → success 흐름을 검증한다.

```yaml
triggerer:
  enabled: true
  replicas: 1
  resources:
    requests: {cpu: 100m, memory: 256Mi}
    limits: {cpu: 500m, memory: 512Mi}
```

위 자원 값은 학습용 시작 예시이며 현재 적용값이나 부하 검증 결과가 아니다.
추가 Pod가 기존 노드 자원과 DB 연결을 사용한다는 점도 고려한다.
triggerer가 필요한 외부 API 인증과 모듈도 이미지/Secret에 준비돼 있어야 한다.

실행 후에는 아래 조회로 확인한다. 현재는 triggerer가 없으므로 성공을 기대하지 않는다.

```sh
kubectl --context k3d-dev -n finance-platform get pods -l component=triggerer
```

## 확인 문제

1. `deferrable=True`만 켜고 triggerer를 안 띄우면 어떻게 될 수 있는가?
2. 순수 CPU 계산 태스크도 triggerer를 켜면 빨라지는가?

**해설:** deferred 작업이 재개되지 못하고 기다릴 수 있다. triggerer는 비동기
대기를 위한 구성요소이므로 CPU 계산 가속 수단이 아니다.
