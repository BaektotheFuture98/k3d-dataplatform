# Kafka와 Kafka Connect

- Kafka·NodePool·토픽·Connect·Neo4j sink 순으로 리소스 간 의존성을 확인한다. Operator 설정은 [Strimzi](../../helm/strimzi)에 있다.
- 토픽과 메시지 계약을 바꾸면 [기사 이벤트 예제](../../../../configs/kafka/article-gold.example.json), 커넥터 매핑과 [Neo4j 제약조건](../../../../configs/neo4j/constraints.cypher)을 함께 확인한다.
- 배포 상태와 별개로 [Kafka 운영 안내](../../../../configs/kafka/README.md)의 준비 범위와 검증 절차를 참고한다.
