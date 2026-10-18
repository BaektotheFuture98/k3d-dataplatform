# PostgreSQL Phase 1 실행 계획

사용자 명세를 설계 기준으로 삼고 현재 프로젝트에서 직접 구현한다.
후속 서비스는 PostgreSQL 검증을 통과하기 전 배포하지 않는다.

## 설계와 변경 파일

- `deploy/k8s/manifests/postgres/initdb-configmap.yaml`: 최초 초기화 스크립트.
  오류 즉시 종료, 비밀번호 SQL 로그 억제, DB와 역할 분리, 완료 마커 기록.
- `service.yaml`: `postgres` ClusterIP, `postgres-headless` governing Service.
- `statefulset.yaml`: PostgreSQL 17, 1 replica, local-path 10Gi, PVC Retain,
  Secret 파일 마운트, 100m/256Mi requests, 1 CPU/512Mi limits, probes.
- `verify-job.yaml`: 별도 Pod에서 Service DNS/TCP/SCRAM 인증, DDL/DML,
  다른 DB 접근 거부, 잘못된 비밀번호 거부, 보존 토큰 확인.
- `configs/postgres/create-secret.py`: 난수 비밀번호를 메모리에서 생성하고
  stdin으로 Secret 생성. 기존 Secret은 변경하지 않는다.
- `README.md`: 아키텍처, 단계별 상태, 실제 배포/검증 명령, 복구/보존 절차.
- `.gitignore`: 실제 Secret, 로컬 인증 파일, 백업 제외.

## 의존성과 검증 순서

1. [x] Git/기존 파일, Namespace, 노드, StorageClass, Docker/Colima 조사.
   깨끗한 scaffold, 빈 Namespace, ARM64, 2 CPU/8112900Ki, local-path 확인.
2. [x] 검증 Job을 먼저 작성하고 서비스 미배포 상태에서 실패 확인.
3. [x] Secret, 초기화 ConfigMap, 두 Service, StatefulSet 작성.
4. [x] YAML 파싱, shell 문법, 서버 dry-run 후 Secret → ConfigMap → Service
   → StatefulSet 순서로 적용. Namespace/StorageClass/PVC 삭제 금지.
5. [x] Ready/Bound/Endpoint/log 확인, 새로운 Job으로 인증/권한/읽기쓰기 확인.
6. [x] rollout restart 후 PVC UID와 PV가 같고 보존 토큰이 남는지 확인.
7. [x] README에 명령 및 관측 결과 기록, 후속 단계의 의존성과 자원 검토.

## 실패 및 기존 데이터 처리

초기화는 빈 PGDATA에서만 자동 실행한다. 실패 후 PG_VERSION이 생기면
컨테이너 재시작으로 스크립트가 재실행되지 않는다. 완료 마커 없는 DB는
Ready로 표시하지 않는다. 원인 수정 후 관리자가 기존 데이터와 역할을
확인하고 명시적으로 스크립트를 재실행한다. 복구 스크립트는 기존 역할의
비밀번호와 기존 DB 소유자를 변경하지 않고 누락 객체만 생성한다.
Secret 변경은 SQL 비밀번호 변경과 별개다. 기존 PVC 삭제나 초기화는 하지 않는다.

## 검토할 조건

- 초기화 중단/부분 성공 시 거짓 Ready 방지.
- Secret 재생성으로 기존 데이터의 인증 정보 불일치 방지.
- PUBLIC 기본 CONNECT 제거 및 앱 역할의 관리자 권한 부재.
- 재생성 전후 실제 토큰과 동일 PVC/PV 확인.
- 테스트는 인프라 검증이며 업무 데이터 파이프라인 성공을 뜻하지 않는다.
