# 15장. 출력·이벤트·로그로 장애 단계 좁히기

## 왜 필요한가

설정을 모르겠다고 Pod를 반복 재시작하면 원인을 볼 기회가 사라질 수 있다.
먼저 “배치 전인가, 컨테이너 시작 전인가, 앱 실행 후인가”를 구분한다.

## 어떻게 동작하는가

`get`은 전체 상태 요약, `describe`는 특정 객체의 상세 상태와 이벤트,
`logs`는 컨테이너의 프로그램 출력을 보는 도구다. 서로 대체하지 않는다.

| 관측 | 우선 확인할 단계 | 다음 증거 |
| --- | --- | --- |
| kubectl 자체가 연결 실패 | API 주소·접속·클러스터 실행 | context, 노드 컨테이너, VM |
| Pending, NODE 없음 | 노드 배치 | FailedScheduling 이벤트, requests, 볼륨 조건 |
| ImagePullBackOff | 이미지 확보 | 이름·태그·registry·노드 이미지 |
| ContainerCreating | 볼륨·네트워크·컨테이너 준비 | mount와 CNI 이벤트 |
| CrashLoopBackOff | 프로세스 반복 종료 | 직전 로그, 종료 사유·코드 |
| Running, READY 0/1 | 준비 검사 | readiness 설정과 앱 응답 |
| Ready인데 외부 접속 실패 | 앱 앞의 연결 경로 | Service, endpoint, Ingress, Host |

이벤트는 영구 이력이 아니다. 앱 로그가 없다는 사실도 앱이 로그를 남기기 전에
시작 실패했을 가능성을 포함한다. exit code 하나만으로 원인을 확정하지 않는다.

## 우리 프로젝트에서는

[Airflow 설정](../../../deploy/k8s/helm/airflow/values.yaml)에는 scheduler,
API server, DAG processor의 자원값이 각각 있다. 어느 Pod의 문제가 발생했는지부터
구분한다. API server가 Ready여도 DAG import나 worker 실행은 별도 검증 대상이다.

## 직접 확인하기

먼저 실제 이름을 찾는다.

```sh
kubectl --context k3d-dev -n finance-platform get pods -o wide
kubectl --context k3d-dev -n finance-platform get events \
  --sort-by=.metadata.creationTimestamp
```

아래의 `실제-Pod-이름`과 `실제-컨테이너-이름`은 조회 결과의 값으로 바꾼다.
이벤트의 사유와 시간, Pod의 NODE·READY·RESTARTS를 연결한다.

```sh
kubectl --context k3d-dev -n finance-platform describe pod 실제-Pod-이름
kubectl --context k3d-dev -n finance-platform logs 실제-Pod-이름 \
  -c 실제-컨테이너-이름 --tail=80
kubectl --context k3d-dev -n finance-platform logs 실제-Pod-이름 \
  -c 실제-컨테이너-이름 --previous --tail=80
```

`-c`는 Pod 안의 컨테이너를 선택한다. `--previous`는 같은 Pod에서 직전 종료한
컨테이너의 로그다. 직전 컨테이너가 없으면 오류가 정상일 수 있다. 삭제된 옛 Pod의
로그를 복구하는 옵션은 아니다. 로그는 읽어도 인증값이 있으면 공유하지 않는다.

## 이해 확인

1. 이미지 다운로드 실패를 앱 Python 로그만으로 조사할 수 있는가?
2. API server Ready만 보고 DAG 실행까지 정상이라고 판단해도 되는가?

**해설:** 앱이 시작되지 않았으므로 Pod 이벤트가 먼저다. 준비 상태는 해당 컴포넌트의
검사 결과이며, 전체 작업 경로는 기능별로 확인해야 한다.

더 읽기: [Pod 진단](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/).

---

[전체 목차](../README.md) · [이전: 14장. 설정·인증정보·실행 신원·권한](14-configuration-and-access.md) · [다음: 16장. Helm과 파일·실행 설정의 차이](16-helm-and-changes.md)
