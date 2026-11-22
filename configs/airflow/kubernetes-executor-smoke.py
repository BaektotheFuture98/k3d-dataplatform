"""Manual-only infrastructure check: no pipeline or external service calls."""
from datetime import datetime, timezone

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def verify_worker():
    import os
    import socket
    import time

    hostname = socket.gethostname()
    assert not hostname.startswith('airflow-scheduler-'), hostname
    assert os.environ['AIRFLOW__CORE__EXECUTOR'] == 'KubernetesExecutor'
    print(f'KUBERNETES_EXECUTOR_SMOKE_OK worker={hostname}', flush=True)
    time.sleep(15)
    return hostname


with DAG(
    dag_id='airflow_kubernetes_executor_smoke',
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    tags=['infrastructure', 'smoke'],
) as dag:
    PythonOperator(task_id='verify_worker', python_callable=verify_worker, retries=0)
