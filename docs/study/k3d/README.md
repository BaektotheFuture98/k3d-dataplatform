# k3d: 컨테이너로 만드는 K3s 개발 클러스터

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [4장](../chapters/04-kubernetes-k3s-k3d.md) · [5장](../chapters/05-k3d-cluster.md) · [6장](../chapters/06-k3s-internals.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

## 학습 목표

k3d와 K3s를 구분하고, API context와 앱 접속 포트의 차이를 이해한다.

## 현재 구성

k3d는 Docker 컨테이너 안에 K3s 노드를 만든다. K3s는 Kubernetes 배포판이고,
k3d는 그 노드를 로컬에서 구성·관리하는 도구다.

| 항목 | 현재 값 |
| --- | --- |
| 클러스터 이름 | `dev` |
| kubectl context | `k3d-dev` |
| 노드 | `k3d-dev-server-0`, 단일 control-plane 노드 |
| K3s 버전 | `v1.35.5+k3s1` |
| 노드 컨테이너 런타임 | containerd 2.2.3 계열, 실제 노드 조회 기준 |
| 앱 진입점 | k3d load balancer → Traefik |

API 서버의 호스트 포트와 `127.0.0.1:8080` 앱 진입 포트는 다르다.
API 포트는 클러스터 생성 시 정해지므로 학습 문서에 특정 번호를 고정하지 않는다.

## 설정을 읽는 순서

```sh
kubectl config get-contexts
kubectl --context k3d-dev cluster-info
kubectl --context k3d-dev get nodes -o wide
k3d cluster list
```

`kubectl`은 선택한 context의 API 서버에 요청한다. Docker socket 접근이 안 되면
`k3d cluster list`는 실패할 수 있지만, 별도 접속 경로의 `kubectl`은 성공할 수도 있다.
둘의 실패를 같은 장애로 단정하지 않는다.

## 로컬 이미지와 웹 포트

```sh
# 변경 예시: 지정 이미지를 현재 클러스터에 반입한다.
k3d image import finance-platform/airflow:study-v1 --cluster dev

# 조회: load balancer의 포트 매핑만 확인한다.
docker inspect k3d-dev-serverlb --format '{{json .HostConfig.PortBindings}}'
```

앱 접속 경로는 다음과 같다.

```text
Mac 127.0.0.1:8080 → k3d serverlb:80 → Traefik → Service → Pod
```

포트 매핑 추가는 기존 load balancer 컨테이너를 교체할 수 있다. 현재 플랫폼을
공부하기 위해 클러스터를 다시 만들거나 포트 매핑을 반복 변경할 필요는 없다.
Pod 교체와 클러스터 삭제는 영향 범위가 전혀 다르다.

## 확인 문제

1. `--cluster dev`와 `--context k3d-dev`는 각각 어떤 도구의 인자인가?
2. 노드 컨테이너를 삭제하면 Pod 하나만 삭제하는 것과 왜 다른가?

**해설:** 전자는 k3d, 후자는 kubectl이다. 노드는 여러 Pod와 로컬 저장소가
동작하는 기반이므로 앱 하나보다 훨씬 넓은 영향을 준다.

참고: [k3d 공식 문서](https://k3d.io/), [K3s 문서](https://docs.k3s.io/).
