# 17장. 단일 노드의 장애와 데이터 복구

## 왜 필요한가

“Kubernetes가 자동 복구한다”는 말에는 조건이 있다. 프로세스 재시작, Pod 재생성,
노드 장애 대응, 사라진 데이터 복원은 서로 다른 수준의 복구다.

## 어떻게 동작하는가

| 장애 | 자동으로 기대할 수 있는 범위 | 별도로 필요한 것 |
| --- | --- | --- |
| 컨테이너 프로세스 종료 | restartPolicy와 상태에 따른 재시작 | 앱 자체 원인 해결 |
| Deployment Pod 소실 | 목표 개수에 맞춘 새 Pod 생성 | 이미지·자원·설정 정상 |
| 노드 장애 | 다른 노드와 저장소 조건이 맞으면 새 Pod 실행 가능 | 여유 노드, 접근 가능한 데이터 |
| VM·디스크 소실 | 선언만으로 업무 데이터 재생 불가 | 백업과 복원 절차 |
| 잘못된 데이터 쓰기 | 재시작해도 잘못된 데이터가 남음 | 이전 데이터 복구·재처리 |

단일 노드가 실행 불가능하면 새 Pod를 만들더라도 배치할 정상 노드가 없다.
다중 노드가 있어도 local-path 데이터가 다른 노드에 저절로 복제되는 것은 아니다.
단일 Colima VM에 노드만 여러 개 만들면 VM 자체의 장애 경계도 여전히 공유한다.

**고가용성**은 장애 중에도 서비스를 유지하는 성질이고, **백업**은 과거 상태를
복원할 자료다. **복원 검증**은 그 자료로 실제 되살릴 수 있는지 확인하는 것이다.
PVC Retain이나 Pod 자동 재생성은 이 셋을 대신하지 않는다.

## 우리 프로젝트에서는

[PostgreSQL 선언](../../../deploy/k8s/manifests/postgres/statefulset.yaml)은
StatefulSet 삭제·축소 시 PVC Retain을 설정한다. PVC 자체의 삭제, PV reclaim
policy, VM 디스크 소실까지 막는 보장은 아니다.
기존 기록의 전체 플랫폼은 단일 노드이고 백업·복원은 미검증이다.

K3s 제어 상태 복원과 PostgreSQL·Garage 데이터 복원도 구분한다.
K3s datastore가 무엇인지에 따라 제어 상태 백업 방식이 달라지고, 그것만으로 앱
볼륨 데이터까지 포함되는 것은 아니다.

## 직접 확인하기

```sh
kubectl --context k3d-dev get nodes
kubectl --context k3d-dev -n finance-platform get pvc
kubectl --context k3d-dev get pv \
  -o 'custom-columns=NAME:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,CLASS:.spec.storageClassName'
```

첫 목록으로 정상 배치 대상 수를, 뒤 목록으로 데이터 연결과 삭제 정책을 읽는다.
예를 들어 노드가 하나이고 저장소가 local-path라면 노드 장애 시 다른 노드로의
자동 데이터 이동을 기대하지 않는다. 이 실습에서는 장애를 일부러 만들지 않는다.

복구 계획은 다음 질문으로 작성해 본다.

1. 어떤 상태를 살릴 것인가: 리소스 선언, DB, 객체 파일, 실행 기록?
2. 어떤 장애를 견딜 것인가: Pod, 노드, VM, 사용자 실수?
3. 복원 자료는 같은 장애로 함께 사라지지 않는가?
4. 복원 뒤 앱 연결과 데이터 일관성을 무엇으로 검증할 것인가?

## 이해 확인

1. 노드 컨테이너를 삭제해 재생성하면 local-path 데이터도 반드시 복구되는가?
2. DB Pod가 Ready이면 복원된 데이터가 올바르다고 말할 수 있는가?

**해설:** 실제 저장 경로·외부 마운트·보존 정책에 달려 있으므로 보장할 수 없다.
Ready는 앱 준비 검사이며, 데이터 내용·일관성과 기능 검증은 별도다.

근거: [K3s 백업과 복원](https://docs.k3s.io/datastore/backup-restore).

---

[전체 목차](../README.md) · [이전: 16장. Helm과 파일·실행 설정의 차이](16-helm-and-changes.md) · [다음: 18장. Airflow의 DAG·Task·실행 기록](18-airflow-concepts.md)
