# 11장. Mac·VM·노드·Pod의 네트워크 경계

## 왜 필요한가

Mac에서 `localhost:5432`가 안 열려도 Pod에서는 `postgres:5432`가 될 수 있다.
주소는 **어디에서 요청하느냐**와 함께 읽어야 한다.

## 어떻게 동작하는가

`localhost`는 요청하는 프로세스의 네트워크 공간 자신을 가리킨다.
Mac의 localhost, Colima VM의 localhost, 노드 컨테이너의 localhost, 일반 Pod의
localhost는 서로 다르다. 같은 Pod의 컨테이너들은 네트워크 공간을 공유하므로
서로 localhost로 통신할 수 있다. hostNetwork 같은 특수 구성은 별도다.

| 주소 종류 | 주 사용 범위 | 예 |
| --- | --- | --- |
| Mac의 로컬 주소·포트 | Mac에서 접근 | 127.0.0.1:8080 |
| Docker 노드 컨테이너 주소 | Docker 네트워크 | k3d 노드 주소 |
| Pod IP | 클러스터의 Pod 통신 | Pod 교체 시 바뀔 수 있음 |
| Service IP·이름 | 안정된 서비스 접속점 | postgres:5432 |

**CNI**는 컨테이너 네트워크 구성 인터페이스다. K3s는 기본적으로 Flannel을 제공하며
설치 옵션으로 바꿀 수 있다. Pod 간 네트워크와 Docker의 노드 컨테이너 네트워크는
역할이 다르다. 단일 노드에서는 쉬워 보여도 두 계층을 같은 것으로 외우지 않는다.

**포트 매핑**은 바깥 연결을 안쪽 포트로 전달한다. 선언의 `containerPort: 8080`은
그 자체로 Mac 8080을 여는 설정이 아니다. 앱이 포트를 듣고 있어야 하고, 바깥에서
들어오는 별도 연결 경로도 있어야 한다.

```text
Mac 127.0.0.1:8080
  → Colima/Docker의 호스트 포트 전달
  → k3d serverlb의 80
  → 노드의 ingress 진입점
  → Traefik → 앱 Service → 앱 Pod
```

위 경로는 기존 로컬 접속 구성의 개념도다. Docker 엔진은 VM에 있으므로 Mac에서
VM으로의 전달도 필요하다. 실제 노출 주소와 포트는 환경 설정을 조회해 확인한다.

## 우리 프로젝트에서는

[Ingress 선언](../../../deploy/k8s/manifests/ingress/platform-ui.yaml)은
`airflow.localhost`의 HTTP 요청을 Airflow Service로 연결한다.
이 선언이 로컬 호스트 이름 해석과 Mac 포트 매핑까지 모두 생성하는 것은 아니다.

serverlb, K3s ServiceLB, Traefik을 구분한다. serverlb는 Docker 측 프록시,
ServiceLB는 K3s의 LoadBalancer Service 구현, Traefik은 HTTP 라우팅을 수행하는
ingress controller다. ServiceLB 사용 여부는 실제 설치 옵션을 확인해야 한다.

## 직접 확인하기

```sh
docker inspect k3d-dev-serverlb --format '{{json .HostConfig.PortBindings}}'
kubectl --context k3d-dev -n finance-platform get pods -o wide
kubectl --context k3d-dev -n finance-platform get services
```

첫 출력은 호스트↔프록시 포트 연결이다. 둘째 IP는 Pod IP, 셋째 CLUSTER-IP는
Service IP다. 세 출력을 서로 다른 색으로 표시해 보자.
Service가 ClusterIP라면 Mac에서 그 IP로 직접 접속할 수 있다고 가정하지 않는다.

## 이해 확인

1. Airflow worker에서 `localhost:5432`는 PostgreSQL Pod를 뜻하는가?
2. containerPort를 쓰면 Mac 포트도 자동 공개되는가?

**해설:** 일반 worker의 localhost는 worker Pod 자신이다. 다른 Pod의 DB에는
Service 이름으로 연결한다. containerPort 표기만으로 호스트 포트는 공개되지 않는다.

근거: [K3s 네트워크 구성](https://docs.k3s.io/networking/basic-network-options),
[K3s Traefik·ServiceLB](https://docs.k3s.io/networking/networking-services).

---

[전체 목차](../README.md) · [이전: 10장. 이미지와 CPU·메모리가 실행에 관여하는 방법](10-images-and-resources.md) · [다음: 12장. Service·DNS·Ingress로 요청 따라가기](12-services-dns-ingress.md)
