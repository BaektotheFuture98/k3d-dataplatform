# Airflow 2: 현재 설정값과 바꾸는 위치

## 학습 목표

Helm values, ConfigMap, 컨테이너 환경변수, 실제 실행값을 구분한다.

## 실행 중 scheduler에서 확인한 값

| section / key | 현재 값 | 의미 |
| --- | --- | --- |
| core.executor | KubernetesExecutor | 태스크별 worker Pod |
| core.parallelism | 2 | 이 scheduler 구성의 동시 실행 상한 |
| core.dags_folder | /opt/airflow/dags | DAG 파일 경로 |
| core.dags_are_paused_at_creation | True | 새 DAG는 기본 paused |
| core.execution_api_server_url | http://airflow-api-server:8080/execution/ | worker의 Execution API |
| core.auth_manager | FAB auth manager | Airflow 웹 사용자 인증 |
| database.sql_alchemy_pool_size | 3 | 프로세스별 기본 DB 연결 pool |
| database.sql_alchemy_max_overflow | 2 | pool을 넘는 추가 연결 한도 |
| kubernetes_executor.namespace | finance-platform | worker 생성 namespace |
| kubernetes_executor.in_cluster | True | Pod의 cluster 연결 사용 |
| kubernetes_executor.multi_namespace_mode | False | 여러 namespace 감시 꺼짐 |
| kubernetes_executor.delete_worker_pods | True | 종료 worker 정리 |
| kubernetes_executor.delete_worker_pods_on_failure | False | 실패 worker는 보존 |
| kubernetes_executor.pod_template_file | /opt/airflow/pod_templates/pod_template_file.yaml | worker spec 원본 |
| logging.base_log_folder | /opt/airflow/logs | PVC의 로그 경로 |
| logging.remote_logging | False | S3 등 원격 로깅은 사용 안 함 |
| api.workers | 1 | API 서버 프로세스 수 |

parallelism=2만으로 모든 태스크가 항상 두 개 실행되는 것은 아니다.
DAG/task 동시성, pool, 스케줄, Kubernetes 자원 상황도 실행 개수를 제한한다.
DB pool=3은 클러스터 전체 연결이 3개라는 뜻이 아니다.

## Pod별 자원

| 역할 | CPU request / limit | 메모리 request / limit |
| --- | --- | --- |
| Scheduler | 150m / 1 | 512Mi / 2Gi |
| API server | 100m / 500m | 256Mi / 1Gi |
| DAG processor | 100m / 500m | 256Mi / 1Gi |
| 임시 worker | 100m / 1 | 256Mi / 1Gi |

`100m`은 CPU 0.1개다. requests는 배치 가능 여부 계산에 쓰이고 limits는 실행
한도에 관련된다. 메모리 limit 초과와 노드 자원 부족은 서로 다른 문제다.

## 저장소 선언의 핵심

```yaml
executor: KubernetesExecutor
allowPodLaunching: true
multiNamespaceMode: false
rbac:
  create: false   # 별도 executor-resources.yaml의 namespace Role 사용
triggerer:
  enabled: false
workers:
  replicas: 0
  serviceAccount:
    create: false
    name: airflow-executor-worker
    automountServiceAccountToken: false
config:
  core:
    parallelism: 2
dags:
  persistence:
    enabled: true
    existingClaim: airflow-executor-dags
logs:
  persistence:
    enabled: true
    existingClaim: airflow-executor-logs
```

이 코드는 핵심 항목만 설명하는 발췌다. 이것만으로 기존 values 전체를 덮어쓰면
이미지·DB·인증·자원 설정을 잃을 수 있다. 실제 배포에는 전체 현행 values가 필요하다.
`workers.replicas=0`은 Celery 상주 worker를 두지 않는다는 뜻이지 executor가
태스크 Pod를 만들지 않는다는 뜻이 아니다.

## 실제 값 확인 실습

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow config get-value core parallelism
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow config get-value kubernetes_executor namespace
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow config get-value logging remote_logging
```

환경변수 `AIRFLOW__SECTION__KEY`가 파일 설정을 재정의할 수 있다.
따라서 값 변경 후에는 파일을 봤다는 이유만으로 적용됐다고 하지 말고
`airflow config get-value`로 실행 중 프로세스의 유효 설정을 확인한다.
비밀번호가 들어갈 수 있는 key는 이 방식으로 출력·공유하지 않는다.

## 설정 변경의 순서

1. 변경할 이유와 기대 동작을 정한다.
2. 전체 values와 필요한 별도 namespace 리소스를 수정한다.
3. 렌더링·검증 후 기존 Secret/PVC를 재사용해 upgrade한다.
4. rollout과 effective config를 확인한다.
5. 영향받는 기능의 작은 검증 태스크를 실행한다.

현재 Helm 기록과 실행 설정이 다른 점은 [운영 문서](06-operations.md)를 먼저 읽는다.

## 확인 문제

1. 파일의 parallelism을 4로 고쳤는데 실행값이 2라면 무엇을 살펴볼까?
2. API workers=1과 태스크 parallelism=2는 같은 설정인가?

**해설:** 실제 사용한 values, ConfigMap, 환경변수, rollout 여부를 확인한다.
API 프로세스 수와 태스크 동시 실행 상한은 별개의 값이다.

참고: [Airflow 3.0.2 설정](https://airflow.apache.org/docs/apache-airflow/3.0.2/configurations-ref.html),
[chart 1.18.0 values](https://github.com/apache/airflow/blob/helm-chart/1.18.0/chart/values.yaml).
