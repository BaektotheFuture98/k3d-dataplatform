# Catalog / Spark runtime build evidence

2026-10-18: ARM64 Colima Docker, repository Dockerfiles, no business pipeline execution.

## Spark / Jupyter

- Built `finance-platform/spark:4.1.2-iceberg1.11.0`, image ID prefix `d84e614c97e5`.
- Spark 4.1.2 archive SHA-512 and Iceberg runtime/AWS bundle 1.11.0 Maven SHA-256 checks passed during build.
- Isolated version inspection confirmed Java 21.0.8, Spark/PySpark 4.1.2, Scala 2.13.17, JupyterLab 4.4.9, ipykernel 6.30.1.
- `k3d image import finance-platform/spark:4.1.2-iceberg1.11.0 --cluster dev` completed successfully.
- Network-disabled Docker inspection produces hostname lookup warnings; setting `SPARK_LOCAL_IP=127.0.0.1` allows Spark's version command to complete. Cluster runtime validation is separate.
- Jupyter config requires a nonempty token from the environment and suppresses token-bearing startup URLs at WARN logging.

## Catalog provenance

The cached `datalakehouse/iceberg-rest:iceberg1.11.0` tag was not used: its embedded build properties reported a main-branch snapshot commit `b0df3ca01d61b2f7ae7143ac660c6b16e33b6e46`, not the requested release. The repository Dockerfile builds the fixture from `apache-iceberg-1.11.0`, which resolved to `6976e020b894f6a6777704df2b8c4458cb291ae9`. Upstream fixture shadow packaging includes the AWS bundle. PostgreSQL JDBC 42.7.8 is added separately. RESTCatalogServer logging remains OFF to prevent printing JDBC passwords.

The initial fixture compilation passed in 4m12s, but packaging failed because upstream's Git checkout computes the next development version (`1.12.0-SNAPSHOT`) without `version.txt`. The Dockerfile now writes the release version `1.11.0` before Gradle, matching upstream release tarball metadata. Inspection of the release-source fixture confirmed `SimpleLogger`, `SimpleLoggerFactory`, `SimpleServiceProvider`, its SLF4J provider service descriptor, Iceberg `S3FileIO`, and AWS SDK `S3Client` classes. The class-specific SimpleLogger OFF setting therefore uses the packaged logging backend.

- Corrected release compilation passed in 3m41s. Final built ARM64 image: `finance-platform/iceberg-rest:1.11.0-pg42.7.8`, `sha256:92baaf67f9e134d25a9e86e6fe50dc773fc720f2e98b2b8694f7f84337a3ba57`.
- Maven Central returned HTTP 200 for PostgreSQL JDBC 42.7.8 jar and `.sha1`, but HTTP 404 for `.sha256` and `.sha512`. The Dockerfile now verifies a fixed SHA-256 recorded from the HTTPS artifact: `2a32a9dcbc42d67a50ad3a0de5efd102c8d2be46720045f2cbd6689f160ab7c7`. This records downloaded bytes; it is not independent signature verification.
- A network-disabled, credential-free Java probe loaded `org.postgresql.Driver` and verified `RESTCatalogServer` logger `isInfoEnabled()` is false under the exact Dockerfile logger property.
- `k3d image import finance-platform/iceberg-rest:1.11.0-pg42.7.8 --cluster dev` completed successfully.
- Kubernetes deployment, JDBC catalog initialization, S3 operations, and synthetic Spark infrastructure validation are performed separately by the coordinating agent. No business DAG, article pipeline, or medallion data jobs were created or executed by this build task.

Build and deployment status in this file is execution evidence; the older `configs/spark/README.md` records the original static preparation stage.
