# Mac에서 Jupyter와 Airflow 접속

## Tailscale 접속

2026-10-19 Tailscale Serve를 다음과 같이 연결했다. 접속 기기는 같은 Tailnet에 연결되어
있어야 하며 기존 Airflow 로그인과 Jupyter 토큰 인증을 사용한다.

| 서비스 | HTTPS 주소 |
| --- | --- |
| Airflow | <https://seonmin-mac-mini.tail481f72.ts.net> |
| Jupyter | <https://seonmin-mac-mini.tail481f72.ts.net:8443> |

2026-10-19 최초 수신 PacketFilter 확인 결과,
MacBook `100.70.20.73`에는 기존 Service VIP의 지정 포트만 허용되며
Mac Mini `100.80.212.1`의 TCP 443·8443 허용 규칙이 없다. 따라서 서버 자체의
HTTPS 검사 성공은 MacBook에서의 접속 성공을 의미하지 않는다.

[Tailscale Access controls](https://login.tailscale.com/admin/acls)의 기존 `grants` 배열에
`tailscale-web-grant.json`의 객체를 추가한다. 기존 정책 전체를 이 객체로 교체하지 않는다.
이는 해당 MacBook에서 Mac Mini의 두 웹 포트로의 접속만 허용하는 규칙이다.
사용자가 정책을 저장한 뒤 수신 PacketFilter에서 MacBook `100.70.20.73` →
Mac Mini `100.80.212.1`의 TCP 443·8443 허용 반영을 확인했다.
서버에서 두 HTTPS 주소는 HTTP 200이며, MacBook 브라우저에서의 접속은 사용자 확인이 필요하다.

```text
Tailnet → Mac Tailscale Serve :443 / :8443
  → 127.0.0.1:8080 → Traefik → Airflow / Jupyter
```

Airflow는 Ingress의 Tailnet 호스트 규칙을 사용한다. Jupyter는 `tailscale-jupyter`
IngressRoute가 Serve의 `X-Forwarded-Host`에 포함된 `:8443`을 구분해 전달한다.
Serve는 백그라운드 설정으로 저장되며 Tailscale 데몬이 실행 중이어야 한다.

```sh
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/k8s/manifests/ingress/platform-ui.yaml -f deploy/k8s/manifests/ingress/tailscale-jupyter.yaml
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/ingress/platform-ui.yaml -f deploy/k8s/manifests/ingress/tailscale-jupyter.yaml
tailscale serve --bg --https=443 http://127.0.0.1:8080
tailscale serve --bg --https=8443 http://127.0.0.1:8080
tailscale serve status
```

두 서비스는 Tailscale IP `100.80.212.1`에 `curl --resolve`로 연결해 TLS 인증서 검증과
HTTP 200 및 페이지 제목을 확인했다. 다른 Tailnet 기기에서의 브라우저 로그인·커널
WebSocket 동작은 별도 검증이 필요하다. 기존 `svc:jupyter` 별칭은 DNS 조회가
NXDOMAIN을 반환해 이번 접속 주소로 사용하지 않았다.

호스트 Mac은 Tailscale 내부 DNS 조회에는 성공하지만 macOS resolver에 Tailnet용
nameserver가 없어 일반 이름 해석은 실패했다. 필요하면 관리자 권한으로 해당 도메인에만
DNS resolver를 지정한다. 이 변경은 아직 적용하지 않았다.

```sh
printf 'nameserver 100.100.100.100\n' | sudo tee /etc/resolver/tail481f72.ts.net
```

이번에 추가한 Serve 포트만 끄려면 아래 명령을 사용한다. 기존 서비스 설정도 지워지는
`tailscale serve reset`은 사용하지 않는다.

```sh
tailscale serve --https=443 off
tailscale serve --https=8443 off
```

## 로컬 접속

기존 k3d `dev` 클러스터의 Traefik을 사용한다. 애플리케이션 Service는 ClusterIP를 유지하고,
`finance-platform/platform-ui` Ingress가 호스트 이름에 따라 요청을 전달한다.

| 주소 | 대상 |
| --- | --- |
| <http://jupyter.localhost:8080> | `jupyter:8888` |
| <http://airflow.localhost:8080> | `airflow-api-server:8080` |

```text
Mac 127.0.0.1:8080
  → k3d-dev-serverlb:80
  → k3d-dev-server-0:80 / Traefik
  → platform-ui Ingress
  → ClusterIP Service
  → Jupyter 또는 Airflow Pod
```

`.localhost`는 로컬 접속용 이름이며 최신 브라우저와 curl에서 루프백으로 해석된다.
별도 hosts 파일 변경은 하지 않는다. 이름 해석을 지원하지 않는 클라이언트에서는
아래의 `--resolve` 방식으로 라우팅을 확인할 수 있다.

Jupyter는 기존 `jupyter-auth/token`, Airflow는 기존 `airflow-admin` Secret의 계정으로 로그인한다.
인증을 비활성화하거나 자격증명을 URL·문서에 넣지 않는다.

## 적용과 복구

저장소 루트에서 Ingress를 검증·적용한다. Traefik이 Ready여야 한다.

```sh
kubectl --context k3d-dev -n kube-system get deployment traefik
kubectl --context k3d-dev -n finance-platform apply --dry-run=server -f deploy/k8s/manifests/ingress/platform-ui.yaml
kubectl --context k3d-dev -n finance-platform apply -f deploy/k8s/manifests/ingress/platform-ui.yaml
```

Mac 포트 매핑은 Kubernetes 리소스가 아닌 Docker/k3d 설정이다.
현재 로드밸런서에 매핑이 없다면 아래 명령으로 추가한다. 이미 있으면 반복 실행하지 않는다.

```sh
docker inspect k3d-dev-serverlb --format '{{json .HostConfig.PortBindings}}'
k3d node edit k3d-dev-serverlb --port-add 127.0.0.1:8080:80
```

이 명령은 기존 로드밸런서 컨테이너를 교체하므로 Kubernetes API 연결이 잠시 끊길 수 있다.
서버 노드와 앱 Pod·PVC는 유지한다. 기존 API 포트 `59772:6443`도 유지한다.
클러스터를 새로 만들 경우에는 생성 옵션 `-p '127.0.0.1:8080:80@loadbalancer'`로 선언할 수 있다.
현재 클러스터를 재생성할 필요는 없다.

## 확인

```sh
kubectl --context k3d-dev -n finance-platform get ingress platform-ui
curl --noproxy '*' -I http://jupyter.localhost:8080/login
curl --noproxy '*' -I http://airflow.localhost:8080/

# 로컬 이름 해석과 분리하여 Ingress 라우팅 확인
curl --noproxy '*' --resolve jupyter.localhost:8080:127.0.0.1 -I http://jupyter.localhost:8080/login
```

HTTP 200 또는 로그인으로의 리다이렉트는 UI 접근 성공이다.
실제 인증·WebSocket 등 실행 검증은 [인프라 실행 기록](../runtime/VALIDATION.md)에 남긴다.

연결 거부는 Mac 포트 매핑을, HTTP 404는 Ingress host/class를,
HTTP 502/503은 대상 Service의 EndpointSlice와 Pod Ready 상태를 확인한다.

구성 근거: [k3d 공식 Ingress 노출 안내](https://k3d.io/v5.4.7/usage/exposing_services/).
