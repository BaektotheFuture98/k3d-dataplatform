FROM eclipse-temurin:21.0.8_9-jre-jammy
ARG SPARK_VERSION=4.1.2
ARG ICEBERG_VERSION=1.11.0
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates python3 python3-pip tini && rm -rf /var/lib/apt/lists/*
COPY docker/spark/verify-sha512.py /usr/local/bin/verify-sha512.py
WORKDIR /tmp/download
RUN curl -fsSLO https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz && curl -fsSLO https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz.sha512 && python3 /usr/local/bin/verify-sha512.py spark-${SPARK_VERSION}-bin-hadoop3.tgz spark-${SPARK_VERSION}-bin-hadoop3.tgz.sha512 && tar -xzf spark-${SPARK_VERSION}-bin-hadoop3.tgz -C /opt && mv /opt/spark-${SPARK_VERSION}-bin-hadoop3 /opt/spark && rm -f spark-*
# Iceberg supplies table I/O; Hadoop S3A dependencies below supply checkpoints.
RUN for artifact in iceberg-spark-runtime-4.1_2.13 iceberg-aws-bundle; do url="https://repo.maven.apache.org/maven2/org/apache/iceberg/${artifact}/${ICEBERG_VERSION}/${artifact}-${ICEBERG_VERSION}.jar"; curl -fsSLo "/opt/spark/jars/${artifact}.jar" "$url"; curl -fsSLo /tmp/artifact.sha256 "${url}.sha256"; echo "$(cat /tmp/artifact.sha256)  /opt/spark/jars/${artifact}.jar" | sha256sum -c -; done
RUN ln -s /opt/spark/python/lib/py4j-[0-9]*-src.zip /opt/spark/python/lib/py4j-src.zip
RUN python3 -m pip install --no-cache-dir jupyterlab==4.4.9 ipykernel==6.30.1 && useradd -m -u 185 spark && mkdir -p /workspace /opt/spark/work-dir && chown -R 185:185 /workspace /opt/spark/work-dir
# Spark 4.1.2 bundles Hadoop 3.4.2. The Hadoop release POM pins SDK v2 2.29.52.
# SHA-256 values recorded from official Maven Central artifacts on 2026-10-18.
RUN curl -fsSLo /opt/spark/jars/hadoop-aws-3.4.2.jar https://repo.maven.apache.org/maven2/org/apache/hadoop/hadoop-aws/3.4.2/hadoop-aws-3.4.2.jar \
    && echo 'd2d24e6b715b5656b9d238bf13b6682a07e2004dd36aad74a73aeb854319f4d9  /opt/spark/jars/hadoop-aws-3.4.2.jar' | sha256sum -c - \
    && curl -fsSLo /opt/spark/jars/bundle-2.29.52.jar https://repo.maven.apache.org/maven2/software/amazon/awssdk/bundle/2.29.52/bundle-2.29.52.jar \
    && echo '62638f33045690c6bc5e496b54b0b2e89a9ad38cbedacdf6e017fea6bc85f55c  /opt/spark/jars/bundle-2.29.52.jar' | sha256sum -c - \
    && mkdir -p /tmp/spark-events && chown 185:185 /tmp/spark-events
ENV SPARK_HOME=/opt/spark PATH=/opt/spark/bin:$PATH PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-src.zip HOME=/home/spark
COPY docker/spark/jupyter_server_config.py /etc/jupyter/jupyter_server_config.py
USER 185:185
WORKDIR /workspace
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["jupyter", "lab", "--config=/etc/jupyter/jupyter_server_config.py"]
