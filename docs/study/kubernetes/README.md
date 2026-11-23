# Kubernetes 참고: 지금 떠 있는 Pod 이해하기

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [7장](../chapters/07-declaration-to-pod.md) · [8장](../chapters/08-pod-lifecycle.md) · [9장](../chapters/09-workload-controllers.md).

## 학습 목표

Pod와 컨테이너, Deployment, StatefulSet, Job의 관계를 실제 리소스에 연결한다.

## 기본 개념

Pod는 하나 이상의 컨테이너를 함께 배치하는 단위다. 같은 Pod 안의 컨테이너는
네트워크 공간과 지정한 볼륨을 공유한다. Deployment는 원하는 수의 교체 가능한
Pod를 유지하고, StatefulSet은 안정된 이름과 저장소 연결이 필요한 앱을 관리한다.
Job은 완료되는 작업을 위한 컨트롤러다.

| 예시 | 리소스 | 이유 |
| --- | --- | --- |
| `dev/headlamp` | Deployment | 상주 프로세스, 교체 가능한 Pod |
| `jenkins/jenkins` | StatefulSet | 안정된 식별자와 데이터 볼륨 |
| 이전 Airflow executor worker | 직접 생성한 임시 Pod | 태스크 하나 실행 후 정리 |
| 향후 collector | Kubernetes Job 템플릿 | 작업 완료·실패·재시도 관리 |

KubernetesExecutor의 worker가 반드시 Job에 소속되는 것은 아니다.
이전 Airflow 구성의 executor는 Kubernetes API로 worker **Pod**를 직접 생성했다.

## 현재 namespace

2026-11-24 기준 앱 배포 대상은 `dev`·`stage`·`prod`이고, 이전 `finance-platform`은
삭제됐다. Headlamp는 `dev`, Jenkins와 Argo CD는 `jenkins`와 `argocd`에 있다.
`kube-system`의 CoreDNS는 서비스 이름을 IP로 해석하는 클러스터 DNS다.

```sh
kubectl --context k3d-dev -n dev get pods,deployment
kubectl --context k3d-dev -n jenkins get statefulset,pvc
# 환경 권한이 허용하는 터미널에서 시스템 Pod도 조회한다.
kubectl --context k3d-dev -n kube-system get pods
```

`Running`은 Pod 실행 단계이고 `READY 1/1`은 컨테이너의 준비 상태다.
Running이지만 Ready 0/1일 수 있다. `AGE`는 Pod가 만들어진 시점이고,
Deployment의 나이는 그보다 훨씬 오래됐을 수 있다.

## 설정 방법

설정 파일에서 `spec.replicas`, `spec.template.spec.containers`, `resources`,
`volumes` 등을 선언한다. Kubernetes는 현재 상태를 선언한 원하는 상태로 맞춘다.
`bronze-to-silver`와 `silver-to-gold`는 저장소 템플릿에 `replicas: 0`으로 선언돼 있다.
두 Deployment가 적용된 환경에서는 이 값이 실행 Pod를 0개로 맞춘다.

## 실습: 주인을 따라가기

```sh
kubectl --context k3d-dev -n dev get pods \
  -o 'custom-columns=NAME:.metadata.name,OWNER_KIND:.metadata.ownerReferences[0].kind,OWNER:.metadata.ownerReferences[0].name'
kubectl --context k3d-dev -n dev get replicasets
kubectl --context k3d-dev -n jenkins get pods,statefulsets
```

Deployment → ReplicaSet → Pod 순서와 StatefulSet → Pod 순서를 찾아본다.
목록에 여러 세대의 ReplicaSet이 있어도 모두 실행 중이라는 뜻은 아니다.

## 확인 문제

1. Deployment가 replicas=1일 때 Pod만 삭제하면 왜 다시 생기는가?
2. 성공한 Airflow task가 있는데 worker Pod가 없는 이유는?

**해설:** 컨트롤러가 원하는 개수를 복구한다. 이전 Airflow 구성의 executor는 성공한
worker를 삭제했다. 실행 상태는 Airflow 메타데이터 DB, 로그는 PVC에 남았다.

다른 참고 자료: [네트워크](02-networking.md), [저장소·권한](03-storage-and-security.md),
[장애 진단](04-troubleshooting.md).
