# Argo CD 배포

- Argo CD는 `argocd`에 설치한다. [values.yaml](values.yaml)은 릴리스 설정을, [GitOps 운영 안내](../../../gitops/README.md)는 프로젝트와 애플리케이션 적용 순서를 설명한다.
- AppProject의 저장소와 대상 네임스페이스를 최소 범위로 지정한다. 애플리케이션 동기화 전 소스 리비전과 대상 환경을 확인한다.
