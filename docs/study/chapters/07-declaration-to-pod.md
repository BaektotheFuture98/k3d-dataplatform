# 7장. YAML 선언에서 Pod 실행까지

## 왜 필요한가

YAML을 저장했는데 앱이 바뀌지 않거나 apply가 성공했는데 Pod가 Pending일 수 있다.
**파일 수정, API 반영, 실제 실행**은 각각 다른 단계다.

## 어떻게 동작하는가

YAML은 데이터를 표현하는 형식이다. Kubernetes manifest는 그 형식으로 쓴 리소스 선언이다.
다음은 구조 설명용 발췌이며, 이 코드만 적용하는 실습은 아니다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jupyter
  namespace: finance-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: jupyter
  template:
    metadata:
      labels:
        app.kubernetes.io/name: jupyter
    spec:
      containers:
        - name: jupyter
          image: example.invalid/jupyter:study
```

`kind`는 리소스 종류, `metadata`는 이름과 namespace 같은 식별 정보다.
`spec`은 원하는 상태다. Deployment의 `template`은 만들 Pod의 설계도다.
`labels`는 객체에 붙이는 표식이고 `selector`는 관리할 대상을 찾는 조건이다.
위 이미지 주소는 실행 가능한 실제 이미지가 아닌 설명용 자리다.

API에서 리소스를 읽으면 `status`도 보인다. `spec`이 사용자가 요구한 상태라면,
`status`는 시스템이 관측해 보고한 상태다. replicas=1을 요구했어도 readyReplicas가
아직 0일 수 있다. 이 차이가 줄어드는 과정을 관찰하는 것이 실행 확인이다.

실제 적용 과정의 논리적 순서는 다음과 같다.

1. kubectl이 파일을 읽어 Kubernetes API에 생성·변경 요청을 보낸다.
2. API server가 요청을 검증하고 리소스 상태를 저장한다.
3. Deployment controller가 필요한 ReplicaSet을 만든다.
4. ReplicaSet controller가 원하는 수만큼 Pod를 만든다.
5. Kubernetes scheduler가 조건과 자원을 보고 노드를 선택한다.
6. 그 노드의 kubelet이 이미지·볼륨·컨테이너 실행을 관리하고 상태를 보고한다.

**ReplicaSet**은 특정 Pod 설계도로 원하는 개수를 유지하는 컨트롤러다.
Deployment는 새 설계도로 교체하는 과정까지 관리한다. `configured` 같은 apply
응답은 선언 반영 결과이며, 위의 모든 단계와 앱 준비가 끝났다는 뜻은 아니다.

## 우리 프로젝트에서는

[Jupyter manifest](../../../deploy/k8s/manifests/spark/jupyter.yaml)는 PVC,
Deployment, Service 세 리소스를 `---`로 구분한다. 실제 파일에는 자원·설정·인증
참조도 있다. `__SPARK_IMAGE__`는 렌더링 때 실제 이미지로 바꾸는 토큰이다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform get deployment jupyter
kubectl --context k3d-dev -n finance-platform get replicasets
kubectl --context k3d-dev -n finance-platform get pods \
  -l app.kubernetes.io/name=jupyter -o wide
```

`-l`은 label 조건이다. Deployment READY의 `1/1`은 준비된 수/목표 수를 뜻한다.
ReplicaSet 이름에는 보통 해시가 붙고, Pod 이름에는 추가 접미사가 붙는다.
예: `jupyter-<해시>-<접미사>`. 과거 ReplicaSet이 남아도 실행 Pod 수가 0일 수 있다.

## 이해 확인

1. 로컬 YAML의 replicas를 바꾸면 API가 자동으로 파일 변경을 읽는가?
2. API에 Pod가 있는데 노드가 배정되지 않았다면 어느 단계부터 볼까?

**해설:** 일반적인 파일 수정만으로는 반영되지 않는다. 배포 도구가 API에 전달해야 한다.
노드가 없는 Pod는 scheduler의 배치 조건과 이벤트부터 살펴본다.

더 읽기: [Kubernetes 객체](https://kubernetes.io/docs/concepts/overview/working-with-objects/),
[Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

---

[전체 목차](../README.md) · [이전: 6장. K3s 내부: 결정하는 쪽과 실행하는 쪽](06-k3s-internals.md) · [다음: 8장. Pod의 수명과 컨테이너 재시작](08-pod-lifecycle.md)
