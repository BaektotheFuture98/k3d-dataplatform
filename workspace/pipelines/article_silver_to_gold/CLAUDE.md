# Silver→Gold

- [article_semantic](article_semantic)에 배치 처리와 RDF 변환, [ontology](ontology)에 어휘와 SHACL shapes가 있다. 결과 계약을 바꿀 때 코드·온톨로지·검증 테스트를 함께 검토한다.
- 저장 멱등성의 기준은 `(article_id, ont_version)`이다. Gemini Batch 상태 추적과 재시도 경로는 합성 응답으로 검증한다.
