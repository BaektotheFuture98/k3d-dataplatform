# JupyterLab: 노트북과 Spark를 사용하는 작업 공간

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [23장](../chapters/23-data-processing.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

## 학습 목표

노트북 파일, 실행 커널 메모리, 외부 테이블 데이터의 수명을 구분한다.

## 현재 구성

Jupyter Deployment 1개 안에서 JupyterLab과 Spark 개발 환경을 제공한다.
기존 검증 기록의 JupyterLab 버전은 4.4.9이며 현재 실행 이미지와 Pod 상태를
대조했다. Pod의 Service는 `jupyter:8888`이다.

| 항목 | 현재 설정 |
| --- | --- |
| ServerApp.ip / port | 0.0.0.0 / 8888 |
| root_dir | /workspace |
| open_browser | false |
| 인증 | jupyter-auth Secret의 token |
| 로그 수준 | WARN, 시작 URL의 토큰 노출 줄이기 |
| 작업 공간 PVC | jupyter-workspace, 2Gi local-path RWO |
| 자원 request / limit | 100m·1Gi / CPU 2·3Gi |

설정 코드는 `docker/spark/jupyter_server_config.py`, 배포는
`deploy/k8s/manifests/spark/jupyter.yaml`이다.
토큰 값이 빈 경우 설정 코드가 실패하도록 작성돼 있다.

## 노트북이 저장돼도 커널 상태는 남지 않는다

`.ipynb` 파일을 PVC에 저장하면 Pod 교체 뒤 파일을 다시 열 수 있다.
하지만 Python 변수, 열린 DB 연결, SparkSession 같은 메모리 상태는 유지되지 않는다.
재현 가능한 노트북은 새 커널에서 위에서 아래로 실행할 수 있어야 한다.

## 접속과 조회 실습

```sh
kubectl --context k3d-dev -n finance-platform get deployment jupyter
kubectl --context k3d-dev -n finance-platform get pvc jupyter-workspace
kubectl --context k3d-dev -n finance-platform port-forward service/jupyter 18888:8888
```

터널을 연 뒤 `http://127.0.0.1:18888`로 접속한다. 토큰은 자신의 안전한 인증
관리 경로에서 확인하고 공개 URL·스크린샷·GitHub 문서에 붙이지 않는다.
Tailnet 접속은 [Tailscale 문서](../tailscale/README.md)의 별도 경로다.

## 현재 노트북 자료

저장소의 `workspace/notebooks/article_medallion.ipynb`와 SQL 파일들이
Article 테이블 구성의 기반이다. 로컬 파일이 Pod에 자동으로 동기화되지는 않는다.
업로드된 파일 위치와 원본 버전을 대조하고, 기존 업무 테이블을 바꾸는 SQL은
학습용 읽기 쿼리와 구분한다.

## 확인 문제

1. Pod가 재시작됐는데 파일은 있고 변수는 없는 이유는?
2. 로컬 `.ipynb`를 고쳤는데 브라우저 노트북에 반영되지 않는 이유는?

**해설:** 파일은 PVC에, 변수는 커널 메모리에 있다. 현재 구성은 로컬 작업
디렉터리 전체를 자동 동기화하지 않는다.

참고: [Jupyter Server 설정](https://jupyter-server.readthedocs.io/en/latest/operators/configuring.html).
