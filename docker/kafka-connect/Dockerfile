# Worker image only. Connector instances are configured separately.
FROM quay.io/strimzi/kafka:0.51.0-kafka-4.2.0
USER root:root
# Official self-contained Apache Kafka connector (not Confluent ZIP).
ADD https://github.com/neo4j/neo4j-kafka-connector/releases/download/5.1.16/neo4j-kafka-connect-5.1.16.jar /opt/kafka/plugins/neo4j/neo4j-kafka-connect-5.1.16.jar
RUN echo 'f137e7b725eeb141cdc80e40bc8e58ae2cd8cc21aca86354b3e122ea8b8bc9f4  /opt/kafka/plugins/neo4j/neo4j-kafka-connect-5.1.16.jar' | sha256sum -c - \
    && chmod 0644 /opt/kafka/plugins/neo4j/neo4j-kafka-connect-5.1.16.jar
USER 1001
