# Kubernetes 4: 상태·이벤트·로그로 진단하기

## 학습 목표

경고 문구 하나만 보고 재시작하지 않고 현재 상태와 발생 시점을 대조한다.

## 기본 순서

```sh
kubectl --context k3d-dev -n finance-platform get pods
kubectl --context k3d-dev -n finance-platform describe pod <POD_NAME>
kubectl --context k3d-dev -n finance-platform get events --sort-by=.lastTimestamp
```

먼저 Ready, 재시작 횟수, Pod 나이, 종료 이유, 이벤트의 마지막 발생 시점을 본다.
필요한 컴포넌트의 로그만 읽고 공유 전 인증값을 지운다. 특히 Airflow 3의 scheduler
workload 로그에는 task JWT가 포함될 수 있으므로 원문 전체를 GitHub에 올리지 않는다.

## 세 가지 probe

| Probe | 질문 | 실패하면 |
| --- | --- | --- |
| startup | 앱이 시작을 마쳤는가? | 설정된 횟수까지 기다리고 실패하면 컨테이너 재시작 |
| readiness | 지금 요청을 받아도 되는가? | 서비스 endpoint에서 제외, 그 자체로 재시작하지 않음 |
| liveness | 실행 중 프로세스가 살아 있는가? | 설정된 실패 기준에 따라 컨테이너 재시작 |

실제 Headlamp에서 Pod 시작 직후 `:4466 connection refused` readiness 경고가
한 번 발생했지만 이후 Ready 1/1, 재시작 0회로 정상화됐다. 이는 현재 장애와
과거 시작 단계 이벤트를 구분해야 하는 예다.
[Pod 생명주기·probe](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/).

## 증상별 확인 위치

| 증상 | 먼저 볼 곳 |
| --- | --- |
| Pending | describe Events: CPU/메모리, PVC binding, node affinity |
| ImagePullBackOff | 이미지명·태그·아키텍처·registry 접근·k3d import 여부 |
| CrashLoopBackOff | 이전 종료 이유와 이전 컨테이너 로그 |
| OOMKilled | memory limit, 앱 메모리 사용량 |
| Running / Ready 0/1 | probe 주소·포트와 앱 시작 완료 여부 |
| HTTP 401/403 | 인증 실패인지 RBAC 거부인지 분리 |
| HTTP 404 | Ingress host/path/class |
| HTTP 502/503 | Service targetPort, selector, endpoint, Pod Ready |

`kubectl` 자체의 `operation not permitted`는 요청이 Kubernetes API에 도착하기
전에 실행 환경에서 막힌 것일 수 있다. Kubernetes가 반환한 `Forbidden`과 구분한다.

## 실패 Pod를 지우기 전에

현재 Airflow는 실패 worker Pod를 남기도록 설정돼 있다. 상태·이벤트·필요한 로그를
확인한 뒤 정리해야 한다. Pod를 지우면 실패 원인 일부를 잃을 수 있다.
이벤트는 영구적인 감사 기록이 아니므로 장기 이력은 별도 수집 체계가 필요하다.

## 확인 문제

1. 어제 경고가 한 번 있었지만 지금 Ready 1/1이면 바로 재시작해야 하는가?
2. readiness 실패가 발생하면 항상 restartCount가 증가하는가?

**해설:** 현재 재현 여부와 영향부터 확인한다. readiness 실패만으로 컨테이너가
재시작되지는 않으며 liveness/startup 실패와 동작이 다르다.
