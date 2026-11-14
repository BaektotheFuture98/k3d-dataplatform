# 10장. 이미지와 CPU·메모리가 실행에 관여하는 방법

## 왜 필요한가

같은 YAML이라도 이미지를 가져올 수 없거나 노드 자원이 부족하면 실행되지 않는다.
컨테이너 코드가 실행되기 전의 문제와 실행 후 자원 문제를 나누어 보자.

## 어떻게 동작하는가

이미지의 `repository:tag`는 배포할 파일 묶음을 가리킨다. tag는 다시 붙일 수 있으므로
내용이 바뀔 수 있다. digest는 특정 내용을 식별한다. 노드는 이미지를 로컬에서 찾거나
registry에서 가져온다. `IfNotPresent`는 노드에 이미 있으면 보통 다시 받지 않는다.

```text
Dockerfile → Docker 이미지 빌드 → 노드가 이미지에 접근 → Pod 이미지 참조로 실행
```

k3d에서는 바깥 Docker의 이미지와 노드 안 containerd 이미지가 별도다.
로컬 이미지는 `k3d image import`로 노드에 반입하거나 접근 가능한 registry를 사용한다.
빌드·반입만 해서는 Deployment의 이미지 참조가 자동 변경되지 않는다.

**requests**는 scheduler가 배치 가능 여부를 계산할 때 쓰는 요청량이다.
**limits**는 컨테이너 실행 자원 한도다. CPU `100m`은 CPU 0.1개다.
CPU limit은 실행 시간을 제한하는 방식으로 작동하고, 메모리 한도를 넘으면
OOM으로 종료될 수 있다. 노드 자체 메모리 압박으로 인한 퇴거와는 다른 상황이다.

예를 들어 allocatable CPU가 2인 노드에 이미 요청 합계 1.95가 잡혀 있으면
request 0.1인 새 Pod는 배치되지 않을 수 있다. 실제 순간 사용률이 낮아도 마찬가지다.
반대로 CPU limit 합계를 노드보다 크게 설정했다고 모두 동시에 그 성능을 보장받지는 않는다.

## 우리 프로젝트에서는

[Airflow values](../../../deploy/k8s/helm/airflow/values.yaml)의 worker 요청은
CPU 100m·메모리 256Mi, 한도는 CPU 1·메모리 1Gi다. `parallelism: 2`는 Airflow
동시성 정책이며 실제 노드 자원과는 별도다. 원본 이미지 토큰은 배포 전에 렌더링해야 한다.

## 직접 확인하기

```sh
kubectl --context k3d-dev describe node k3d-dev-server-0
kubectl --context k3d-dev -n finance-platform get deployment jupyter \
  -o jsonpath='{.spec.template.spec.containers[0].resources}{"\n"}'
```

첫 결과의 Capacity/Allocatable과 Allocated resources를 비교한다.
Allocated resources는 요청·한도 합계이며 순간 사용량과 다르다.
둘째 결과는 Jupyter의 requests와 limits다. 한도만 보고 VM 전체 용량이라고 읽지 않는다.
노드 이름이 다르면 4장의 조회 결과에 나온 이름을 사용한다.

## 이해 확인

1. Docker 이미지가 있는데도 Pod가 ImagePullBackOff인 이유는?
2. 노드 사용률이 낮은데 CPU 부족으로 Pending일 수 있는가?

**해설:** 노드의 이미지 저장소·참조·registry 접근을 따로 확인해야 한다.
배치는 사용률만이 아니라 requests와 다른 조건을 사용하므로 가능하다.

근거: [자원 관리](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/),
[이미지](https://kubernetes.io/docs/concepts/containers/images/).

---

[전체 목차](../README.md) · [이전: 9장. Deployment·StatefulSet·Job을 나누는 이유](09-workload-controllers.md) · [다음: 11장. Mac·VM·노드·Pod의 네트워크 경계](11-network-boundaries.md)
