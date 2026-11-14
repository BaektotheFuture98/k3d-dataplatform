# 4장. Kubernetes·K3s·k3d는 무엇이 다른가

## 왜 필요한가

세 이름은 별개의 Pod 문법 세 개를 뜻하지 않는다. **기능 체계, 배포판,
클러스터를 구성하는 도구**를 구분하면 공부할 대상이 선명해진다.

## 어떻게 동작하는가

**Kubernetes**는 컨테이너화한 앱을 선언한 상태에 맞게 관리하는 시스템이다.
“이 이미지의 앱을 1개 유지해 줘”라는 목표를 주면 현재 상태와 비교하며 맞춰 간다.
한 번 실행하고 끝나는 스크립트가 아니라 계속 제어하는 시스템이다.

**K3s**는 Kubernetes를 설치·운영하기 쉽게 묶은 배포판이다. Kubernetes API와
Pod·Deployment 같은 리소스를 사용하며 실행 구성 요소와 기본 도구들을 함께 제공한다.

**k3d**는 Docker 안에 K3s 노드를 구성하는 도구다. 장비 여러 대 대신 컨테이너를
노드로 사용한다. 앱 상태를 지속해서 맞추는 주체는 k3d CLI가 아니라 노드 안의
Kubernetes 구성 요소다.

| 이름 | 책임 | 프로젝트 예 |
| --- | --- | --- |
| Kubernetes | 리소스 API와 앱 관리 동작 | Deployment, Pod, Service |
| K3s | Kubernetes 배포판과 실행 구성 | API server, kubelet, containerd |
| k3d | 컨테이너 기반 클러스터 구성 | dev 클러스터, 노드 컨테이너 |
| kubectl | Kubernetes API에 요청 | Pod 목록 조회 |
| Helm | 앱 리소스를 템플릿으로 묶어 배포 관리 | Airflow chart와 values |

K3s의 기본 제공 항목에는 containerd, CoreDNS, Traefik, ServiceLB,
local-path provisioner 등이 있다. **기본 제공**과 **내 클러스터에서 실제 활성화**는
다르다. 설치 옵션과 버전에 따라 달라질 수 있으므로 실제 리소스로 대조한다.

## 우리 프로젝트에서는

[namespace 선언](../../../deploy/k8s/namespace.yaml)과
[Jupyter Deployment](../../../deploy/k8s/manifests/spark/jupyter.yaml)는 표준
Kubernetes 리소스다. 다른 배포판에서도 기본 개념은 같다. 이미지 반입·외부 접속·
저장소 클래스 같은 환경별 연결은 달라진다.

기존 관측의 K3s 버전은 `v1.35.5+k3s1`이다. k3d CLI 버전과 실행 중인 Kubernetes
서버 버전, 앱 버전은 별도다. 같은 숫자를 기대하지 않는다.

## 직접 확인하기

```sh
k3d version
kubectl --context k3d-dev version
kubectl --context k3d-dev get nodes -o wide
```

첫 명령은 k3d 도구 정보를 보여 준다. 기본 K3s 이미지 버전이 나오더라도 실행 중인
노드 버전을 대신하지 않는다. 둘째는 Kubernetes 클라이언트·서버 버전, 셋째는
실제 노드와 runtime을 보여 준다. 노드 출력의 형태는 다음과 같다. 값은 예시다.

```text
NAME               STATUS   ROLES           VERSION      ... CONTAINER-RUNTIME
k3d-dev-server-0   Ready    control-plane   v...+k3s...   ... containerd://...
```

## 이해 확인

1. k3d CLI 명령이 끝났는데도 앱이 유지되는 이유는?
2. K3s를 쓰면 Deployment와 Service를 공부하지 않아도 되는가?

**해설:** 클러스터의 상주 프로세스가 계속 제어한다. K3s는 Kubernetes 배포판이므로
그 리소스와 동작 원리를 그대로 이해해야 한다.

근거: [K3s 소개](https://docs.k3s.io/), [k3d 프로젝트 구조](https://k3d.io/stable/design/project/).

---

[전체 목차](../README.md) · [이전: 3장. Colima와 Docker의 역할](03-colima-docker.md) · [다음: 5장. k3d 클러스터의 server·agent·serverlb](05-k3d-cluster.md)
