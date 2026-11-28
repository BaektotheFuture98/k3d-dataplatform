# Headlamp

공식 Helm chart 0.46.0과 이미지 `ghcr.io/headlamp-k8s/headlamp:v0.46.0`을
`platform-tools`에 설치한다. 별도 DB/PVC/플러그인 관리 sidecar는 사용하지 않는다.
Pod 1개, CPU request/limit 100m/500m, 메모리 request/limit 128Mi/512Mi이다.
설치 직후 측정값은 CPU 1m, 메모리 14Mi이며 사용량은 화면·작업에 따라 달라진다.

## Tailscale

접속 주소: <https://headlamp.tail481f72.ts.net>

```text
MacBook → svc:headlamp HTTPS :443 → Mac Mini 127.0.0.1:8080
  → Traefik Ingress headlamp.tail481f72.ts.net → headlamp:80 → Pod:4466
```

다음 광고 설정은 적용 완료했다. 사용자가 서비스 정의·호스트 승인과 접근 규칙 추가를
완료했고, 서버에서 서비스 VIP `100.72.156.163`과 MacBook → 서비스 TCP 443 허용 반영을 확인했다.

```sh
tailscale serve --service=svc:headlamp --https=443 http://127.0.0.1:8080
```

1. [Services](https://login.tailscale.com/admin/services)에서 `headlamp` 서비스를 정의한다.
   이름은 `headlamp`, endpoint는 `tcp:443`으로 지정한다. 이미 있으면 재생성하지 않는다.
2. 해당 서비스의 pending host인 `seonmin-mac-mini`를 승인한다.
3. [Access controls](https://login.tailscale.com/admin/acls)의 기존 `grants` 배열에
   다음 객체를 추가한다. 전체 정책을 교체하지 않는다.

```json
{
  "src": ["autogroup:member"],
  "dst": ["svc:headlamp"],
  "ip": ["443"]
}
```

같은 내용은 `configs/headlamp/tailscale-grant.json`에 있다.
이 규칙은 Headlamp 서비스의 443에만 접근을 허용하며 기존 Mac Mini 기기 IP의
443·8443 허용 규칙을 변경하지 않는다.

## 로그인과 Kubernetes 권한

2026-11-13부터 브라우저의 비밀번호 입력창에서 공유 `admin` 계정으로 로그인한다.
비밀번호는 로컬 Secret 파일의 BCrypt 해시로 관리하며 Git에 저장하지 않는다.
설정과 적용·복구 방법은 [BASIC-AUTH.md](BASIC-AUTH.md)에 있다.
Traefik이 모든 Ingress 요청을 인증하며, Headlamp는 자동 갱신되는 Pod 토큰을 사용한다.
따라서 사용자가 로그인 토큰을 직접 재발급할 필요가 없다.

수동 토큰 로그인을 복구했을 때 사용할 명령은 다음과 같다.

```sh
kubectl --context k3d-dev -n platform-tools create token headlamp-user --duration=8h
```

처음 발급한 토큰은 `/private/tmp/finance-headlamp-login-token.txt`에 모드 600으로 저장했다.
해당 토큰의 만료 시 새로 발급한다. 토큰은 Git에 저장하지 않는다.

서버 Pod는 기존 로그인용 `headlamp-user` ServiceAccount를 사용한다.
비밀번호 인증을 통과한 사용자는 이 계정의 다음 권한을 공유한다.

- 클러스터 전역의 기본 `view` 역할: 일반 워크로드 및 로그 조회.
- 노드·namespace·PV·metrics 읽기.

UI 토큰 로그인 생략 옵션 `unsafeUseServiceAccountToken`은 true다.
비밀번호 인증은 Traefik의 `headlamp-basic-auth` 미들웨어가 담당한다.

## 설치와 검증

```sh
# 공식 차트 0.46.0 다운로드 후 SHA-256 대조
# faa471a8c5c55125b3dceed1cf73000e1ced18f07e2088e5e12e75292fb9ae62
kubectl --context k3d-dev -n platform-tools apply --dry-run=server \
  -f deploy/k8s/helm/headlamp/access.yaml \
  -f configs/headlamp/basic-auth-secret.local.json \
  -f deploy/k8s/helm/headlamp/basic-auth.yaml
kubectl --context k3d-dev -n platform-tools apply \
  -f deploy/k8s/helm/headlamp/access.yaml \
  -f configs/headlamp/basic-auth-secret.local.json \
  -f deploy/k8s/helm/headlamp/basic-auth.yaml
/private/tmp/finance-platform-tools/helm upgrade --install headlamp \
  /private/tmp/finance-platform-tools/headlamp-0.46.0.tgz \
  --kube-context k3d-dev --namespace platform-tools \
  -f deploy/k8s/helm/headlamp/values.yaml --hide-notes --atomic --wait --timeout 3m
```

재배포 후 [비밀번호 로그인 검증 절차](BASIC-AUTH.md)에 따라 Ingress의 인증 응답과
`lakehouse`·`pipelines`·`platform-tools`의 Pod 조회를 확인한다. 서비스 호스트의 DNS에서 서비스 이름이
해석되지 않으면 tailnet 클라이언트에서 확인하거나 서비스 VIP에 `curl --resolve`로
접속해 HTTPS 응답을 확인한다.

공식 문서: [Headlamp 설치](https://headlamp.dev/docs/latest/installation/in-cluster/),
[Tailscale Services](https://tailscale.com/docs/features/tailscale-services).
