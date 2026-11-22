# Neo4j 배포

- [values.yaml](values.yaml), [운영 안내](../../../../configs/neo4j/README.md), [제약조건](../../../../configs/neo4j/constraints.cypher)을 함께 확인한다.
- 인증 Secret 참조와 PVC 계약을 유지하고, Kafka Connect 설정 변경 시 Bolt 주소와 인증 키가 맞는지 확인한다.
- 검증에는 내부 Bolt 연결과 합성 데이터 쿼리를 사용한다. [Neo4j 검증 스크립트](../../../../configs/runtime/neo4j-smoke.sh)의 조회와 쓰기 모드를 구분한다.
