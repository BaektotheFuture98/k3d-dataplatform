# Strimzi 배포

- Operator 차트 설정과 [Kafka 리소스](../../manifests/kafka)는 별도로 관리한다. Kafka 매니페스트의 API 버전과 형식은 적용할 Strimzi CRD와 대조한다.
- 클러스터 상태는 Operator Deployment부터 Kafka·KafkaNodePool·KafkaConnect 상태 조건까지 확인한다. 준비 범위와 설치 순서는 [Kafka 운영 안내](../../../../configs/kafka/README.md)를 따른다.
