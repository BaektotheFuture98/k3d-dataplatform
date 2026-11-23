# Headlamp: Kubernetes를 보는 웹 UI

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [14장](../chapters/14-configuration-and-access.md) · [15장](../chapters/15-observing-and-debugging.md).

## 학습 목표

관리 화면도 Pod로 실행된다는 점과, UI 로그인·Kubernetes 권한의 차이를 이해한다.

## 현재 구성

Headlamp 0.46.0을 `dev`의 Deployment 1개로 실행한다.
Service는 80번, 실제 앱은 4466번 포트다. DB나 별도 PVC는 사용하지 않는다.
화면에 Headlamp 자신의 Pod가 나타나는 것이 정상이다.

CPU request/limit는 100m/500m, 메모리는 128Mi/512Mi다.
접속은 `<HEADLAMP_HOST>`로 표시하며 실제 개인 주소는 공개 문서에 넣지 않는다.

## 현재 로그인 방식

```text
브라우저 → Tailscale HTTPS → Traefik BasicAuth
  → Headlamp → headlamp-user 신원으로 Kubernetes API
```

Headlamp 자체의 사용자 DB에 아이디·비밀번호를 등록한 구성이 아니다.
Traefik이 비밀번호를 확인하고 Headlamp가 Pod의 자동 갱신 ServiceAccount 토큰을
사용한다. 사용자에게 8시간 토큰을 계속 발급·복사하게 하는 이전 방식을 대체했다.

| 설정 | 현재 값 |
| --- | --- |
| config.inCluster | true |
| config.unsafeUseServiceAccountToken | true |
| serviceAccount.name | headlamp-user |
| serviceAccount.create | false |
| Middleware | headlamp-basic-auth |
| Password Secret | headlamp-basic-auth, BCrypt hash |

`unsafeUseServiceAccountToken`은 방문자마다 다른 Kubernetes 신원을 쓰지 않고
서버 신원을 공유한다는 뜻이다. 인증 프록시 없이 단독으로 켜는 설정으로 이해하면
안 된다. 현재 Headlamp 내부 Service에 직접 닿는 경로는 ingress 인증을 거치지
않으므로 네트워크 신뢰 경계도 함께 고려한다.

## 권한

`headlamp-user`는 전역 view 계열 조회와 node/namespace/PV/metrics 읽기,
`dev`의 edit 권한을 가진다. 이 권한은 `dev`의 Secret 접근과 워크로드 변경을
포함한다. `stage`와 `prod`에서는 조회 권한만 있다. 모든 방문자는 같은 신원의
권한을 공유한다.

## 설정 확인 실습

```sh
kubectl --context k3d-dev -n dev get deployment headlamp
kubectl --context k3d-dev -n dev get ingress headlamp
kubectl --context k3d-dev -n dev get middleware headlamp-basic-auth
kubectl --context k3d-dev -n dev get serviceaccount headlamp-user
```

비밀번호 값과 hash를 학습 노트에 복사하지 않는다. 변경할 때는 로컬의 제한된
파일에서 새 hash를 생성하고 Secret을 갱신한다. 기존 Secret이 없는 신규 환경에는
현재 로컬 파일이 자동 전송되지 않으므로 별도 준비가 필요하다.

## 현재 검증 범위

`dev`의 Headlamp Pod는 Ready 1/1이다. 서비스 API에서 각 환경과 전체
네임스페이스의 PodList 응답을 확인했다. Tailscale 서비스 VIP에 HTTPS로 접속하면
미인증·잘못된 인증 요청에 401이 반환된다. 원격 클라이언트의 DNS 및 브라우저
로그인은 별도 확인이 필요하다.

## 확인 문제

1. Headlamp에서 어떤 Pod를 수정하면 실제 cluster가 바뀌는가?
2. 비밀번호가 서로 다른 사용자에게 서로 다른 RBAC를 주는 현재 구성인가?

**해설:** UI는 실제 Kubernetes API를 호출하므로 권한이 있으면 변경된다.
현재는 공유 BasicAuth/ServiceAccount 방식이고 사용자별 신원 분리는 아니다.

참고: [Headlamp BasicAuth](https://headlamp.dev/docs/latest/installation/in-cluster/basic-auth/),
[고정 chart 값](https://github.com/kubernetes-sigs/headlamp/blob/v0.46.0/charts/headlamp/values.yaml).
