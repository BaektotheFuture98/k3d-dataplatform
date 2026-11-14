# 21장. DAG 배포·로그·동시성·대기

## 왜 필요한가

DAG 파일은 있는데 UI에 없거나, Pod가 삭제돼 로그가 안 보이거나, 실행이 두 개보다
적을 수 있다. 배포·상태·저장·자원 정책을 함께 읽어야 한다.

## 어떻게 동작하는가

**DAG 배포**는 DAG processor와 worker가 올바른 코드 버전을 읽게 하는 일이다.
공유 볼륨, 이미지 포함, Git 동기화 등 여러 방식이 있다. 로컬 파일 저장만으로
Pod에 전달되지 않는다. DAG 탐색·해석에 시간이 걸리며 import 오류가 날 수도 있다.

**실행 기록**과 **작업 로그**도 다르다. 메타데이터 DB는 실행 상태 등을,
태스크 로그는 프로그램 출력을 보관한다. worker 삭제 뒤 로그를 읽으려면
PVC나 원격 저장소처럼 실행 컨테이너보다 오래 남는 경로가 필요하다.

**동시성**은 여러 제한을 동시에 만족해야 한다. 이 프로젝트의 parallelism=2는
현재 단일 scheduler 구성에서 태스크 동시 실행 상한이다. DAG의 실행 수·태스크
제한, Airflow pool, 의존성, 노드 자원이 추가로 제한할 수 있다.
API workers=1은 웹/API 처리 프로세스 수로, 태스크 동시 실행 수와 다른 설정이다.

**대기**도 자원을 사용한다. 일반 태스크가 worker에서 sleep이나 반복 조회로
외부 Job 완료를 기다리면 그동안 실행 자원을 차지할 수 있다. deferrable operator는
대기를 triggerer에 넘겨 worker 자원을 반납하고, 조건이 오면 다시 배정돼 이어 실행한다.
triggerer는 CPU 계산을 대신하는 엔진이 아니다.

## 우리 프로젝트에서는

[values](../../../deploy/k8s/helm/airflow/values.yaml)에서 다음을 읽을 수 있다.

| 항목 | 저장소 선언과 의미 |
| --- | --- |
| dags.persistence | 공유 DAG PVC 사용, Git sync 비활성화 |
| logs.persistence | 공유 로그 PVC 사용 |
| delete_worker_pods | 성공 종료 worker 정리 |
| delete_worker_pods_on_failure | False: 실패 worker 보존 |
| logGroomerSidecar | 비활성화: 자동 보존 기간 정책을 의미하지 않음 |
| triggerer.enabled | False: deferrable 실행은 별도 준비 필요 |

로그 PVC 요청량은 2Gi지만 local-path의 실사용 상한을 보장하지 않는다.
준비된 [업무 DAG](../../../workspace/airflow/dags/article_collection.py)는 Job
실행용 SA·토큰·이미지·템플릿 연결도 필요하다. 일반 worker에 KJO를 넣기만 하면
작동하는 구성은 아니다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow config get-value core parallelism
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow config get-value logging remote_logging
kubectl --context k3d-dev -n finance-platform get pvc airflow-executor-dags airflow-executor-logs
kubectl --context k3d-dev -n finance-platform get pods -l component=triggerer
```

선언과 과거 기록 기준으로 예상하는 응답은 2, False, 연결된 PVC, triggerer 없음이다.
현재 출력이 다르면 과거 기록을 덮어 믿지 말고 유효 설정과 적용 내역을 대조한다.
기존 실행 로그는 UI에서 해당 DAG Run과 태스크를 선택해 읽는다.

## 이해 확인

1. 성공 worker를 계속 남기는 것과 로그를 영속 보관하는 것은 같은가?
2. triggerer를 켜면 기존 Python 태스크가 자동으로 deferrable이 되는가?

**해설:** Pod 보존은 로그 저장 정책이 아니다. 오래 남는 저장소와 관리 정책이
필요하다. deferrable을 지원하는 operator와 그 설정, triggerer 구성을 함께 준비해야 한다.

근거: [Deferrable 작업](https://airflow.apache.org/docs/apache-airflow/3.0.2/authoring-and-scheduling/deferring.html),
[설정 참조](https://airflow.apache.org/docs/apache-airflow/3.0.2/configurations-ref.html).

---

[전체 목차](../README.md) · [이전: 20장. 두 scheduler와 태스크별 worker Pod](20-airflow-on-kubernetes.md) · [다음: 22장. PostgreSQL·Garage·Iceberg의 저장 책임](22-data-storage.md)
