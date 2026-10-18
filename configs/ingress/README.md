# Mac에서 Jupyter와 Airflow 접속

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
