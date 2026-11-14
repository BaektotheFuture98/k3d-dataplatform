# 14장. 설정·인증정보·실행 신원·권한

## 왜 필요한가

DB 비밀번호, 앱 설정 파일, Pod의 Kubernetes 권한은 다른 문제다.
“Secret이 있으니 권한도 있다”거나 “토큰 마운트를 껐으니 모든 비밀값이 없다”고
생각하면 실제 실행 조건을 잘못 이해하게 된다.

## 어떻게 동작하는가

| 개념 | 목적 | 예 |
| --- | --- | --- |
| ConfigMap | 일반 설정값·파일 | airflow.cfg, Spark 설정 |
| Secret | 인증값 등 비밀 데이터 전달 | DB 접속 정보, API 키 |
| ServiceAccount(SA) | Pod 등이 Kubernetes에 요청할 때 사용하는 신원 | airflow-scheduler |
| Role | namespace 안의 작업 권한 규칙 | pods 생성·조회 |
| RoleBinding | 신원에 Role 연결 | scheduler SA에 Pod 생성 권한 부여 |

ClusterRole은 클러스터 범위 리소스 권한 등을 정의할 수 있고, ClusterRoleBinding은
클러스터 범위로 연결한다. RoleBinding으로 ClusterRole을 namespace에 한정해
연결할 수도 있다. 핵심은 **규칙**과 **누구에게 연결했는지**를 함께 보는 것이다.

Pod가 Kubernetes API에 요청하려면 접근 경로와 인증 수단, 권한이 필요하다.
SA 토큰 자동 마운트를 끄면 그 기본 인증 수단을 제공하지 않는다.
그러나 `secretKeyRef`로 앱의 DB 암호를 주입하는 것까지 막는 설정은 아니다.

Secret의 base64는 암호화가 아니다. Secret은 아무나 읽어도 되는 객체가 아니며,
환경변수·파일로 전달한 값을 실행 중인 앱 코드가 읽을 수 있다는 점도 이해해야 한다.

설정 변경은 전달 방법에 따라 반영 방식이 다르다. 환경변수는 이미 실행 중인
프로세스에 자동 재주입되지 않는다. ConfigMap을 `subPath` 파일로 마운트한 경우도
기존 컨테이너의 파일이 자동 갱신되지 않는다. 앱이 설정을 다시 읽는지도 별도다.

## 우리 프로젝트에서는

executor 리소스(로컬 파일 `deploy/k8s/helm/airflow/executor-resources.yaml`)는
scheduler의 Pod 생성 권한과 API server의 로그 조회 권한을 나눈다.
기본 worker에는 별도 RoleBinding과 SA 토큰 자동 마운트가 없다.
[worker 템플릿](../../../deploy/k8s/helm/airflow/values.yaml)은 DB·Fernet·JWT 등
Secret 참조를 포함한다. Kubernetes API 권한과 Airflow 자격증명을 분리해 읽는다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform get serviceaccounts,roles,rolebindings
kubectl --context k3d-dev -n finance-platform auth can-i create pods \
  --as=system:serviceaccount:finance-platform:airflow-scheduler
kubectl --context k3d-dev -n finance-platform auth can-i create pods \
  --as=system:serviceaccount:finance-platform:airflow-executor-worker
```

`auth can-i`는 권한을 질의하며 Pod를 생성하지 않는다. `--as`는 해당 신원으로
검사한다. 선언대로 적용돼 있다면 뒤 두 응답은 yes/no가 예상된다.
검사자에게 신원 대행 권한이 없으면 검사 자체가 거부될 수 있다. 그것을 worker의
권한 결과와 혼동하지 않는다. Secret 값 조회는 이 실습에 필요하지 않다.

## 이해 확인

1. worker의 SA 토큰 자동 마운트가 꺼져 있으면 DB 암호도 없는가?
2. ConfigMap 파일을 수정하면 실행 중인 Airflow 설정이 바로 바뀌는가?

**해설:** 앱 인증값 주입과 Kubernetes 신원은 별개다. 변경 파일의 API 반영,
마운트 방식, 새 Pod 생성 여부, 앱의 설정 로딩을 확인해야 한다.

근거: [ServiceAccount](https://kubernetes.io/docs/concepts/security/service-accounts/),
[RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/),
[ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

---

[전체 목차](../README.md) · [이전: 13장. 볼륨·PV·PVC와 실제 데이터 위치](13-storage.md) · [다음: 15장. 출력·이벤트·로그로 장애 단계 좁히기](15-observing-and-debugging.md)
