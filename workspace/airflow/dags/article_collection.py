"""Deployment contract only: the collector application is supplied separately."""
from datetime import datetime, timedelta, timezone
import os
import re

from airflow.sdk import DAG
from airflow.providers.cncf.kubernetes.operators.job import KubernetesJobOperator


class ConfiguredCollectorJobOperator(KubernetesJobOperator):
    """Validate at task execution so missing configuration does not break DAG parsing."""

    def execute(self, context):
        image = os.environ.get('ARTICLE_COLLECTOR_IMAGE', '').strip()
        if not image or re.search(r'__[A-Z][A-Z0-9_]*__', image):
            raise ValueError('Set ARTICLE_COLLECTOR_IMAGE to the published collector image before running this DAG')
        if any(c.isspace() for c in image):
            raise ValueError('ARTICLE_COLLECTOR_IMAGE must be a single container image reference')
        self.image = image
        return super().execute(context)


with DAG(
    dag_id='article_collection',
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    tags=['finance-platform'],
) as dag:
    ConfiguredCollectorJobOperator(
        task_id='collect_articles',
        name='article-collector',
        namespace='finance-platform',
        # Deliver this file alongside the DAG in the custom Airflow image.
        job_template_file='/opt/airflow/job-templates/article-collector.yaml',
        in_cluster=True,
        kubernetes_conn_id=None,
        wait_until_job_complete=True,
        deferrable=False,
        get_logs=True,
        do_xcom_push=False,
        on_finish_action='keep_pod',
        on_kill_propagation_policy='Foreground',
        backoff_limit=1,
        ttl_seconds_after_finished=86400,
        retries=0,
        execution_timeout=timedelta(minutes=35),
    )
