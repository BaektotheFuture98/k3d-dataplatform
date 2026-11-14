# 5장. k3d 클러스터의 server·agent·serverlb

## 왜 필요한가

`k3d-dev-server-0`와 `k3d-dev-serverlb`는 둘 다 Docker 컨테이너일 수 있다.
그렇다고 둘 다 Kubernetes 노드는 아니다. 이름과 책임을 연결해 보자.

## 어떻게 동작하는가

**server 노드**는 K3s 제어 평면과 datastore 역할을 맡는다. 기본 구성에서는
앱 실행에 필요한 kubelet·containerd도 실행한다. server 하나뿐이어도 앱을 배치할 수 있다.

**agent 노드**는 제어 평면 없이 앱 실행에 참여한다. server에 연결해 관리받고
자기 노드에 배정된 Pod를 실행한다. agent가 없다고 앱 실행 기능이 없는 것은 아니다.

**serverlb**는 k3d의 프록시 컨테이너다. Kubernetes API 연결 등을 노드로 전달하고
설정된 앱 포트 매핑도 전달할 수 있다. Kubernetes 노드가 아니므로 노드 개수에 포함하지 않는다.

```text
Docker가 관리하는 컨테이너
├─ k3d-dev-serverlb    : 연결을 전달하는 프록시
└─ k3d-dev-server-0   : K3s server 노드
   ├─ 제어 기능
   └─ 앱 Pod 실행 기능
```

여러 노드는 앱 배치 대상을 늘려 준다. 하지만 같은 VM 안의 컨테이너 노드들은
VM 장애를 공유한다. 컨테이너 노드 3개가 독립된 물리 장비 3대와 같은 가용성은 아니다.

**클러스터 이름** `dev`와 **context 이름** `k3d-dev`도 구분한다.
앞의 이름은 k3d의 관리 대상이고 뒤의 이름은 kubectl의 연결 설정이다.
**kubeconfig**는 클러스터 주소·인증정보 참조·context 등을 담은 설정이다.
전체 파일을 공개할 필요 없이 context 목록으로 연결 대상을 확인한다.

## 우리 프로젝트에서는

과거 기록상 server 1개인 `dev` 클러스터다. 생성 옵션 전체가 저장소에 선언돼
있다고 가정하지 않는다. 현재 노드 수와 포트는 조회해 확인한다.
앱 YAML 재배포와 노드 컨테이너 재생성은 전혀 다른 범위의 작업이다.

## 직접 확인하기

```sh
k3d cluster list
kubectl config get-contexts
kubectl --context k3d-dev get nodes
docker inspect k3d-dev-serverlb --format '{{json .HostConfig.PortBindings}}'
```

첫 출력의 SERVERS/AGENTS와 셋째 노드 목록을 비교한다. 둘째 출력의 `*`는 기본
선택 context다. 명령에 `--context`를 쓰면 그 context를 직접 선택한다.
넷째는 serverlb 포트 매핑만 조회한다.

예를 들어 컨테이너 `80/tcp`에 호스트 포트 `8080`이 연결돼 있으면 호스트 8080의
요청을 컨테이너 80으로 전달한다는 뜻이다. 실제 출력이 다르면 실제 매핑을 따른다.
모든 계층의 포트 번호가 같아야 하는 것은 아니다.

## 이해 확인

1. server 1개와 serverlb 1개이면 Kubernetes 노드는 몇 개인가?
2. agent가 없어도 PostgreSQL Pod가 실행될 수 있는가?

**해설:** serverlb는 노드가 아니므로 이 구성의 노드는 1개다. 기본 server에는
앱 실행 기능도 있어서 배치 제한과 자원이 허용하면 Pod를 실행한다.

근거: [k3d 노드 역할](https://k3d.io/stable/design/project/),
[K3s server와 agent](https://docs.k3s.io/architecture).

---

[전체 목차](../README.md) · [이전: 4장. Kubernetes·K3s·k3d는 무엇이 다른가](04-kubernetes-k3s-k3d.md) · [다음: 6장. K3s 내부: 결정하는 쪽과 실행하는 쪽](06-k3s-internals.md)
