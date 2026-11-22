# Kubernetes 배포 정의

- [helm](helm)에는 외부 차트 values와 보조 리소스가 있고, [manifests](manifests)에는 직접 적용할 리소스가 있다.
- 설치나 업그레이드 전에 릴리스·차트 버전, 렌더링 결과, 네임스페이스, Service와 Secret 참조를 대조한다. 이미지 자리표시자가 있는 파일은 [렌더러](../../scripts/render-manifests.py)를 통해 처리한다.
- 관련 파일만 지정해 서버 dry-run을 사용한다. 배포 경로 전체에는 비활성 워크로드와 명시적으로 생성하는 Job도 포함돼 있다.
