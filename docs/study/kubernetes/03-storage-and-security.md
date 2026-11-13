# Kubernetes 3: 데이터 저장과 실행 권한

## 학습 목표

emptyDir, PVC, ConfigMap, Secret, ServiceAccount와 RBAC를 구분한다.

## 데이터와 설정의 수명

| 종류 | 현재 사용 예 | Pod가 교체되면? |
| --- | --- | --- |
| 컨테이너 쓰기 계층 | 임시 파일 | 보존을 기대하지 않는다 |
| emptyDir | 임시 작업·캐시 | Pod와 함께 사라진다 |
| PVC | DB·DAG·작업 로그·노트북 | PVC/PV가 유지되면 다시 연결 가능 |
| ConfigMap | Spark 설정, airflow.cfg | 객체는 유지되지만 mount 방식에 따라 갱신 동작이 다르다 |
| Secret | DB/S3 인증값, JWT key | 객체로 별도 관리하며 이미지에 넣지 않는다 |

현재 PVC는 PostgreSQL·Garage·Neo4j 각 10Gi, Jupyter 2Gi,
Airflow DAG 1Gi, Airflow 로그 2Gi다. 모두 local-path/RWO다.
**RWO는 Pod 한 개만 쓸 수 있다는 뜻이 아니라 한 노드에서 읽기·쓰기로
마운트한다는 뜻**이다. 현재 단일 노드의 여러 Airflow Pod가 같은 PVC를 공유한다.
[PersistentVolume 공식 설명](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).

local-path는 네트워크 분산 저장소가 아니다. Pod 교체에 데이터가 남는 것과
VM·노드 디스크가 사라져도 복구되는 것은 다르다. 용량 요청 역시 디스크 quota를
보장하지 않는다. 백업·복원은 별도로 검증해야 한다.

## ConfigMap 갱신의 함정

현재 Airflow 설정은 ConfigMap을 `subPath`로 파일 마운트한다.
ConfigMap만 수정했다고 이미 실행 중인 프로세스의 설정이 즉시 바뀌지 않는다.
새 Pod가 새 파일을 읽도록 rollout이 필요하다. Secret을 환경변수로 주입한 경우도
이미 실행 중인 프로세스가 새 값을 자동으로 읽는다고 가정하면 안 된다.

## Kubernetes 실행 신원

ServiceAccount는 Pod가 Kubernetes API에 접근할 때 사용하는 신원이다.
Role은 namespace 안에서 허용할 동작을 정의하고 RoleBinding이 신원과 역할을 연결한다.
ClusterRole/ClusterRoleBinding은 범위와 연결 방식을 별도로 이해해야 한다.

| 신원 | 현재 권한 |
| --- | --- |
| `airflow-scheduler` | finance-platform의 worker Pod 관리, Secret 읽기는 거부 |
| `airflow-api-server` | 같은 namespace의 Pod·로그 읽기 |
| `airflow-executor-worker` | 별도 RBAC 없음, API 토큰 자동 mount 꺼짐 |
| `headlamp-user` | 전역 view 계열 읽기 + finance-platform edit |

Worker에 API 토큰을 주지 않는다고 모든 인증정보가 격리되는 것은 아니다.
현재 worker template에는 기존 Airflow DB/Fernet/API/JWT Secret 참조가 들어 있다.
서로 신뢰하지 않는 DAG를 실행하는 보안 경계로 해석하지 않는다.

## 조회 실습

```sh
kubectl --context k3d-dev -n finance-platform get pvc
kubectl --context k3d-dev -n finance-platform get serviceaccount,role,rolebinding
kubectl --context k3d-dev -n finance-platform auth can-i create pods \
  --as=system:serviceaccount:finance-platform:airflow-scheduler
kubectl --context k3d-dev -n finance-platform auth can-i get secrets \
  --as=system:serviceaccount:finance-platform:airflow-scheduler
```

기대하는 결과는 각각 yes/no다. 실행자의 impersonation 권한이 없거나 실행 환경이
네트워크 요청을 막으면 검사가 실패할 수 있으므로 앱 신원의 RBAC 거부와 구분한다.
Secret의 base64 표현은 암호화나 공개 가능한 익명화가 아니다.

## 확인 문제

1. Secret의 비밀번호 값을 바꾸면 PostgreSQL 내부 계정 암호도 바뀌는가?
2. PVC 요청을 2Gi로 만들면 노드 디스크를 2Gi 이상 못 쓰는가?

**해설:** DB 내부 암호는 별도로 변경해야 한다. local-path의 요청 용량은 실제
사용량 제한을 보장하지 않으므로 디스크 사용량과 로그 보존 정책을 관리해야 한다.
