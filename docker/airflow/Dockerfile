# Build context: repository root. Infrastructure only; no DAGs or job templates.
FROM apache/airflow:3.0.2-python3.12
USER airflow
# Existing Snowflake, MSAL, gcloud and PyOpenSSL dependencies bound these shared
# libraries. Keep their compatible versions while upgrading the K8s provider.
RUN pip install --no-cache-dir "apache-airflow==3.0.2" "apache-airflow-providers-cncf-kubernetes==10.24.0" "cryptography==45.0.7" "cffi==1.17.1" \
    && pip check
