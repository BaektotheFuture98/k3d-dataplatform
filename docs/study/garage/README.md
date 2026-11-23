# Garage: S3 호환 오브젝트 저장소

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [13장](../chapters/13-storage.md) · [22장](../chapters/22-data-storage.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

2026-11-24 기준 Garage는 현재 미배포 상태다. 아래 저장소 구성과 조회 명령은 이전 `finance-platform` 기준이다.
현재 클러스터 조회 방법은 [루트 README](../../../README.md)를 참고한다.

## 학습 목표

파일 저장소와 관계형 DB, Iceberg catalog의 책임을 구분한다.

## 이전 환경의 역할

이전 환경에서는 Garage **2.4.1**을 StatefulSet `garage`와 Pod `garage-0` 하나로 실행했다.
Iceberg 테이블의 실제 데이터 파일과 메타데이터 JSON을 S3 호환 API로 저장한다.
이전 환경의 warehouse는 `s3://warehouse/`다. 이것은 Mac 로컬 폴더 경로가 아니다.

| 설정 | 현재 선언 |
| --- | --- |
| S3 endpoint | http://garage:3900 |
| region | garage |
| bucket | warehouse |
| replication_factor | 1 |
| consistency_mode | consistent |
| DB engine | lmdb |
| metadata/data directory | /var/lib/garage/meta, /var/lib/garage/data |
| 데이터 PVC | data-garage-0, 10Gi local-path RWO |
| 자원 request / limit | 100m·128Mi / 500m·512Mi |

replication_factor=1의 단일 인스턴스는 복제 고가용성을 제공하지 않는다.
키는 `garage-credentials` Secret에서 전달하고 ConfigMap이나 이미지에 넣지 않는다.

## 설정 변경 방법

원본은 `configs/garage/garage.toml`이다. 이를 변경한 뒤 저장소의
`configs/garage/render-configmaps.rb`로 ConfigMap을 생성하는 계약이다.
renderer의 출력과 manifest 차이를 확인한 다음 해당 서비스 파일만 검증·적용한다.
현재 metadata/data 경로를 바꾸는 것은 단순 HTTP 설정 변경과 달리 데이터
접근에 영향을 줄 수 있으므로 스토리지 경로를 임의로 바꾸지 않는다.

## S3와 실제 AWS의 차이

S3 호환이라고 AWS의 모든 기능과 모든 SDK 설정을 동일하게 지원하는 것은 아니다.
이 환경은 path-style 접근과 region `garage`를 사용한다. Catalog와 Jupyter에는
`AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED`,
`AWS_RESPONSE_CHECKSUM_VALIDATION=WHEN_REQUIRED`를 설정했다.
과거 기본 checksum 처리와 Garage의 서명 검증 사이에 호환성 오류가 있었다.

## 조회 실습

```sh
kubectl --context k3d-dev -n finance-platform get statefulset garage
kubectl --context k3d-dev -n finance-platform get service garage
kubectl --context k3d-dev -n finance-platform get pvc data-garage-0
```

Pod Ready는 버킷 권한과 실제 객체 입출력 검증을 대신하지 않는다.
기존 `configs/garage/s3-check.py`와 검증 기록을 읽으며 익명 차단, 잘못된 키 거부,
multipart와 데이터 보존을 각각 어떤 검사로 확인했는지 찾아본다.

## 확인 문제

1. Iceberg의 Parquet 파일은 PostgreSQL과 Garage 중 어디에 저장되는가?
2. Garage Pod를 두 개 띄우기만 하면 현재 설정이 자동으로 고가용성이 되는가?

**해설:** 현재 실제 파일은 Garage다. 복제·레이아웃·저장소 구성 없이 replica만
늘리는 것으로 분산 저장소가 완성되지 않는다.

참고: [Garage 공식 문서](https://garagehq.deuxfleurs.fr/documentation/).
