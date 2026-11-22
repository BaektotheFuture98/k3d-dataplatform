# Article 파이프라인 소스

- 공통 설정과 종료 처리는 [pipeline_runtime](pipeline_runtime), 엔트리포인트는 [Bronze→Silver](article_bronze_to_silver)와 [Silver→Gold](article_silver_to_gold)에 있다. 환경변수 변경은 [작업별 ConfigMap](../../deploy/k8s/manifests/pipelines)과 맞춘다.
- Python 3.13과 [uv.lock](uv.lock)을 사용한다. 저장소 루트에서 `uv run --project workspace/pipelines --locked --extra semantic --group test python -m pytest workspace/pipelines -q`로 오프라인 단위 테스트를 실행한다. Spark와 Iceberg 입출력 스모크는 [운영 문서](../../configs/pipelines/README.md)를 참고한다.
