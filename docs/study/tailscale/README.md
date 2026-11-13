# Tailscale: 다른 기기에서 내부 웹 도구에 접속하기

## 학습 목표

네트워크 접근 허용, HTTPS 제공, 앱 로그인이 각각 다른 층임을 이해한다.

## 현재 접속 구조

```text
같은 Tailnet의 기기
  → Tailscale Serve HTTPS
  → 서버의 127.0.0.1:8080
  → Traefik → Airflow / Jupyter / Headlamp
```

Airflow는 서버의 HTTPS 기본 포트, Jupyter는 HTTPS 8443을 사용하도록 구성했다.
Headlamp는 별도 Tailscale Service 이름을 사용한다.
개인 기기 주소와 Tailnet 도메인은 이 공개 문서에서 가렸다.

| 주소 자리 | 대상 |
| --- | --- |
| `https://<AIRFLOW_HOST>` | Airflow |
| `https://<AIRFLOW_HOST>:8443` | Jupyter |
| `https://<HEADLAMP_HOST>` | Headlamp |

Tailscale 정책이 통과해도 Airflow 계정이나 Jupyter 토큰 인증은 별도로 필요하다.
Serve는 앱 인증을 대신하지 않는다. 서버에서 자기 주소로 성공한 검사만으로
다른 기기의 DNS·ACL·브라우저 로그인까지 검증됐다고 할 수 없다.

## 설정 위치

접속 구성은 `configs/ingress/README.md`, 정책 예시는 같은 디렉터리의
`tailscale-web-grant.json`, Headlamp 쪽은 `configs/headlamp/`에 있다.
실제 정책을 수정할 때는 기존 전체 정책을 예제 객체 하나로 교체하지 않는다.

조회 명령:

```sh
tailscale status
tailscale serve status
```

Serve 설정 추가는 상태를 바꾼다. 현재 연결을 바꾸기 전에 기존 Serve 구성을
보관하고 필요한 포트만 조정한다. `serve reset`은 다른 서비스까지 없앨 수 있으므로
단순 접속 점검 수단으로 사용하지 않는다.

## DNS 문제와 앱 문제 분리

1. 이름이 해석되는가?
2. TCP 연결이 가능한가?
3. TLS 인증서가 맞는가?
4. 올바른 Ingress로 가는가?
5. 앱 로그인이 성공하는가?

이 프로젝트의 과거 기록에는 호스트 Mac resolver와 Tailnet DNS가 달라 일반
이름 해석이 실패한 사례가 있다. 그 과거 기록이 모든 현재 기기의 상태를 의미하지는 않는다.

## 확인 문제

1. Tailnet에 연결했는데 앱이 401을 반환하면 네트워크 장애인가?
2. 서버의 curl 성공만으로 MacBook의 ACL 통과를 증명할 수 있는가?

**해설:** 앱의 인증 요구일 수 있다. 원격 기기는 별도의 경로와 정책을 거치므로
해당 기기에서도 확인해야 한다.

참고: [Tailscale Serve](https://tailscale.com/kb/1312/serve).
