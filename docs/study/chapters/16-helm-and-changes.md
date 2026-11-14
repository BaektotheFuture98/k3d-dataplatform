# 16장. Helm과 파일·실행 설정의 차이

## 왜 필요한가

values를 고쳤는데 실행값은 그대로일 수 있다. 반대로 kubectl로 실행 설정만 고치면
다음 Helm 배포에서 이전 내용으로 돌아갈 수 있다. 관리하는 상태가 여러 곳에 있기 때문이다.

## 어떻게 동작하는가

**Chart**는 Kubernetes 리소스를 만드는 템플릿 묶음이다. **values**는 그 템플릿에
넣는 입력값이다. **렌더링**은 둘을 합쳐 실제 manifest를 만드는 과정이다.
**Release**는 Helm이 이름을 붙여 관리하는 설치와 변경 기록이다.

```text
Chart + values → 렌더링된 Kubernetes manifest → API에 반영 → 실행 중인 Pod
                    ↑ Helm이 관리하는 release 기록
```

Helm은 상주하면서 모든 변경을 계속 되돌리는 Kubernetes controller와는 다르다.
API의 Deployment를 따로 바꾸면 Helm 기록과 실제 객체 사이에 차이가 생길 수 있다.
`helm rollback`은 지정한 과거 release로 되돌리는 동작이지 최신 실행 상태의 자동 백업 복원은 아니다.

프로젝트에는 **이미지 토큰 치환**과 **Helm 템플릿 렌더링** 두 단계도 있다.
`scripts/render-manifests.py`는 전자를 처리해 `__AIRFLOW_REPOSITORY__` 등을 바꾼다.
그 결과 values를 chart에 넣어 Kubernetes manifest를 만드는 작업은 Helm 쪽이다.

## 우리 프로젝트에서는

[chart 고정 정보](../../../deploy/k8s/helm/airflow/chart.yaml)는 chart 1.18.0,
Airflow 3.0.2다. [values](../../../deploy/k8s/helm/airflow/values.yaml)는 실제 입력이다.
과거 기록상 executor 전환 때 kubectl로 ConfigMap과 Deployment를 변경했고,
Helm 기록은 이전 LocalExecutor 설정이었다. **현재도 같은지는 대조가 필요하다.**

기존 변경·재배포 절차는 KubernetesExecutor 안내(로컬 파일 `configs/airflow/KUBERNETES-EXECUTOR.md`)에
있다. 이 장에서는 upgrade나 rollback을 실행하지 않는다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/airflow-scheduler \
  -c scheduler -- airflow config get-value core executor
kubectl --context k3d-dev -n finance-platform get deployment airflow-scheduler \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

첫 명령을 나눠 읽는다. kubectl은 클러스터에 요청하고, `exec`는 해당 Deployment의
Pod 안에서 명령을 실행하며, `-c scheduler`는 컨테이너를 고른다.
`--` 뒤는 컨테이너 안의 명령이다. Airflow CLI가 그 환경에서 읽은 유효 설정을 출력한다.
이미 실행 중인 모든 프로세스의 메모리를 직접 검사하는 명령은 아니다.

선언대로 적용됐다면 첫 응답은 `KubernetesExecutor`다. 로컬 values와 이 값을 비교한다.
Helm CLI가 설치됐다면 다음으로 release 목록과 revision·상태를 확인할 수 있다.

```sh
helm list --kube-context k3d-dev --namespace finance-platform
```

values 전체나 렌더링된 Secret을 그대로 출력할 필요는 없다.
변경할 때는 원본·치환 결과·chart 결과·API 객체·새 Pod의 유효 설정을 순서대로 대조한다.

## 이해 확인

1. values 파일 저장만으로 실행 중인 프로세스 설정이 바뀌는가?
2. Helm 기록이 오래됐을 때 rollback이 최신 구성을 복원하는가?

**해설:** 전달·API 반영·새 Pod/설정 로딩을 거쳐야 한다. rollback은 과거 Helm
revision을 대상으로 하므로 별도 적용한 최신 변경을 되돌릴 수 있다.

근거: [Helm chart](https://helm.sh/docs/topics/charts/),
[Helm rollback](https://helm.sh/docs/helm/helm_rollback/).

---

[전체 목차](../README.md) · [이전: 15장. 출력·이벤트·로그로 장애 단계 좁히기](15-observing-and-debugging.md) · [다음: 17장. 단일 노드의 장애와 데이터 복구](17-failure-and-recovery.md)
