# Bronze→Silver

- [main.py](main.py)의 Iceberg MERGE와 [transformations](transformations)의 정제 로직을 분리해서 검증한다. 기사 ID, 최신 레코드 선택, 체크포인트 호환성은 재처리 결과에 영향을 준다.
- 정제 경계값은 [변환 테스트](tests/test_transformations.py)로 확인한다. 스트림 재시작과 MERGE는 합성 데이터용 오프라인 스모크에서 검증한다.
