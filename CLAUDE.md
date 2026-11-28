# k3d-dataplatform

- 이 저장소는 Colima 위의 k3d/K3s에서 기사 데이터 수집·정제·그래프 적재를 구성한다. 전체 구조와 운영 문서의 시작점은 [README.md](README.md)다.
- Kubernetes를 조회하거나 변경하기 전에 `kubectl config current-context`와 대상 네임스페이스를 확인한다. 로컬 컨텍스트는 `k3d-dev`다. 저장소와 카탈로그는 `lakehouse`, Airflow와 데이터 작업은 `pipelines`, Kafka와 Headlamp는 `dev`에 둔다. 기존 `finance-platform` 참조는 이전 설정일 수 있으므로 파일의 선언과 실제 배포 상태를 확인한다.
- 배포 정의는 [deploy/k8s](deploy/k8s), 운영 설정은 [configs](configs), 이미지 빌드는 [docker](docker), 애플리케이션 소스는 [workspace](workspace)에 있다. 같은 설정을 여러 경로에서 사용하면 변경 영향과 검증 대상을 함께 확인한다.
- Secret 값과 로컬 인증 파일은 Git, 공유 로그, 문서에서 제외한다. 예제에는 합성 값과 Secret 키 이름을 사용한다.
- 저장소 루트에서 `python3 -m unittest discover -s tests -v`, `ruby scripts/check-configs.rb`, `git diff --check`로 정적 검증을 시작한다. Ruby 검사는 일부 매니페스트에 기존 네임스페이스 정책을 적용하므로, 결과를 현행 배포 검증과 구분한다.
