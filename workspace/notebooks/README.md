# Article 테이블 구성 노트북

[article_medallion.ipynb](article_medallion.ipynb)는 기존 `data_platform` 프로젝트의
`workspace/notebooks/pipelines/price_medallion/medallion.ipynb`를 기준으로 작성했다.
현재 k3d의 Iceberg REST Catalog와 Garage를 사용한다.

Jupyter에서 열기: <http://jupyter.localhost:8080/lab/tree/notebooks/article_medallion.ipynb>

## 생성한 테이블

| 테이블 | 컬럼 수 | 파티션 | 논리적 처리 단위 |
| --- | --- | --- | --- |
| `lakehouse.bronze.article` | 14 | `days(collected_at)` | 수집 원본 이력, append |
| `lakehouse.silver.article` | 7 | `bucket(32, article_id)`, `days(dt_created_at)` | 기사별 최신 상태 |
| `lakehouse.gold.graph_article` | 10 | `days(ont_analyzed_at)` | 기사·온톨로지 버전별 결과 |
| `lakehouse.ops.ontology_batch_job` | 9 | `days(dt_created_at)` | 비동기 분석 배치 시도 |

네 테이블은 2026-10-18 생성했으며, 신규 생성 직후와 재실행 후 모두 0행을 확인했다.
Iceberg v2, Parquet, Zstd를 사용하며 Silver에는 copy-on-write MERGE와 hash distribution을 지정했다.
논리적 처리 단위는 후속 파이프라인의 계약이며 DB의 PRIMARY KEY 제약은 아니다.

`sql/`의 네 SQL 파일이 생성문이다. 실행한 노트북에는 스키마·행 수 출력이 저장되어 있다.
데이터 파일과 Iceberg 메타데이터 JSON은 Garage의 `s3://warehouse/`에,
JDBC Catalog 등록 정보는 PostgreSQL에 저장된다.

## 실행

클러스터에는 `/workspace/notebooks/`의 Jupyter PVC에 노트북과 SQL을 저장했다.
노트북을 열고 위에서 아래로 실행한다. Spark와 인증 정보는 기존 Pod 설정을 사용한다.
노트북에 Secret 값을 직접 입력하지 않는다. 마지막 셀은 Spark를 종료해 자원을 반환한다.

저장소의 파일을 새 Jupyter 환경에 업로드할 때는 `sql/`도 함께 전달해야 한다.
다음은 대상 파일을 검토한 뒤 사용하는 업로드 예시이며 기존 동명 파일을 덮어쓴다.

```sh
tar -C workspace -cf - notebooks | kubectl --context k3d-dev -n finance-platform exec -i deployment/jupyter -- tar -C /workspace -xf -
```

Pod 안에서 노트북을 실행하는 예시:

```sh
kubectl --context k3d-dev -n finance-platform exec deployment/jupyter -- \
  python3 -m jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=180 /workspace/notebooks/article_medallion.ipynb
```

실제 생성·재실행 검증은 `nbformat`과 `nbclient.NotebookClient`로 새 커널에서 수행했다.
전체 9개 코드 셀이 두 번 모두 성공했고 기존 테이블의 재생성·데이터 변경은 없었다.
브라우저 화면 검수와 업무 파이프라인 실행은 수행하지 않았다.

## 원본과의 차이

- Bronze의 `ar_published_at TIMESTAMP`를 최초 CREATE에 포함했다. 재실행 시 중복 ADD COLUMN 오류를 피한다.
- 원본의 언어 일괄 변경 UPDATE는 포함하지 않는다.
- 기존 테이블은 컬럼 순서·타입·필수값·파티션·속성을 먼저 검사하고 다르면 중단한다. 자동 마이그레이션이나 삭제는 하지 않는다.
- `ops.article_pipeline_state`는 원본에 생성 정의와 실제 생산자가 없어 제외했다. 노트북에서는 존재 여부만 확인한다.
- 기사 수집·변환·LLM 분석·Neo4j 적재는 실행하지 않는다.
