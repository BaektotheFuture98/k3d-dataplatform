# Traefik: 브라우저 요청을 Service로 라우팅하기

## 학습 목표

Ingress 선언과 Ingress controller의 차이를 이해한다.

## 개념과 현재 구성

Ingress 객체에 host/path를 써도 이를 해석해 요청을 전달하는 controller가 필요하다.
이 프로젝트는 K3s의 Traefik을 사용하며 앱 Ingress class는 `traefik`이다.
`platform-ui`는 Airflow와 Jupyter를 구분하고 Headlamp는 별도 Ingress를 사용한다.
이번 조사에서 kube-system의 현재 Pod 목록을 확인하지 못했으므로 Traefik의
실시간 image/version이나 Pod 개수를 추정해 기입하지 않았다.

```text
Host: airflow.localhost → airflow-api-server:8080
Host: jupyter.localhost → jupyter:8888
Host: <HEADLAMP_HOST> → BasicAuth → headlamp:80 → Pod:4466
```

## 설정을 읽는 법

`deploy/k8s/manifests/ingress/platform-ui.yaml`에는
`networking.k8s.io/v1`, kind `Ingress`, ingressClassName `traefik`와 각 host의
backend Service가 선언돼 있다. Ingress의 포트는 컨테이너 포트가 아니라 우선
Service의 포트다.

Jupyter의 Tailnet `:8443` 경로는 별도 `IngressRoute`가 `X-Forwarded-Host`
헤더를 보고 구분한다. 포트 번호만 바꾸고 host/header 라우팅을 확인하지 않으면
원치 않는 앱으로 갈 수 있다.

Headlamp는 `Middleware`의 BasicAuth를 연결한다. Secret에 저장된 password
hash를 검증하고 `removeHeader: true`로 Basic Authorization 헤더를 뒤쪽 앱에
전달하지 않는다. Middleware 이름은 annotation에서 namespace까지 포함해 참조한다.

## 조회 실습

```sh
kubectl --context k3d-dev -n finance-platform get ingress
kubectl --context k3d-dev -n finance-platform get middleware headlamp-basic-auth
kubectl --context k3d-dev -n finance-platform get ingressroute tailscale-jupyter
```

CRD인 Middleware/IngressRoute와 표준 Ingress를 구분해 본다.
다음은 라우팅 규칙만 확인하는 로컬 요청이다.

```sh
curl --noproxy '*' -I -H 'Host: airflow.localhost' http://127.0.0.1:8080/
```

로그인으로의 redirect는 앱 도달을 의미할 수 있다. 404가 나오면 요청 Host와
Ingress 규칙, 503이면 Service endpoint를 확인한다.

## 확인 문제

1. Ingress host를 바꾸면 인터넷 DNS도 자동으로 생성되는가?
2. BasicAuth middleware를 만들기만 하면 모든 Ingress에 적용되는가?

**해설:** DNS는 별도 설정이다. Middleware를 대상 router/Ingress에 연결해야 한다.

참고: [Traefik BasicAuth](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/basicauth/).
