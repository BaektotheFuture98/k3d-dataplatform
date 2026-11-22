# Airflow DAG 소스

- [article_collection.py](dags/article_collection.py)는 기사 수집 워크플로를 정의한다. collector의 [Job 템플릿](../../deploy/k8s/manifests/pipelines/article-collector/job-template.yaml)과 DAG의 이미지·ServiceAccount·인자 계약을 함께 확인한다.
- 정적 구문 확인과 실행 중 Airflow에서의 DAG import·태스크 실행을 구분한다. worker Pod 검증은 [KubernetesExecutor 운영 안내](../../configs/airflow/KUBERNETES-EXECUTOR.md)를 참고한다.
