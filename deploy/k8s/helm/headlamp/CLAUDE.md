# Headlamp 배포

- Headlamp는 `dev`에서 실행한다. [access.yaml](access.yaml)의 `headlamp-user`는 클러스터 전체 조회와 `dev` 수정 권한을 갖는다. `stage`·`prod`는 조회 범위다.
- [values.yaml](values.yaml)의 Ingress는 [basic-auth.yaml](basic-auth.yaml)의 Traefik 미들웨어를 참조한다. 미들웨어와 Secret은 같은 네임스페이스에 둔다. 브라우저 인증과 Pod의 서비스 계정 토큰 사용은 [인증 가이드](../../../../configs/headlamp/BASIC-AUTH.md)에 기록돼 있다.
- 검증은 Deployment Ready, 세 환경의 조회 및 Deployment 수정 권한 차이, Ingress 인증 응답, Tailscale HTTPS 순으로 진행한다.
