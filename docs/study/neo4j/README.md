# Neo4j: 기사와 이벤트를 그래프로 표현하기

## 학습 목표

관계형 테이블과 노드·관계 모델의 차이를 이해하고 현재 가동과 업무 연결을 구분한다.

## 현재 구성

Neo4j Community **5.26.32**, chart **5.26.32**, Pod `neo4j-0` 하나를 실행한다.
기사 파이프라인에서 실제 업무 그래프를 계속 적재하는 단계는 아직 연결하지 않았다.

| 항목 | 설정 |
| --- | --- |
| Bolt | neo4j:7687 |
| HTTP | neo4j:7474 |
| 데이터 PVC | data-neo4j-0, 10Gi local-path RWO |
| CPU / 메모리 | 500m / 2Gi |
| heap initial / max | 512m / 512m |
| page cache | 512m |
| 인증 Secret | neo4j-auth |
| 외부 LoadBalancer | 비활성화 |

heap과 page cache만 합쳐 Pod memory limit을 계산하면 안 된다.
프로세스와 native 메모리 등 추가 사용량도 있으므로 전체 메모리 여유가 필요하다.

## 설정 위치와 인증 계약

`deploy/k8s/helm/neo4j/values.yaml`에서 Community edition, Secret, 자원, 볼륨을
지정한다. 현재 chart의 `passwordFromSecret`는 `NEO4J_AUTH` 키를 사용한다.
연동용 raw password 키와 같은 실제 암호를 가리켜야 하지만 값을 문서에 쓰지 않는다.
기존 DB의 암호를 바꾸는 것은 초기 Secret 생성과 별도의 절차다.

## 그래프 개념

기사와 사건을 각각 노드로 두고 관계를 연결할 수 있다.

```text
(:Article {article_id: ...}) -[:MENTIONS]-> (:Event {event_id: ...})
```

위 관계 이름은 모델 학습용 예시이며 현재 적용된 실제 ingestion schema를
단정하는 코드가 아니다. 실제 제약 조건 원본은 `configs/neo4j/constraints.cypher`다.
파일이 존재한다는 사실과 모든 제약 조건을 실제 DB에 적용했다는 사실을 구분한다.

## 읽기 실습

```sh
kubectl --context k3d-dev -n finance-platform get statefulset neo4j
kubectl --context k3d-dev -n finance-platform get service neo4j
kubectl --context k3d-dev -n finance-platform get pvc data-neo4j-0
kubectl --context k3d-dev -n finance-platform port-forward service/neo4j 17474:7474 17687:7687
```

브라우저에서 `http://127.0.0.1:17474`로 접근해 안전한 경로의 기존 계정으로
로그인한 뒤 다음 읽기 쿼리를 사용한다. Bolt 주소는 환경에 맞춰 지정한다.

```cypher
RETURN 1 AS connection_ok;
SHOW CONSTRAINTS;
```

노드 생성·삭제 대신 연결과 실제 제약 조건을 먼저 확인한다.

## 확인 문제

1. Neo4j가 Running이면 Kafka→Neo4j 연동도 동작한다고 말할 수 있는가?
2. Secret의 비밀번호만 바꾸면 기존 DB 로그인도 자동으로 바뀌는가?

**해설:** DB 가동과 ingestion 연결은 별도다. 기존 DB의 인증 변경은 DB가 지원하는
암호 변경 절차와 Secret 갱신을 함께 맞춰야 한다.

참고: [Neo4j Kubernetes 구성](https://neo4j.com/docs/operations-manual/current/kubernetes/configuration/).
