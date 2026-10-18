# Build from repository root; targets: bronze-to-silver, silver-to-gold, test.
ARG SPARK_BASE=finance-platform/spark:4.1.2-iceberg1.11.0-s3a-v1
FROM ${SPARK_BASE} AS runtime
USER root
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python UV_PROJECT_ENVIRONMENT=/opt/pipelines UV_LINK_MODE=copy
RUN python3 -m pip install --no-cache-dir uv==0.11.29
COPY workspace/pipelines/pyproject.toml workspace/pipelines/uv.lock /opt/pipeline-project/
RUN uv sync --no-cache --frozen --no-default-groups --project /opt/pipeline-project --python 3.13.14
ENV PATH=/opt/pipelines/bin:$PATH \
    PYSPARK_PYTHON=/opt/pipelines/bin/python \
    PYSPARK_DRIVER_PYTHON=/opt/pipelines/bin/python \
    PYTHONPATH=/app:/app/article_silver_to_gold:/opt/spark/python:/opt/spark/python/lib/py4j-src.zip
COPY --chown=185:185 workspace/pipelines/pipeline_runtime /app/pipeline_runtime
WORKDIR /app
USER 185:185

FROM runtime AS bronze-to-silver
COPY --chown=185:185 workspace/pipelines/article_bronze_to_silver/main.py workspace/pipelines/article_bronze_to_silver/__init__.py /app/article_bronze_to_silver/
COPY --chown=185:185 workspace/pipelines/article_bronze_to_silver/transformations /app/article_bronze_to_silver/transformations
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/spark/bin/spark-submit", "/app/article_bronze_to_silver/main.py"]
CMD []

FROM runtime AS silver-to-gold
USER root
RUN uv sync --no-cache --frozen --no-default-groups --extra semantic --project /opt/pipeline-project --python 3.13.14
COPY --chown=185:185 workspace/pipelines/article_silver_to_gold /app/article_silver_to_gold
USER 185:185
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/spark/bin/spark-submit", "/app/article_silver_to_gold/main.py"]
CMD []

FROM silver-to-gold AS test
USER root
RUN uv sync --no-cache --frozen --no-default-groups --extra semantic --group test --project /opt/pipeline-project --python 3.13.14
COPY --chown=185:185 workspace/pipelines/article_bronze_to_silver /app/article_bronze_to_silver
COPY --chown=185:185 workspace/pipelines/tests /app/tests
COPY --chown=185:185 configs/runtime/article-pipeline-smoke.py /app/validation/article-pipeline-smoke.py
COPY --chown=185:185 workspace/notebooks/sql /app/validation/sql
USER 185:185
ENTRYPOINT ["/opt/pipelines/bin/python", "-m", "pytest"]
CMD ["-q", "-p", "no:cacheprovider", "/app/tests", "/app/article_bronze_to_silver/tests"]
