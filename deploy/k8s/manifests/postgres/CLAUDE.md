# PostgreSQL 배포

- [StatefulSet](statefulset.yaml), [초기화 ConfigMap](initdb-configmap.yaml), [검증 Job](verify-job.yaml)을 [PostgreSQL 운영 기록](../../../../configs/postgres/VALIDATION.md)과 함께 확인한다.
- Airflow의 `airflow_meta`와 Iceberg의 `iceberg_catalog`가 사용하는 DB·계정·Secret 참조를 구분한다.
- 초기화 스크립트 변경은 이미 초기화된 PVC에 자동 반영되지 않는다. 기존 DB 변경과 신규 설치 경로를 따로 검증한다.
