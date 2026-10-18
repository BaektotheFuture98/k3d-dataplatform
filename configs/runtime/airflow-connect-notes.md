# Airflow and Kafka Connect infrastructure images

These images support infrastructure services only. The Airflow image contains no
project DAG or collector Job template. The Connect image contains the Neo4j plugin,
but no connector instance is created and no events are consumed or written by this
image build or its offline inspections.

- Airflow: `finance-platform/airflow:3.0.2-kubernetes-10.24.0-infra`
- Connect: `finance-platform/kafka-connect-neo4j:0.51.0-kafka4.2.0-neo4j5.1.16`

Build for `linux/arm64` from the repository root with the respective Dockerfiles.
The Neo4j JAR download is verified against its pinned SHA256 during the build.
Runtime credentials are supplied by deployment configuration, never baked into
these images.

Validated on 2026-10-18:

- Both images built as ARM64 and imported successfully into k3d cluster `dev`.
- Airflow image ID: `sha256:e79012de765df52d18c5e0d426bc0550b10836b4fa5e501b0a7301ee830d28e1`.
- Connect image ID: `sha256:572a8c734d65072a944479d3e37abbbb70d3d51de03dce52280c87c8bf13231d`.
- Airflow reports 3.0.2, Kubernetes provider reports 10.24.0, and
  `KubernetesJobOperator` imports. `/opt/airflow/dags` contains no Python files.
- `pip check` passes during the Airflow build. `cryptography==45.0.7` and
  `cffi==1.17.1` preserve compatibility with dependencies already in the official
  image; leaving them unbounded selected incompatible 50.0.2 and 2.1.1 versions.
- Connect's JAR SHA256 matches the Dockerfile pin; the packaged sink and source
  classes are `org.neo4j.connectors.kafka.{sink,source}.Neo4jConnector` and the
  manifest reports 5.1.16. Its runtime is Java 21 and Kafka client JAR is 4.2.0.
- Inspections used `--network none`; no worker, connector instance, DAG, or
  pipeline was executed during validation.
