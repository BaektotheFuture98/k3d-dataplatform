# Jenkins 배포

- Jenkins 컨트롤러와 빌드 에이전트는 `jenkins`에 둔다. 컨트롤러는 `local-path` PVC를 사용하고 빌드는 Kubernetes 에이전트에서 실행한다.
- [Jenkinsfile](../../../../Jenkinsfile)과 [CI/CD 운영 안내](../../../gitops/README.md)를 참고한다. 설치 검증과 실제 Pipeline 결과를 따로 확인한다.
