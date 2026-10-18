# Build context: repository root. File-only example; do not build yet.
FROM apache/airflow:3.0.2-python3.12
USER airflow
# Keep Airflow pinned while adding the operator provider; resolve/lock and test
# the complete dependency set before publishing this image.
RUN pip install --no-cache-dir "apache-airflow==3.0.2" "apache-airflow-providers-cncf-kubernetes==10.24.0"
COPY --chown=airflow:root workspace/airflow/dags/article_collection.py /opt/airflow/dags/article_collection.py
COPY --chown=airflow:root deploy/k8s/manifests/pipelines/article-collector/job-template.yaml /opt/airflow/job-templates/article-collector.yaml
