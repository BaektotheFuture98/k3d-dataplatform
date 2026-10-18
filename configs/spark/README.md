# Catalog / Spark 파일 구성

이 변경은 파일 준비만 수행했다. 이미지 빌드·pull·컨테이너 실행, k3d import, Kubernetes 배포, DB/S3 연결 및 Spark 실행은 하지 않았다. 기존 PostgreSQL/Garage는 변경하지 않는다.

## 버전과 공식 근거

- [Spark 4.1.2 릴리스](https://spark.apache.org/releases/spark-release-4-1-2.html), Scala 2.13 / Java 21 기반.
- [Iceberg 지원 매트릭스](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/site/docs/multi-engine-support.md): Spark 4.1 지원 시작은 Iceberg 1.11.0. `iceberg-spark-runtime-4.1_2.13:1.11.0`과 `iceberg-aws-bundle:1.11.0`을 함께 사용한다.
- [공식 1.11.0 open-api build](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/build.gradle): `:iceberg-open-api:shadowJar`는 REST test fixture runtime을 만든다. PostgreSQL JDBC 42.7.8을 추가한다. [JDBC catalog](https://iceberg.apache.org/docs/latest/jdbc/).
- [RESTCatalogServer](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/open-api/src/testFixtures/java/org/apache/iceberg/rest/RESTCatalogServer.java), [환경 변수 변환](https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/open-api/src/testFixtures/java/org/apache/iceberg/rest/RCKUtils.java): `CATALOG_` 제거 후 `__` → `-`, `_` → `.`. `CATALOG_JDBC_PASSWORD`는 Kubernetes Secret 값을 직접 받으며 셸 문자열 치환에 의존하지 않는다.
- [공식 알려진 1.11.0 Spark runtime 문제](https://github.com/apache/iceberg/issues/16856): Spark 전용 환경에서 Flink 클래스 로딩 문제가 보고되어 있다. 버전 조합 지원과 실제 실행 성공은 별개이며, 현재 핀을 유지하고 이후 smoke test에서 확인해야 한다. 임의의 Flink 의존성 추가나 업그레이드는 하지 않았다.

Spark tarball의 SHA-512 검증기는 bare/GNU/BSD 및 줄바꿈된 hex digest를 처리하고 형식·불일치 검사를 로컬 정적 도구 검증으로 확인했다. 공식 4.1.2 `.sha512` 원문은 브라우저에서 가져오지 못했으므로 실제 다운로드 파일로 검증기를 실행한 것은 아니다. Spark tarball은 SHA-512, Maven jar는 게시된 SHA-256 파일을 빌드 시 확인한다. checksum은 다운로드 전송 검증이며 별도로 검토된 고정 해시나 서명 검증을 대체하지 않는다. REST 소스는 고정 릴리스 tag를 clone한다. 베이스 이미지는 버전 tag이며 digest pin은 후속 공급망 검토 대상이다. pip 전이 의존성은 lock하지 않았다.

## 나중에 실행할 빌드 / import 명령

아래 명령은 저장소 루트에서 사용자가 실행할 예시다. 이번 작업에서는 실행하지 않았다.

```sh
docker build -f docker/iceberg-rest/Dockerfile -t finance-platform/iceberg-rest:1.11.0-pg42.7.8 .
docker build -f docker/spark/Dockerfile -t finance-platform/spark:4.1.2-iceberg1.11.0 .
k3d image import finance-platform/iceberg-rest:1.11.0-pg42.7.8 --cluster dev
k3d image import finance-platform/spark:4.1.2-iceberg1.11.0 --cluster dev
```

렌더링 시 `__ICEBERG_REST_IMAGE__`, `__SPARK_IMAGE__`를 실제 사용자 이미지명으로 대체한다. ARM 노드에서는 해당 아키텍처로 빌드한다. 업무 pipeline 코드는 포함하지 않는다.

## 연결 및 Secret 계약

모두 `finance-platform`. Catalog `iceberg-rest:8181`, PostgreSQL `postgres:5432/iceberg_catalog`, 사용자 `iceberg_user`, Secret `postgres-credentials/iceberg-password`. JDBC catalog는 Iceberg catalog 테이블을 초기화할 수 있는 DB 권한이 필요하다.

Garage `http://garage.finance-platform.svc.cluster.local:3900`, region `garage`, path-style, warehouse `s3://warehouse/`. Catalog와 Spark는 AWS SDK 기본 credential provider가 읽는 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`에 `garage-credentials/s3-access-key-id` / `s3-secret-access-key`를 직접 주입한다. 키는 spark-defaults, 이미지, ConfigMap에 넣지 않는다.

Jupyter는 기본 replicas=0의 필요 시 활성화하는 별도 Deployment로 `jupyter-auth/token`의 비어 있지 않은 인증 토큰이 필요하다. 이 Secret은 이번 작업에서 생성하지 않았다. ClusterIP `jupyter:8888`만 사용하며 나중에 로컬 port-forward로 접근한다. 노트북은 `jupyter-workspace` local-path PVC에 보관한다. 삭제하지 않는다. Spark는 각 프로세스의 `local[2]`로 실행되며 공유 Spark master/worker나 Kubernetes executor를 만들지 않는다. Spark UI는 비활성화했다. `configs/spark/spark-defaults.conf`와 ConfigMap의 내용을 함께 유지한다.

## 제한과 후속 실행 검증

REST 서버는 Apache의 **테스트 fixture**이며 운영용 서버가 아니다. 인증·권한 분리·TLS·고가용성 제공을 전제하지 않는다. 신뢰할 수 있는 개발 클러스터 내부 전용이며 외부로 노출하지 않는다. 해당 fixture의 INFO 로그는 전체 catalog 속성(암호 포함)을 기록하므로 서버 클래스 로거를 OFF로 고정했다. 이를 해제하지 않는다. 자격증명 전달은 AWS 환경변수로 처리하며 클라이언트에 credential vending하지 않는다.

정적 확인은 파일 구문·서비스/Secret/이미지 계약만 검증한다. 이미지 빌드 자체, SHA 파일 제공 여부, Gradle fixture 패키징, 아키텍처, JDBC 테이블 생성, Garage 서명/파일 I/O, Jupyter 인증 및 notebook PySpark kernel, 알려진 1.11.0 문제는 실행으로 확인하지 않았다. 후속 승인된 검증에서 별도 시험 namespace/table에 namespace 생성 → write/read → catalog 재시작 후 재조회하고 Jupyter 무토큰 접근 차단도 확인한다. 기존 데이터를 삭제하거나 PVC를 재생성하지 않는다.
