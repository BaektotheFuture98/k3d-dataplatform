# 8장. Pod의 수명과 컨테이너 재시작

## 왜 필요한가

Pod 이름이 그대로인데 RESTARTS가 늘어나는 경우와 Pod 이름이 바뀐 경우는 다르다.
무엇이 새로 만들어졌는지 구분해야 로그와 파일의 수명도 이해할 수 있다.

## 어떻게 동작하는가

Pod는 고유한 UID를 가지며 특정 노드에 배정된다. 기존 Pod를 다른 노드로 옮겨
계속 실행하는 것이 아니라, 필요할 때 다른 UID의 새 Pod를 만든다.
같은 Pod 안의 컨테이너는 재시작 정책에 따라 다시 실행될 수 있다.

| 상태·표시 | 뜻 | 먼저 볼 것 |
| --- | --- | --- |
| Pending | 아직 준비가 끝나지 않음 | 노드 배정, 이미지, 볼륨 이벤트 |
| Running | Pod가 노드에 배정됐고 컨테이너 실행이 진행 중 | Ready와 앱 응답 |
| Succeeded | 모든 컨테이너가 성공 종료하고 재시작하지 않음 | 완료 작업 결과 |
| Failed | 모든 컨테이너가 종료했고 하나 이상 실패 | 종료 코드와 로그 |
| CrashLoopBackOff | 반복 종료 후 재시작 대기라는 표시 | 직전 컨테이너 로그 |

`CrashLoopBackOff`는 Pod phase 이름이 아니다. `kubectl get pods`의 STATUS에는
phase 외의 상세 사유도 표시된다. `Running`과 `READY 1/1`도 다른 정보다.

**readiness probe**는 요청을 받을 준비가 됐는지 검사한다. 실패하면 일반적인
Service 트래픽 대상에서 제외된다. **liveness probe**는 컨테이너를 다시 시작할지
판단한다. **startup probe**는 느린 초기화를 기다리며 성공 전까지 다른 probe를 유예한다.
readiness 실패만으로 컨테이너를 재시작시키지는 않는다.

컨테이너 재시작에서도 `emptyDir`는 같은 Pod가 유지되면 남을 수 있다.
Pod 자체가 교체되면 `emptyDir`도 사라진다. PVC는 별도 객체이므로 다른 수명을 갖는다.

## 우리 프로젝트에서는

[Jupyter](../../../deploy/k8s/manifests/spark/jupyter.yaml)는 TCP probe를 사용한다.
포트가 열렸다는 준비 검사와 Spark 쿼리·Garage 접근 성공은 별도다.
Airflow worker는 한 작업 후 종료하는 Pod이므로 성공 종료가 정상일 수 있다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform get pods \
  -o 'custom-columns=NAME:.metadata.name,UID:.metadata.uid,PHASE:.status.phase,NODE:.spec.nodeName'
kubectl --context k3d-dev -n finance-platform get pods
```

첫 명령은 지정한 열만 출력한다. UID와 이름을 기록해 두면 나중에 Pod 교체 여부를
비교할 수 있다. 둘째는 READY와 RESTARTS를 본다. 이 실습을 위해 Pod를 삭제하지 않는다.
예상하는 해석은 “RESTARTS 증가만으로 새 Pod라고 결론 내릴 수 없다”는 것이다.

## 이해 확인

1. readiness가 실패하면 반드시 RESTARTS가 증가하는가?
2. StatefulSet Pod 이름이 다시 `postgres-0`이면 동일한 Pod인가?

**해설:** readiness는 요청 처리 준비 상태다. 컨테이너 재시작 판단과 다르다.
StatefulSet은 이름을 재사용할 수 있으므로 같은 이름이라도 UID가 다르면 새 Pod다.

근거: [Pod 수명](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/),
[Probe](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/).

---

[전체 목차](../README.md) · [이전: 7장. YAML 선언에서 Pod 실행까지](07-declaration-to-pod.md) · [다음: 9장. Deployment·StatefulSet·Job을 나누는 이유](09-workload-controllers.md)
