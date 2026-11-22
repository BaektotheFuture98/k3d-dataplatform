# Airflow 배포

- [values.yaml](values.yaml)과 [executor-resources.yaml](executor-resources.yaml)을 함께 확인한다. KubernetesExecutor는 태스크별 worker Pod를 시작하므로 Pod 템플릿과 ServiceAccount·RBAC가 맞아야 한다.
- [KubernetesExecutor 운영 절차](../../../../configs/airflow/KUBERNETES-EXECUTOR.md)에 따라 scheduler·worker 상태, 검증 DAG 결과, worker 정리와 로그 PVC를 확인한다.
- DAG와 이미지가 바뀌면 [DAG 소스](../../../../workspace/airflow/dags)와 [Airflow Dockerfile](../../../../docker/airflow/Dockerfile)의 입력도 대조한다.
