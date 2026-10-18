FROM eclipse-temurin:21.0.8_9-jdk-jammy AS build
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch apache-iceberg-1.11.0 https://github.com/apache/iceberg.git .
# Official open-api shadowJar packages RESTCatalogServer test fixtures and their runtime.
RUN printf '1.11.0\n' > version.txt && ./gradlew --no-daemon :iceberg-open-api:shadowJar -x test
RUN mkdir /out && cp open-api/build/libs/iceberg-open-api-test-fixtures-runtime-1.11.0.jar /out/catalog.jar
# Maven Central publishes SHA-1, but no SHA-256 sidecar for this artifact.
# SHA-256 recorded from the HTTPS Maven Central artifact on 2026-10-18.
RUN curl -fsSLo /out/postgresql.jar https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.8/postgresql-42.7.8.jar && echo "2a32a9dcbc42d67a50ad3a0de5efd102c8d2be46720045f2cbd6689f160ab7c7  /out/postgresql.jar" | sha256sum -c -
FROM eclipse-temurin:21.0.8_9-jre-jammy
WORKDIR /opt/catalog
COPY --from=build /out/ ./
USER 185:185
EXPOSE 8181
# The upstream fixture logs the complete catalog property map at INFO (including jdbc.password).
# Keep this class OFF even if another logger is later raised for diagnosis.
ENTRYPOINT ["java", "-Dorg.slf4j.simpleLogger.log.org.apache.iceberg.rest.RESTCatalogServer=off", "-cp", "/opt/catalog/*", "org.apache.iceberg.rest.RESTCatalogServer"]
