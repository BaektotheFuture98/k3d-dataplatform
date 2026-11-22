# Iceberg REST 카탈로그

- [Deployment](deployment.yaml)에서 PostgreSQL JDBC 카탈로그 설정, Garage 접근 Secret, AWS SDK checksum 설정을 확인한다. [Spark 설정 문서](../../../../configs/spark/README.md)에 버전 조합과 카탈로그 계약이 있다.
- 현재 이미지는 Apache Iceberg 테스트 fixture 기반의 내부용 카탈로그다. 인증과 TLS가 필요한 환경에 이 배포를 그대로 사용하지 않는다.
- 검증 시 [Iceberg smoke 스크립트](../../../../configs/runtime/iceberg-smoke.py)의 합성 테이블을 사용하고 REST 응답과 Spark의 읽기 결과를 구분한다.
