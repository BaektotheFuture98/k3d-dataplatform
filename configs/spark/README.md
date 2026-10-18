# Catalog / Spark 파일 구성

> 2026-10-18 실행 업데이트: 두 ARM64 이미지를 저장소 Dockerfile로 빌드하고 k3d `dev`에 import했다. 아래는 최초 정적 준비 시점 기록이며, 실제 빌드 결과·수정·검증은 [runtime 실행 기록](../runtime/catalog-spark-notes.md)을 참조한다.

사용자의 후속 실행 지시에 따라 Catalog와 Jupyter를 배포했다. 합성 테이블 쓰기·읽기와
Catalog 재시작 후 새 Spark 세션의 재조회·테이블 정리에 성공했다.
기사 파이프라인은 생성하지 않았다. 전체 결과는 [실행 검증](../runtime/VALIDATION.md)에 있다.

## 버전과 공식 근거

- [Spark 4.1.2 릴리스](https://spark.apache.org/releases/spark-release-4-1-2.html), Scala 2.13 / Java 21 기반.
- [Iceberg 지원 매트릭스](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/site/docs/multi-engine-support.md): Spark 4.1 지원 시작은 Iceberg 1.11.0. `iceberg-spark-runtime-4.1_2.13:1.11.0`과 `iceberg-aws-bundle:1.11.0`을 함께 사용한다.
- [공식 1.11.0 open-api build](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/build.gradle): `:iceberg-open-api:shadowJar`는 REST test fixture runtime을 만든다. PostgreSQL JDBC 42.7.8을 추가한다. [JDBC catalog](https://iceberg.apache.org/docs/latest/jdbc/).
- [RESTCatalogServer](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/open-api/src/testFixtures/java/org/apache/iceberg/rest/RESTCatalogServer.java), [환경 변수 변환](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/open-api/src/testFixtures/java/org/apache/iceberg/rest/RCKUtils.java): `CATALOG_` 제거 후 `__` → `-`, `_` → `.`. `CATALOG_JDBC_PASSWORD`는 Kubernetes Secret 값을 직접 받으며 셸 문자열 치환에 의존하지 않는다.
- [공식 알려진 1.11.0 Spark runtime 문제](https://github.com/apache/iceberg/issues/16856): Spark 전용 환경에서 Flink 클래스 로딩 문제가 보고되어 있다. 버전 조합 지원과 실제 실행 성공은 별개이며, 현재 핀을 유지하고 이후 smoke test에서 확인해야 한다. 임의의 Flink 의존성 추가나 업그레이드는 하지 않았다.

실제 이미지 빌드에서 Spark archive SHA-512와 Iceberg Maven jar SHA-256 검증을 통과했다.
PostgreSQL JDBC jar는 SHA-256 sidecar가 없어 다운로드한 공식 artifact의 해시를 Dockerfile에 고정했다.
checksum은 독립적인 서명 검증을 대체하지 않는다. REST는 고정 릴리스 tag를 clone하고
version.txt=1.11.0을 명시해 fixture를 패키징한다. 베이스 이미지는 버전 tag이며 pip 전이 의존성은 lock하지 않았다.

## 실행한 빌드 / import 명령

아래는 저장소 루트에서 실행한 빌드와 import 절차다.

```sh
docker build -f docker/iceberg-rest/Dockerfile -t finance-platform/iceberg-rest:1.11.0-pg42.7.8 .
docker build -f docker/spark/Dockerfile -t finance-platform/spark:4.1.2-iceberg1.11.0-s3a-v1 .
k3d image import finance-platform/iceberg-rest:1.11.0-pg42.7.8 --cluster dev
k3d image import finance-platform/spark:4.1.2-iceberg1.11.0-s3a-v1 --cluster dev
```

렌더링 시 `__ICEBERG_REST_IMAGE__`, `__SPARK_IMAGE__`를 실제 사용자 이미지명으로 대체한다. ARM 노드에서는 해당 아키텍처로 빌드한다. 업무 pipeline 코드는 포함하지 않는다.

## 연결 및 Secret 계약

모두 `finance-platform`. Catalog `iceberg-rest:8181`, PostgreSQL `postgres:5432/iceberg_catalog`, 사용자 `iceberg_user`, Secret `postgres-credentials/iceberg-password`. JDBC catalog는 Iceberg catalog 테이블을 초기화할 수 있는 DB 권한이 필요하다.

Garage `http://garage.finance-platform.svc.cluster.local:3900`, region `garage`, path-style, warehouse `s3://warehouse/`. Catalog와 Spark는 AWS SDK 기본 credential provider가 읽는 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`에 `garage-credentials/s3-access-key-id` / `s3-secret-access-key`를 직접 주입한다. 키는 spark-defaults, 이미지, ConfigMap에 넣지 않는다.

Jupyter는 replicas=1이고 `jupyter-auth/token`으로 인증한다. Secret을 생성했고 무토큰/잘못된 토큰은
HTTP403, 올바른 토큰은 HTTP200으로 확인했다. ClusterIP `jupyter:8888`를 유지하며
이후 추가한 Traefik Ingress로 Mac의 `http://jupyter.localhost:8080`에서 접근한다.
토큰 인증과 WebSocket 연결을 검증했다. [로컬 UI 접속 설정](../ingress/README.md)을 참고한다.
노트북은 `jupyter-workspace` local-path PVC에 보관한다. Spark는 각 프로세스의 `local[2]`로 실행한다.
Spark UI는 비활성화했다. `configs/spark/spark-defaults.conf`와 ConfigMap을 함께 유지한다.

## 원본 Spark 설정과의 동기화

기존 프로젝트의 `spark-defaults.conf`와 `log4j2.properties`를 기준으로 공통 설정을 정리했다.
Iceberg Catalog 설정은 유지하고 MinIO endpoint를 Garage로 바꿨다.
S3A에도 Garage endpoint·region·path-style·HTTP 설정을 적용한다.
인증은 `EnvironmentVariableCredentialsProvider`를 사용하며 설정 파일에 키를 넣지 않는다.

이미지에는 Spark 배포판의 Hadoop과 동일한 `hadoop-aws:3.4.2` 및
Hadoop 릴리스 POM에 지정된 `software.amazon.awssdk:bundle:2.29.52`를 추가한다.
두 artifact의 SHA-256은 Dockerfile에 고정했다.
근거: [Hadoop 3.4.2 POM](https://github.com/apache/hadoop/blob/rel/release-3.4.2/hadoop-project/pom.xml),
[S3A 의존성 안내](https://hadoop.apache.org/docs/r3.4.2/hadoop-aws/tools/hadoop-aws/index.html).
Iceberg AWS bundle도 유지하므로 클래스패스 조합은 S3A 체크포인트와 Iceberg 입출력을 함께 검증한다.
실제 검증에서 AWS SDK는 `bundle-2.29.52.jar`에서 로드되었고, 별도 Spark 프로세스로
체크포인트를 복구해 합성 데이터가 3행에서 중복 없이 6행으로 이어졌다.
같은 클래스패스의 Iceberg 쓰기·읽기와 검증 데이터 정리도 성공했다.

원본과 동일하게 console root WARN·Iceberg INFO 로깅과 Spark 이벤트 로그를 활성화한다.
이벤트 로그는 현재 컨테이너의 쓰기 가능한 `file:///tmp/spark-events`에 저장한다.
원본의 `/home/iceberg/spark-events`와 경로만 다르며 별도 History Server나 로그 영속 볼륨은 구성하지 않는다.
Pod 교체 시 이벤트 로그는 유지되지 않는다. 노트북 PVC와 Garage의 checkpoint는 별개로 보존한다.

2 CPU 개발 노드에 맞춘 driver 1GiB, shuffle partitions=4, UI 비활성화와 Java 21은 유지한다.
UTC를 공통 설정으로 지정했다. 두 업무 streaming 템플릿도 동일 ConfigMap을 사용하지만
업무 코드·이미지의 준비와 실행 검증은 별도다.

Catalog와 Jupyter에는 `AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED`,
`AWS_RESPONSE_CHECKSUM_VALIDATION=WHEN_REQUIRED`를 설정한다. 기본 AWS SDK CRC trailer는
Garage에서 `Invalid payload signature`로 실패했고 이 설정 후 동일 테스트가 성공했다.
[AWS 공식 체크섬 설정](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/s3-checksums.html).
나중에 게시하는 업무 이미지의 S3 클라이언트에도 해당 호환 설정을 적용해야 한다.

## 제한과 후속 실행 검증

REST 서버는 Apache의 **테스트 fixture**이며 운영용 서버가 아니다. 인증·권한 분리·TLS·고가용성 제공을 전제하지 않는다. 신뢰할 수 있는 개발 클러스터 내부 전용이며 외부로 노출하지 않는다. 해당 fixture의 INFO 로그는 전체 catalog 속성(암호 포함)을 기록하므로 서버 클래스 로거를 OFF로 고정했다. 이를 해제하지 않는다. 자격증명 전달은 AWS 환경변수로 처리하며 클라이언트에 credential vending하지 않는다.

실제 검증은 합성 namespace/table 생성 → write/read → Catalog 재시작 → 새 Spark 세션 read →
테스트 테이블 PURGE까지다. JDBC `iceberg_tables` 행도 확인했다. 이번 smoke 경로에서는
보고된 선택적 Flink 클래스 오류가 재현되지 않았으며 streaming·업무 변환 전반의 호환성을 보장하지 않는다.
Jupyter HTTP 인증과 별도 PySpark 프로세스는 확인했지만 브라우저 노트북 UI/kernel 상호작용은 미검증이다.
기존 데이터를 삭제하거나 PVC를 재생성하지 않았다.

## Article 테이블 구성

후속 요청으로 기존 프로젝트 노트북의 생성 정의를 옮겨 `bronze.article`, `silver.article`,
`gold.graph_article`, `ops.ontology_batch_job`을 생성했다. 스키마·파티션·속성·0행을 확인했고
노트북을 새 커널에서 두 번 실행해 재실행 가능 여부도 확인했다.
[노트북 안내](../../workspace/notebooks/README.md)와 [실행 기록](../runtime/VALIDATION.md)을 참고한다.
