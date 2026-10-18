# 후속 플랫폼 파일 구성 검증

## 범위

사용자 최신 지시에 따라 파일만 구축했다. 구현은 `gpt-6.1-sol` / `low` 서브에이전트
3개가 Catalog·Spark, Kafka·Neo4j, Airflow·pipeline 설정을 병렬 작성했다.
서비스/Secret/이미지/이벤트 계약과 최종 변경 검토는 주 에이전트가 수행했다.

이번 작업에서는 Kubernetes 명령, 서버 dry-run, Helm 설치/template, Docker image
build/run/pull, k3d import, Secret 생성, Job 실행을 하지 않았다.
공식 문서 및 일부 chart/릴리스 메타데이터 다운로드는 읽기 전용으로 수행했다.
이전 PostgreSQL/Garage 런타임 검증 기록과 이번 정적 결과는 구분한다.

## 최종 정적 검증 결과

- `ruby scripts/check-configs.rb`: YAML 문서 35개 파싱. namespace/표준 label,
  민감 env의 Secret 참조, pipeline Deployment=0/CronJob suspend=true 검사 통과.
- 빈 MinIO scaffold 3개는 그대로 보존하며 파싱/구현 대상에서 제외했다.
- `python3 -m unittest discover -s tests -v`: **12/12 통과**.
- Python 파일 전체 AST 구문 통과. DAG나 Spark/Jupyter 애플리케이션을 import하지 않았다.
- 임시 디렉터리에서 fixture 이미지 참조로 전체 렌더링: YAML 파일 **29개** 생성 및 재파싱 통과.
  출력은 테스트 후 정리했으며 배포나 이미지 존재 확인을 하지 않았다.
- PostgreSQL ConfigMap의 초기화 shell과 검증 Job의 shell을 `bash -n`으로 확인했다.
- Spark SHA-512 보조 파서는 bare/GNU/BSD/wrapped-hex와 불일치 거부를 검사했다.
- `git diff --check`: 통과.

## 검토 중 수정한 연결 문제

- Airflow chart의 repository/tag 분리와 전체 이미지 입력을 맞췄다.
- 이미지 토큰 renderer가 Iceberg 환경변수 `CATALOG_S3_PATH__STYLE__ACCESS`의
  일부를 토큰으로 오인하는 문제를 재현한 테스트를 추가하고 수정했다.
- 실제 민감 값 대신 fixture로 SQLAlchemy 비밀번호 URL encoding,
  Neo4j chart/Connect 인증 키 일치를 검증했다.
- KJO가 operator의 image로 Job template image를 덮어쓰는 공식 구현을 확인했다.
- Neo4j chart의 기본 ClusterIP Service가 release `neo4j` 이름을 쓰는 것을 확인했다.
  `operations.enableServer=false`는 Community DB를 중지하지 않는다는 설명을 수정했다.
- Airflow는 명시적 FabAuthManager와 기본 사용자 생성 비활성화를 사용한다.
- 2 CPU 노드 여유를 위해 Jupyter도 기본 replicas=0의 필요 시 사용하도록 했다.

## 검증하지 않은 항목과 알려진 제한

- Helm values의 전체 schema/template 렌더링 및 CRD의 서버 검증.
- 실제 Dockerfile 빌드, base image ARM64 availability, artifact 다운로드와 packaging.
- REST fixture의 JDBC 초기화/테이블 생성/HTTP/S3 I/O, Jupyter 인증 및 kernel 동작.
- Spark 4.1.2/Iceberg 1.11.0의 실제 처리. 요청한 버전의
  [선택적 Flink 클래스 로딩 문제](https://github.com/apache/iceberg/issues/16856)는
  알려진 제한으로 남아 있으며 해결·우회 성공을 주장하지 않는다.
- Airflow 의존성 설치/실제 DAG import, KubernetesJobOperator 실행과 인증 계정 provisioning.
- Kafka 기동/플러그인 로딩/Neo4j Cypher/중복·역순 이벤트 통합 시험.
- 실제 기사 수집·변환·Gold 변경 발행 애플리케이션과 Service API 구현.
- 전체 스택 동시 실행, 백업 복원, 호스트 장애 복구.

Pipeline Docker Hub 이미지와 실제 업무 구현은 사용자가 나중에 제공한다.
Streaming/Publisher/Connect는 기본 비활성이고 수집 Job은 명시적 생성 전용이다.
정적 구문 통과를 실행 가능성·업무 처리 성공으로 간주하지 않는다.

## 후속 자원 검토

Jupyter/업무 작업을 제외한 앱 requests는 약 1700m CPU이며 기존 시스템 요청량을
더하면 약 1900m다. chart init/hook/sidecar는 렌더링 후 다시 합산해야 한다.
두 streaming 각 250m와 Connect 100m를 활성화하면 약 2500m가 되어 2 CPU를 초과한다.
사용자가 전체 동시 실행을 원할 때는 CPU 할당 또는 작업 배치/요청량을 먼저 조정해야 한다.
현재 cluster/Colima 자원을 자동으로 변경하지 않았다.
