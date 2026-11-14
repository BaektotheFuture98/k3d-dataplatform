# Spark: Jupyter 안에서 실행하는 데이터 처리 엔진

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [23장](../chapters/23-data-processing.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

## 학습 목표

현재 Spark 실행 방식과 KubernetesExecutor를 구분한다.

## 현재 실행 방식

Spark **4.1.2**, Iceberg **1.11.0**, Java 21 기반 이미지가 Jupyter Pod에 들어 있다.
Spark 설정의 `spark.master`는 **`local[2]`**다. 현재 별도 Spark master/worker
클러스터나 Spark executor Pod를 구성한 것이 아니다.
Airflow가 KubernetesExecutor를 사용한다고 Spark도 자동으로 Kubernetes 모드가
되는 것은 아니다.

| 설정 | 현재 값 |
| --- | --- |
| spark.master | local[2] |
| spark.driver.memory | 1g |
| spark.sql.shuffle.partitions | 4 |
| spark.sql.session.timeZone | UTC |
| spark.ui.enabled | false |
| default catalog | lakehouse |
| event log | file:///tmp/spark-events, 영속 보존 안 됨 |

`local[2]`는 로컬 실행 thread 수에 관한 설정이지 Kubernetes Pod 두 개를 뜻하지 않는다.
Jupyter Pod 자원 한도 안에서 Spark와 노트북 프로세스가 함께 실행된다.

## 설정 파일과 연결

원본은 `configs/spark/spark-defaults.conf`, 배포되는 설정은
`deploy/k8s/manifests/spark/configmap.yaml`이다. 두 파일의 값을 함께 관리한다.
Iceberg REST에 catalog 조회를 하고 Garage에 파일을 쓴다.

S3 접근에는 두 경로가 있다.

- Iceberg의 `S3FileIO`: Iceberg 테이블 파일 입출력.
- Hadoop `S3AFileSystem`: checkpoint 등 Hadoop 파일시스템 경로.

둘 다 endpoint·region·path-style·인증 provider가 맞아야 한다.
Jar 버전은 Spark/Hadoop/Scala와 호환되는 조합으로 고정했으며 임의 jar 추가는
클래스 충돌을 일으킬 수 있다. 인증키는 환경변수와 Secret으로 주입한다.

## 작은 읽기 실습

노트북의 기존 Spark 세션에서 실행한다.

```python
print(spark.sparkContext.master)
print(spark.version)
print(spark.conf.get("spark.sql.session.timeZone"))
spark.range(10).groupBy().sum("id").show()
```

마지막 결과는 45다. 저장소에 업무 데이터를 쓰지 않고 엔진의 기본 동작을 본다.
노트북에서 새 SparkSession을 만들 때 이미지·공통 설정 적용 여부도 확인한다.

## Streaming과 저장소의 수명

Spark event log는 현재 컨테이너 임시 경로에 있어 Pod 교체 뒤 유지되지 않는다.
Jupyter 노트북 PVC와 Garage의 streaming checkpoint는 서로 다른 저장 대상이다.
두 업무 streaming Deployment는 replicas=0이므로 현재 이들이 상시 처리 중인 것은 아니다.

## 확인 문제

1. Airflow worker가 Kubernetes Pod라면 그 안의 Spark도 분산 실행되는가?
2. event log, checkpoint, 결과 테이블은 같은 데이터인가?

**해설:** Spark master와 실행 구성을 따로 정해야 한다. event log는 실행 관측,
checkpoint는 streaming 진행 상태 복구, 테이블은 처리 결과를 관리한다.

참고: [Spark 설정](https://spark.apache.org/docs/4.1.2/configuration.html).
