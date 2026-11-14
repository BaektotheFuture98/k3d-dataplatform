# 24장. 요청 하나와 작업 하나를 끝까지 설명하기

## 왜 필요한가

도구 이름을 따로 아는 것과 전체 동작을 설명하는 것은 다르다. 두 경로를 그려 보면
남은 빈칸을 찾을 수 있다. 파일을 적용하거나 서비스에 장애를 낼 필요는 없다.

## 어떻게 동작하는가

### 경로 A: 브라우저에서 Airflow 화면까지

로컬 Ingress 접속의 개념적 경로다. 실제 포트·Host는 자신의 설정과 대조한다.

```text
브라우저: airflow.localhost:8080
 → 호스트 이름 해석과 Mac↔VM 포트 전달
 → Docker가 노출한 k3d serverlb 포트
 → K3s 노드의 ingress 진입점
 → Traefik의 Host/path 규칙
 → airflow-api-server Service의 endpoint
 → Airflow API server Pod
 → 로그인 확인과 Airflow 응답
```

여기에는 서로 다른 판단이 있다. DNS는 이름을 주소로 바꾸고, 포트 전달은 연결을
안쪽으로 보내고, Traefik은 HTTP 목적지를 고르고, Airflow는 사용자 요청을 처리한다.
Kubernetes API server는 이 브라우저 요청을 대신 처리하는 웹 서버가 아니다.

### 경로 B: 두 태스크 DAG의 실행

```text
Mac의 DAG Python 파일
 → DAG 공유 PVC에 전달
 → DAG processor가 해석해 구조 반영
 → 수동 DAG Run 생성
 → Airflow scheduler가 make_articles 실행 결정
 → KubernetesExecutor가 worker Pod 요청
 → Kubernetes scheduler가 노드 배정
 → kubelet/containerd가 실행
 → worker가 Airflow Execution API로 통신
 → 성공 뒤 normalize_titles도 같은 원리로 실행
 → 실행 기록은 DB, 로그는 공유 PVC에 보관
```

미래의 업무 파이프라인에서는 이 뒤에 수집 Job, Iceberg 파일 저장, Spark 정제,
그래프 적재 등이 연결될 수 있다. **구성 파일이 있다는 사실과 전체 업무 경로가
현재 실행 중이라는 주장은 다르다.** 지금 검증한 범위를 따로 기록해야 한다.

## 우리 프로젝트에서는

[배포 선언](../../../deploy/k8s/), [Airflow 설정](../../../deploy/k8s/helm/airflow/values.yaml),
[Spark 설정](../../../configs/spark/spark-defaults.conf)을 옆에 두고 위 경로에
파일·리소스 이름을 붙인다. 실행 당시 값이 필요하면 해당 장의 조회 명령으로 확인한다.

## 직접 확인하기

다음은 조회다. 순서대로 어떤 경로의 어느 구간을 확인하는지 적는다.

```sh
kubectl --context k3d-dev get nodes
kubectl --context k3d-dev -n finance-platform get deploy,sts,pods
kubectl --context k3d-dev -n finance-platform get svc,ingress
kubectl --context k3d-dev -n finance-platform get pvc
```

예상되는 학습 결과는 특정 Pod 개수가 아니라 **서로 연결할 수 있는 리소스 지도**다.
노드→Pod, controller→Pod, Ingress→Service→endpoint, Pod→PVC의 관계를 표시한다.
모든 항목이 Running이어도 실제 업무 결과가 옳다는 보장은 아니라는 점을 설명한다.

## 이해 확인

| 상황 | 먼저 돌아갈 장 | 설명해야 할 것 |
| --- | --- | --- |
| docker에는 앱이 없는데 kubectl에는 있다 | 1–6 | 실행 환경과 runtime 경계 |
| apply 성공 뒤 Pod가 Pending | 7, 10, 15 | API 반영과 배치·실행의 차이 |
| 내부 접속은 되는데 브라우저는 실패 | 11–12 | 외부 진입과 HTTP 라우팅 |
| Pod 교체 뒤 파일이 없어졌다 | 8, 13, 17 | 파일 저장 위치와 보존 범위 |
| DAG가 있는데 worker가 없다 | 18, 20–21 | 정의·실행 상태·executor와 동시성 |
| DB는 복원했는데 Iceberg를 못 읽는다 | 22–23 | catalog 등록과 객체 파일의 일관성 |

**해설:** 원인을 맞히는 것보다 확인할 계층과 증거를 고르는 것이 중요하다.
모르는 이름을 재시작하기 전에 “누가 무엇을 관리하고 어디에 상태가 남는가”를
설명해 보자. 막히는 행의 장으로 돌아가 자기 말로 경로를 다시 그리면 된다.

---

[전체 목차](../README.md) · [이전: 23장. Jupyter·Spark·Neo4j의 실행 위치](23-data-processing.md)
