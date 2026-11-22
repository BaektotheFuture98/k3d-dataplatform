# 플랫폼 운영 설정

- 서비스별 절차는 이 디렉터리의 README와 운영 기록에서 찾는다. 파일의 예제 명령은 현재 컨텍스트와 대상 네임스페이스에 맞춰 검토한다.
- 배포 이미지 예시는 [platform-images.env.example](platform-images.env.example), Secret 준비 로직은 [prepare-secrets.py](prepare-secrets.py)에 있다. 변경 전 `python3 scripts/render-manifests.py --help`와 `python3 configs/prepare-secrets.py --help`로 입력 형식을 확인한다.
- [runtime/VALIDATION.md](runtime/VALIDATION.md)는 과거 실행 기록이다. 현재 상태는 Kubernetes 조회나 새 검증 결과로 확인한다.
