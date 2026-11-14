# 9장. Deployment·StatefulSet·Job을 나누는 이유

## 왜 필요한가

웹 앱은 계속 떠 있어야 하지만 수집 작업은 끝나야 한다. DB는 파일 연결과 식별자도
유지해야 한다. 모두 컨테이너라고 같은 관리 방식을 쓰는 것은 아니다.

## 어떻게 동작하는가

| 종류 | 목표 | 현재 예 |
| --- | --- | --- |
| Deployment | 교체 가능한 앱 Pod 개수 유지와 교체 | Jupyter, Airflow scheduler |
| StatefulSet | 안정된 식별자·저장소 연결을 가진 앱 관리 | PostgreSQL, Garage, Neo4j |
| Job | 유한한 작업이 완료되도록 관리 | 검증 Job, 향후 수집 Job |
| CronJob | 일정에 따라 Job 생성 | 향후 publisher |
| 직접 만든 Pod | 별도 상위 컨트롤러가 없다면 자체 복제 목표 없음 | Airflow executor worker |

Deployment가 replicas=1이면 Pod 소실 뒤 ReplicaSet이 새 Pod를 만든다.
StatefulSet은 `postgres-0` 같은 식별자를 사용하고 volumeClaimTemplates로 저장소를
연결할 수 있다. **StatefulSet 자체가 DB 복제나 백업을 구현하는 것은 아니다.**

Job은 실패 시 정책에 따라 새 Pod 등을 통해 재시도할 수 있다. 재시도는 외부에
이미 한 작업까지 자동 취소하지 않으므로 중복 실행을 고려해야 한다.

Airflow KubernetesExecutor는 기본적으로 worker **Pod를 직접 생성**한다.
모든 worker가 Kubernetes Job에 속한다고 생각하면 안 된다. 재실행 판단은
Airflow의 태스크 상태와 retry 정책에도 달려 있다.

## 우리 프로젝트에서는

[PostgreSQL](../../../deploy/k8s/manifests/postgres/statefulset.yaml)은 StatefulSet,
[Jupyter](../../../deploy/k8s/manifests/spark/jupyter.yaml)는 Deployment다.
[파이프라인 선언](../../../deploy/k8s/manifests/pipelines/)에는 replicas=0인
Deployment와 일시중지된 CronJob이 있다. 객체가 존재한다고 업무가 실행 중인 것은 아니다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform get deploy,sts,job,cronjob
kubectl --context k3d-dev -n finance-platform get pods \
  -o 'custom-columns=NAME:.metadata.name,OWNER_KIND:.metadata.ownerReferences[0].kind,OWNER:.metadata.ownerReferences[0].name'
kubectl --context k3d-dev -n finance-platform get replicasets
```

`deploy`와 `sts`는 Deployment와 StatefulSet의 약칭이다. 두 번째 명령은 Pod의
소유 객체를 보여 준다. Deployment의 Pod는 보통 ReplicaSet을 직접 소유자로 가진다.
따라서 `Deployment → ReplicaSet → Pod`를 세 번째 출력과 연결한다.
직접 생성한 worker는 owner가 비어 있을 수 있다.

## 이해 확인

1. replicas=0인 Deployment는 설정이 없는 것과 같은가?
2. StatefulSet replicas를 3으로 바꾸면 PostgreSQL 복제가 자동 완성되는가?

**해설:** 선언은 존재하지만 유지할 Pod 수가 0이다. DB 복제·리더·데이터 동기화는
DB와 운영 도구의 별도 구성이다. Pod 수만 늘려 해결하지 않는다.

더 읽기: [워크로드 관리](https://kubernetes.io/docs/concepts/workloads/controllers/).

---

[전체 목차](../README.md) · [이전: 8장. Pod의 수명과 컨테이너 재시작](08-pod-lifecycle.md) · [다음: 10장. 이미지와 CPU·메모리가 실행에 관여하는 방법](10-images-and-resources.md)
