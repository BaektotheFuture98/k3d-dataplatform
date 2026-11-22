# 기사 파이프라인 배포

- [파이프라인 운영 문서](../../../../configs/pipelines/README.md)에 작업별 ConfigMap, 공유 Spark 설정, Secret 및 S3A 체크포인트 계약이 있다.
- 스트리밍 Deployment는 `replicas: 0`, 발행 CronJob은 `suspend: true`가 저장소의 기본값이다. 수집 Job 템플릿과 스모크 Job은 개별 실행 대상으로 취급한다.
- 오프라인 스모크에는 격리된 테이블과 체크포인트를 사용한다. 실제 Gemini 호출이나 상시 작업 활성화는 해당 실행이 요청된 경우에만 진행한다.
