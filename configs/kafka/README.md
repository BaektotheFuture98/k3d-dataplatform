# Kafka / Connect files

파일 구성 전용이며 이 작업에서는 배포·이미지 빌드·Secret 생성·메시지 전송을 실행하지 않았다.

## 고정 버전과 공식 근거

- Strimzi operator/chart/CRDs **0.51.0**, Kafka/Connect **4.2.0**, API `kafka.strimzi.io/v1`.
  [지원표](https://strimzi.io/downloads/), [동일 릴리스 단일 KRaft 예제](https://github.com/strimzi/strimzi-kafka-operator/blob/0.51.0/examples/kafka/kafka-single-node.yaml), [Connect v1 예제](https://github.com/strimzi/strimzi-kafka-operator/blob/0.51.0/examples/connect/kafka-connect.yaml).
  지원 Kubernetes 범위는 1.30–1.35이며 기존 클러스터 버전은 이번 작업에서 조회하지 않았다.
- Neo4j Apache Kafka connector **5.1.16** self-contained JAR.
  [5.1 설치 문서](https://neo4j.com/docs/kafka/5.1/installation/), [공식 릴리스](https://github.com/neo4j/neo4j-kafka-connector/releases/tag/5.1.16), [공식 SHA-256](https://github.com/neo4j/neo4j-kafka-connector/releases/download/5.1.16/neo4j-kafka-connect-5.1.16.jar.sha256).
  SHA-256 `f137e7b725eeb141cdc80e40bc8e58ae2cd8cc21aca86354b3e122ea8b8bc9f4`를 Dockerfile에서 검사한다.
  [5.1 호환 범위](https://neo4j.com/docs/kafka/5.1/)는 Kafka Connect >=3.4.1, Neo4j 5.x/2025.x, Java 11/17/21이다.
  최신 6.0은 Connect >=4.3.0을 요구하므로 이 Strimzi 조합에 사용하지 않는다.
- [5.1 sink 설정](https://neo4j.com/docs/kafka/5.1/sink/configuration/)의 클래스, `neo4j.cypher.topic.<topic>`와 `__value` 바인딩을 사용한다.
- [Strimzi 0.51 스키마](https://strimzi.io/docs/operators/0.51.0/configuring.html), [외부 설정 로딩](https://strimzi.io/docs/operators/0.51.0/deploying#con-loading-config-from-external-sources-str).
  Secret은 `template.pod.volumes`/`template.connectContainer.volumeMounts`로 `/mnt/neo4j-auth`에 마운트하며 DirectoryConfigProvider로 raw `neo4j-password` 키를 읽는다. Kubernetes Secret API 접근 권한을 Connect에 추가하지 않는다.

## 설치 경계와 나중에 사용할 명령

Operator는 release namespace `finance-platform`만 감시한다 (`watchNamespaces: []`, `watchAnyNamespace: false`).
CRD와 ClusterRole/ClusterRoleBinding은 클러스터 범위다. **0.51.0 CRD 설치/업그레이드와 클러스터 RBAC 준비는 별도 관리자 검토·승인이 필요한 단계**이며 기본 namespaced 적용 대상에 포함하지 않는다.
`createGlobalResources: false`는 기존 cluster role을 전제로 한다. Helm이 생성하는 cluster role binding도 관리자 검토 대상이다. operator chart를 일반 workload apply와 혼합하지 않는다.

아래는 문서용이며 실행하지 않았다. 로컬 template은 배포가 아니지만 Helm이 설치되어 있어야 한다.

```sh
helm template strimzi-cluster-operator strimzi-kafka-operator --repo https://strimzi.io/charts/ --version 0.51.0 --namespace finance-platform -f deploy/k8s/helm/strimzi/values.yaml > /tmp/strimzi-rendered.yaml
# 별도 관리자 승인 후에만 operator 설치 (사전 CRDs/cluster RBAC 필요):
helm upgrade --install strimzi-cluster-operator strimzi-kafka-operator --repo https://strimzi.io/charts/ --version 0.51.0 --namespace finance-platform --skip-crds -f deploy/k8s/helm/strimzi/values.yaml
# workloads 적용은 이후 별도 실행 단계에서: NodePool -> Kafka -> topics -> rendered Connect -> connector.
```

단일 dual-role broker/controller, 10Gi local-path PVC (`deleteClaim: false`), 내부 plaintext bootstrap `finance-kafka-kafka-bootstrap:9092`.
개발용이며 broker 중단 시 가용성은 없다. 모든 broker/Connect internal-topic replication factor와 min ISR은 1이다.
`article-gold`는 선언형 KafkaTopic으로 1 partition/1 replica, 7일 보관한다.
Connect internal topics는 worker가 명시적 AdminClient create로 생성하며 auto topic creation 비활성화와 충돌하지 않는다.

## 이미지와 안전한 활성화

`docker/kafka-connect/Dockerfile`은 pinned Strimzi base에 공식 Neo4j JAR을 넣는다.
기본 Strimzi 이미지에는 Neo4j sink가 없다. 이후 사용자가 이미지를 빌드·검증·게시한 뒤 `__KAFKA_CONNECT_IMAGE__`를 실제 digest/tag로 렌더링해야 한다.
현재 Connect `replicas: 0`, connector `state: stopped`다. 토큰 상태를 실행 가능한 배포로 간주하지 않는다.
Neo4j와 Secret 준비, 아래 제약조건 적용, plugin discovery와 이벤트 계약 검증을 마친 이후에만 worker replicas를 1로, connector state를 running으로 변경한다.
이 단계들은 아직 실행 검증하지 않았다.

## article-gold 계약

업무 publisher는 아직 구현되어 있지 않다. `article-gold.example.json`은 payload 예시다.
Kafka key는 nonempty `article_id` 문자열, value는 schema envelope 없는 JSON object여야 한다.
필수 필드는 `article_id` (string), `source_version` (0 이상의 단조 증가 integer), `event_id` (해당 article/version의 안정적 식별자), `events` (array)다.
동일 `(article_id, source_version)`는 항상 같은 내용이어야 하며 삭제/tombstone은 지원하지 않는다.
`title`, `url`, `published_at`는 문자열 또는 null이다. events 원소는 nonempty 안정적 `event_id`, `type`, `occurred_at` 문자열을 가진다.
같은 event_id의 event 속성은 불변이어야 한다. top-level event_id는 추적용이고 그래프 키는 article_id와 각 events[].event_id이다.

sink는 Article을 article_id로 MERGE하고 `source_version`이 현재 값보다 클 때만 갱신하며 Event/MENTIONS도 MERGE한다.
재전송과 오래된 버전은 article 상태를 덮어쓰지 않는다. 빈 events 배열도 article 업데이트는 유지한다.
이 매핑은 **누적 관계**이며 새 버전에서 빠진 이벤트를 삭제하지 않는다. 수정 가능한 Event 또는 완전 교체 관계가 필요하면 계약과 Cypher를 먼저 수정한다.
동일 article은 같은 Kafka key/partition으로 순서를 유지하고 tasksMax=1을 유지한다.
`configs/neo4j/constraints.cypher`의 uniqueness constraints를 activation 전에 적용해야 동시 writer에서도 중복 키가 생기지 않는다.
외부 writer는 이 버전/관계 계약을 준수해야 한다. 유효성 검증 실패는 tolerance=none으로 task를 중지시킨다. 잘못된 record를 조용히 건너뛰는 정책은 없다.

정적 검토는 YAML/계약 수준이며 브로커 기동, plugin class loading, Cypher 실행, 재전송/순서 뒤집힘 통합 검증은 이후 단계다.
