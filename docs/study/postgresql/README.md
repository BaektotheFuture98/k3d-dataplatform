# PostgreSQL: Airflow와 Iceberg의 메타데이터 DB

## 학습 목표

업무 파일과 메타데이터를 구분하고 초기화·Secret·PVC의 관계를 이해한다.

## 현재 역할과 설정

PostgreSQL 17 계열 이미지를 digest로 고정한 StatefulSet `postgres`, Pod `postgres-0`
하나를 실행한다. 과거 검증 기록의 SQL 버전은 17.11이며 이번에는 실행 이미지와
Pod 상태를 재확인했다. SQL `SELECT version()`을 새로 실행한 결과와 혼동하지 않는다.

| 항목 | 설정 |
| --- | --- |
| 내부 Service | postgres:5432 |
| Airflow DB / 사용자 | airflow_meta / airflow_user |
| Iceberg catalog DB / 사용자 | iceberg_catalog / iceberg_user |
| PVC | data-postgres-0, 10Gi local-path RWO |
| max_connections | 60 |
| shared_buffers | 128MB |
| 인증 방식 | host SCRAM-SHA-256 |
| 자원 request / limit | 100m·256Mi / CPU 1·512Mi |

실제 비밀번호는 `postgres-credentials` Secret으로 전달한다.
Airflow 연결 URI는 `airflow-metadata/connection`으로 따로 관리한다.
DB 비밀번호에 특수문자가 있으면 URI의 password 부분은 URL encoding이 필요하다.

## 초기화가 언제 실행되는가?

`deploy/k8s/manifests/postgres/initdb-configmap.yaml`의 스크립트는 새 데이터
디렉터리 초기화 때 사용한다. readiness는 초기화 완료 marker도 확인한다.
기존 PVC에 DB가 만들어진 뒤 ConfigMap이나 Secret만 고친다고 초기 SQL이
처음부터 다시 실행되는 것은 아니다. Secret 변경과 실제 SQL 계정의 암호 변경도 별개다.

StatefulSet에는 삭제·축소 시 PVC Retain 설정이 있다. 이것은 PVC를 직접 지우거나
노드 디스크를 없애도 복구된다는 뜻이 아니다. 백업은 별도로 필요하다.

## 읽기 실습

```sh
kubectl --context k3d-dev -n finance-platform get statefulset postgres
kubectl --context k3d-dev -n finance-platform get pvc data-postgres-0
kubectl --context k3d-dev -n finance-platform exec postgres-0 -- \
  psql -U postgres -d postgres -c 'SELECT version();'
```

마지막 예시는 컨테이너 안의 설정된 로컬 관리자 인증 경로를 사용한다.
앱의 TCP/SCRAM 인증 성공과 동일한 검사는 아니다. 실제 앱 계정의 접속과
다른 DB 접근 거부는 별도의 테스트로 확인해야 한다.

## 확인 문제

1. PostgreSQL이 Ready면 Airflow migration도 끝난 것인가?
2. Secret만 바꿨는데 앱 로그인이 실패하는 이유는?

**해설:** DB 가동과 Airflow schema 준비는 다르다. 실제 SQL 계정의 암호와
Secret의 값이 달라졌거나 이미 실행 중인 앱이 예전 값을 사용할 수 있다.

참고: [PostgreSQL 17 문서](https://www.postgresql.org/docs/17/),
설정 원본 `deploy/k8s/manifests/postgres/`.
