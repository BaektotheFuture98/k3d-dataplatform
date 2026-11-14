# 23장. Jupyter·Spark·Neo4j의 실행 위치

## 왜 필요한가

Airflow가 KubernetesExecutor라고 Spark도 자동으로 여러 Pod에서 계산하는 것은 아니다.
작업 순서를 관리하는 시스템과 계산 엔진, 결과 저장소를 나누어 보자.

## 어떻게 동작하는가

**JupyterLab**은 노트북 편집과 실행을 위한 작업 공간이다. Python 코드는 커널
프로세스에서 실행된다. **Spark**는 데이터를 계산하는 엔진이다. **Neo4j**는
노드와 관계를 저장·질의하는 그래프 DB다. Airflow는 이 작업들의 실행을 조정할 수 있다.

Spark에서 **driver**는 애플리케이션 실행을 조정하고, 분산 모드의 **executor**는
계산을 수행한다. 이 executor와 Airflow executor는 이름이 같아도 다른 시스템의 개념이다.
`local[2]`는 한 환경에서 두 worker thread로 실행하는 로컬 모드다.
Kubernetes Pod 두 개나 별도의 분산 Spark 클러스터를 뜻하지 않는다.

```text
Jupyter Pod
├─ Jupyter 서버와 Python 커널
├─ Spark 로컬 실행: local[2]
└─ 외부 연결
   ├─ Iceberg REST: catalog 요청
   └─ Garage: 파일 입출력

Neo4j Pod: 별도의 그래프 DB
```

Neo4j 모델의 간단한 예는 다음과 같다. 현재 업무 데이터가 실제 적재돼 있다는
뜻이 아니라 그래프 표현을 보여 주는 예시다.

```text
(기사 A) -[언급한다]-> (사건 B)
```

## 우리 프로젝트에서는

[Spark 설정](../../../configs/spark/spark-defaults.conf)의 master는 `local[2]`다.
[Jupyter Pod](../../../deploy/k8s/manifests/spark/jupyter.yaml) 자원 안에서 노트북과
Spark를 실행한다. [Neo4j values](../../../deploy/k8s/helm/neo4j/values.yaml)는
별도 DB 인스턴스를 구성한다. Kafka에서 Neo4j로의 업무 적재가 계속 실행 중이라는 뜻은 아니다.

저장 수명도 구분한다. 노트북 파일은 `/workspace` PVC, Python 변수는 메모리,
Iceberg 파일은 Garage, 현재 Spark event log는 임시 경로다.
노트북 파일이 남아도 커널을 새로 시작하면 연결·변수를 다시 준비해야 한다.

## 직접 확인하기

기존 Spark 세션이 있는 Jupyter 노트북에서 다음을 실행한다.

```python
print(spark.sparkContext.master)
print(spark.version)
spark.range(10).groupBy().sum("id").show()
```

설정대로라면 master 출력은 local[2]이고, 마지막 계산 결과는 0부터 9의 합인 45다.
업무 테이블을 만들거나 변경하지 않는 작은 계산이다.
오류가 나면 Spark 세션 준비 여부와 Pod 로그를 확인한다. 곧바로 Kubernetes
클러스터 전체를 재생성할 이유는 없다.

## 이해 확인

1. Airflow worker Pod 수를 늘리면 기존 local[2] Spark가 자동 분산 실행되는가?
2. 노트북 파일, Spark 메모리, Iceberg 테이블은 같은 수명을 갖는가?

**해설:** Spark 실행 모드와 자원 배치를 별도로 구성해야 한다. 파일·메모리·외부
데이터는 각각 다른 위치에 있으므로 보존·재현 방법도 다르다.

근거: [Spark 실행 구성](https://spark.apache.org/docs/4.1.2/configuration.html),
[Spark 클러스터 개요](https://spark.apache.org/docs/4.1.2/cluster-overview.html).

---

[전체 목차](../README.md) · [이전: 22장. PostgreSQL·Garage·Iceberg의 저장 책임](22-data-storage.md) · [다음: 24장. 요청 하나와 작업 하나를 끝까지 설명하기](24-end-to-end.md)
