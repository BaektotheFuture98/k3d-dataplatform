# Neo4j Community files

공식 `neo4j/neo4j` Helm chart **5.26.32**, image **neo4j:5.26.32-community**를 고정한다.
Kafka connector 5.1.16의 Neo4j 5.x 지원 범위와 맞춘 단일 Community 인스턴스다.
이 작업은 파일 구성만 수행했으며 설치·Secret 생성·Cypher 실행은 하지 않았다.

공식 근거: [chart repository/index](https://neo4j.github.io/helm-charts/index.yaml), [고정 chart archive](https://github.com/neo4j/helm-charts/releases/download/5.26.32/neo4j-5.26.32.tgz), [Helm 설정 문서](https://neo4j.com/docs/operations-manual/current/kubernetes/configuration/), [connector 호환성](https://neo4j.com/docs/kafka/5.1/).
다운로드한 고정 chart의 values/templates를 정적으로 확인했다. `neo4j.passwordFromSecret`는 `NEO4J_AUTH` 키(`neo4j/<password>`)를 요구한다. `existingSecret` 또는 단독 raw password 키는 chart 설정이 아니다.
Secret `neo4j-auth`는 chart용 `NEO4J_AUTH`와 Connect용 `neo4j-password` raw 값이 같은 비밀번호를 가리켜야 한다.
비밀번호를 values나 Git에 저장하지 않는다. 기존 PVC의 인증은 초기 Secret 변경만으로 바뀌지 않으므로 기존 데이터의 암호 회전은 별도 운영 절차다.

release 이름 **neo4j**, namespace **finance-platform**을 유지하면 기본 ClusterIP service `neo4j:7687`가 생성된다.
외부 LoadBalancer와 admin/internal 추가 service는 끈다. 기본 ClusterIP service는 chart의 unconditional 템플릿으로 유지된다. `operations.enableServer: false`는 Enterprise cluster의 ENABLE SERVER 작업만 비활성화하며 Community database 시작을 막지 않는다. HTTP가 필요하면 이후 별도 port-forward 작업으로 접근한다.
10Gi local-path RWO PVC, CPU 500m/메모리 2Gi, heap 512m/page cache 512m이다. 개발 데이터량 기준이며 부하 검증은 하지 않았다.
PVC/데이터를 삭제하거나 초기화하는 명령은 제공하지 않는다.

아래는 **나중에 사용할 문서용 명령**이며 이번 작업에서 실행하지 않았다.
로컬 template의 `disableLookups=true`는 클러스터 조회를 생략한다. 실제 설치에서는 생략하여 chart의 기존 Secret 검사를 유지한다.

```sh
helm template neo4j neo4j --repo https://neo4j.github.io/helm-charts/ --version 5.26.32 --namespace finance-platform -f deploy/k8s/helm/neo4j/values.yaml --set disableLookups=true > /tmp/neo4j-rendered.yaml
# 사용자 후속 실행 시, Secret을 먼저 준비한 뒤:
helm upgrade --install neo4j neo4j --repo https://neo4j.github.io/helm-charts/ --version 5.26.32 --namespace finance-platform -f deploy/k8s/helm/neo4j/values.yaml
```

`constraints.cypher`는 sink 활성화 전 수동 적용용이다. Article.article_id와 Event.event_id의 uniqueness만 요구하므로 Community에서 사용 가능하다.
실제 DB 접속·constraints·중복 이벤트/오래된 버전 동작 검증은 남아 있다. event shape와 누적 관계 의미는 [Kafka 계약](../kafka/README.md)을 따른다.
