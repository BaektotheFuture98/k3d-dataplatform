# Spark와 JupyterLab 배포

- [configmap.yaml](configmap.yaml)의 Spark 설정을 [원본 구성](../../../../configs/spark)과 대조한다. Jupyter 및 기사 파이프라인이 공통 설정을 소비한다.
- [jupyter.yaml](jupyter.yaml)의 인증 Secret, PVC, 노트북과 설정 마운트를 확인한다. 데이터 경로 변경 시 Iceberg REST, Garage S3A, 기존 체크포인트까지 검토한다.
- 데이터 경로 검증은 [Spark 운영 문서](../../../../configs/spark/README.md)의 합성 테스트 절차를 사용한다.
