# Traefik Ingress와 Tailscale

- [platform-ui.yaml](platform-ui.yaml) 및 [Tailscale Jupyter 라우트](tailscale-jupyter.yaml)는 [접속 운영 안내](../../../../configs/ingress/README.md)와 대조한다. Headlamp 경로는 [별도 Helm 설정](../../helm/headlamp/values.yaml)에 있다.
- DNS, Tailscale Serve, Mac 루프백, Traefik Host 매칭, upstream Service를 순서대로 확인한다. HTTPS 확인에는 해당 호스트 이름과 인증서 검증을 유지한다.
- 기본 애플리케이션 인증을 보존하고 기존 Tailscale 서비스나 다른 호스트의 매핑이 영향받는지 확인한다.
