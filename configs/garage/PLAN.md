# Phase 2 — Garage로 MinIO 대체

사용자가 Garage 대체를 명시적으로 허용했다. 원래 MinIO scaffold는 보존한다.
공식 v2.4.1 ARM64 manifest를 확인하고 digest로 고정한다.

## 의존성과 설계

- 기존 finance-platform, local-path 유지. 단일 StatefulSet, 10Gi PVC Retain.
- S3만 ClusterIP 3900으로 제공. 관리 3903은 Service로 노출하지 않는다.
- replication_factor=1, consistent, LMDB metadata와 object data를 모두 PVC에 저장.
- 공식 single-node/default-bucket 기능으로 최초 layout/key/warehouse를 생성한다.
- RPC/admin token/S3 key는 Secret으로만 주입. 재실행 시 기존 Secret 보존.
- 개발용 default key는 warehouse read/write/owner와 bucket 생성 권한을 가진다.
  후속 앱별 세부 권한 분리는 별도 키로 확장할 수 있다.
- S3는 SigV4/path-style/region garage, 이후 Iceberg에는 endpoint/region/path-style
  및 이 Secret의 S3 키 두 개만 주입한다. RPC/admin 키를 앱에 제공하지 않는다.
- configs/garage가 원본, Ruby renderer로 생성한 두 ConfigMap도 Git에서 관리한다.
- 검증 Job 이미지에는 고정 Python base와 boto3/botocore를 설치한다.

## 실행 순서

1. [x] 공식 문서/이미지/설정/API 확인.
2. [x] 원본 설정·Secret helper·검증 코드·Manifest 작성과 문법 검증.
3. [x] 검증 이미지 build/import, ConfigMap/Secret 반영 후 Service 없는 상태 실패 확인.
4. [x] server dry-run, Service/StatefulSet 적용, Ready/PVC Bound 확인.
5. [x] 반복 Job으로 bucket 초기화 및 PUT/GET/HEAD/LIST/DELETE, multipart checksum,
   익명 GET 403 검증.
6. [x] rollout restart 후 동일 PVC/PV, 이전 객체 내용, 새 Job 재실행 성공 확인.
7. [x] README/검증 기록 갱신. Iceberg Catalog/Spark 실연결은 Phase 3/4에서 별도 검증.

S3 기본 API 호환성은 Iceberg/Spark 전체 호환성 증명이 아니다.
Garage는 IAM bucket policy/ACL/versioning 등을 모두 구현하지 않으며 해당 기능에 의존하지 않는다.
