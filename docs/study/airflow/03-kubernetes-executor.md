# KubernetesExecutor: 설정 참고 자료

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [20장](../chapters/20-airflow-on-kubernetes.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

## 학습 목표

executor 이름만 바꾸는 것과 실제 태스크가 별도 Pod에서 성공하는 것을 구분한다.

## 전환 전후

| 항목 | 이전 LocalExecutor | 현재 KubernetesExecutor |
| --- | --- | --- |
| 태스크 프로세스 | scheduler Pod 내부 | 별도 worker Pod |
| 작업별 자원 | scheduler Pod 자원 공유 | worker spec으로 지정 |
| Kubernetes 권한 | 실행에 Pod 생성 권한 불필요 | scheduler에 Pod 생성 권한 필요 |
| DAG 전달 | scheduler에 파일 필요 | worker에도 같은 DAG가 필요 |
| 작업 로그 | scheduler 쪽 디스크 | 현재 공유 로그 PVC |

KubernetesPodOperator/KubernetesJobOperator는 DAG 안에서 사용하는 **operator**다.
KubernetesExecutor는 태스크를 어디에서 실행할지 정하는 **executor**다.
둘을 같이 쓰면 executor worker가 operator 코드를 실행하고, 그 코드가 별도
업무 Pod/Job을 다시 만들 수 있다. 모든 task가 이중 Pod 구조인 것은 아니다.

## 필수 연결 네 가지

1. **Scheduler 권한:** finance-platform Pod create/get/list/watch/patch/delete.
2. **Worker template:** 실행 이미지, base 컨테이너, 볼륨, API 연결.
3. **DAG 전달:** worker와 DAG processor가 같은 DAG 버전을 읽어야 한다.
4. **로그 보존:** 임시 Pod가 사라져도 로그를 확인할 방법이 있어야 한다.

현재 worker는 `airflow-executor-worker` SA를 사용하고 API 토큰 자동 mount를 끈다.
Scheduler의 namespace Role에는 Secret 조회나 다른 namespace의 권한을 추가하지 않았다.
Pod 생성 권한 자체가 namespace 내에서 강한 권한이라는 점도 이해해야 한다.

## Pod template의 핵심

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: airflow-worker-placeholder
spec:
  restartPolicy: Never
  serviceAccountName: airflow-executor-worker
  automountServiceAccountToken: false
  containers:
    - name: base
      image: finance-platform/airflow:3.0.2-kubernetes-10.24.0-infra
      imagePullPolicy: IfNotPresent
      resources:
        requests: {cpu: 100m, memory: 256Mi}
        limits: {cpu: '1', memory: 1Gi}
```

첫 컨테이너 `base`와 비어 있지 않은 image, placeholder Pod 이름이 필요하다.
실제 이름과 task 실행 인자는 executor가 채운다. 위 예시는 구조 설명용이며
현재 사용하는 전체 template에는 DAG/log/config 볼륨과 기존 Secret 참조도 있다.
학습용으로 직접 이 Pod를 `apply`해도 Airflow의 task 실행 검증을 대신하지 못한다.

## 실제로 검증한 실행

- DAG: `airflow_kubernetes_executor_smoke`.
- Run: `manual__kubernetes_executor_validation_20261113`.
- Task: `verify_worker`.
- 별도 worker Pod가 생성돼 Running 상태가 됐다.
- task가 자기 호스트가 scheduler가 아님을 검사하고 성공했다.
- worker Pod가 자동 삭제된 뒤 API server에서 PVC의 성공 로그를 읽었다.
- 검증 DAG는 다시 paused 상태로 뒀다.

## 조회 실습

```sh
kubectl --context k3d-dev -n finance-platform get pods -l component=worker
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow tasks states-for-dag-run \
  airflow_kubernetes_executor_smoke manual__kubernetes_executor_validation_20261113 \
  --output json
```

현재 작업이 없으면 첫 명령의 결과가 비어 있는 것이 정상이다.
실행 완료 여부는 두 번째 명령이나 UI에서 확인한다.

## 확인 문제

1. scheduler가 새 worker를 못 만들면 어느 SA의 RBAC를 확인할까?
2. Worker에 DAG가 없는데 scheduler에는 있으면 정상 실행할 수 있을까?

**해설:** `airflow-scheduler`를 확인한다. DAG 해석과 태스크 실행에 필요한 파일이
다른 Pod에 있다는 사실을 구분해야 하므로 worker 쪽 전달도 필요하다.

참고: [KubernetesExecutor 공식 문서](https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/stable/kubernetes_executor.html).
링크의 stable provider 버전과 현재 고정한 10.24.0의 차이는 확인하고 적용한다.
