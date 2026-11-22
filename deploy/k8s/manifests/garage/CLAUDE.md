# Garage 객체 저장소

- [Garage 설정](../../../../configs/garage/garage.toml), ConfigMap, StatefulSet, 버킷 초기화 Job을 함께 검토한다.
- S3 endpoint, `warehouse` 버킷, region, path-style 설정을 변경할 때 Spark와 Iceberg REST 소비자 설정도 대조한다.
- 인증·합성 객체 읽기와 쓰기 검증은 [Garage 검증 기록](../../../../configs/garage/VALIDATION.md)을 참고한다. StatefulSet이나 PVC 변경 전 보존 범위를 확인한다.
