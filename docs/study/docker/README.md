# Docker: 이미지와 k3d 노드 컨테이너

> **설정 참고 자료** — 처음 공부한다면 [전체 목차](../README.md)의 본문을 먼저 읽는다.
> 관련 본문: [2장](../chapters/02-process-container-vm.md) · [3장](../chapters/03-colima-docker.md) · [10장](../chapters/10-images-and-resources.md). 아래의 실행 상태·검증 결과는 기존 작성 당시의 기록이며,
> 2026-11-14 재구성 과정에서 클러스터를 새로 조회한 결과가 아니다.

## 학습 목표

이미지 빌드, 컨테이너 실행, Kubernetes에 이미지 전달하는 과정을 구분한다.

## 이 환경에서 Docker의 두 역할

첫째, `k3d-dev-server-0` 같은 Kubernetes 노드 자체를 컨테이너로 실행한다.
둘째, 저장소의 Dockerfile로 Airflow·Spark·Iceberg 등의 이미지를 빌드한다.
애플리케이션 Pod 안의 컨테이너를 실제 관리하는 것은 K3s 노드 내부의 containerd다.
따라서 Mac의 `docker images`에 보이는 이미지가 노드에 자동으로 존재한다고
가정하면 안 된다. 로컬 이미지는 `k3d image import`로 전달한다.

## 현재 Airflow 이미지 계약

Dockerfile은 `docker/airflow/Dockerfile`이다. Airflow 3.0.2와 Kubernetes provider
10.24.0을 포함하며 업무 DAG는 포함하지 않는다. DAG 코드를 바꾸는 작업과 Airflow
Python 라이브러리를 바꾸는 작업은 배포 방식이 다르다.

```sh
# 변경 예시: 이미지를 새로 빌드하고 dev 노드에 반입한다.
docker build --platform linux/arm64 -f docker/airflow/Dockerfile \
  -t finance-platform/airflow:study-v1 .
k3d image import finance-platform/airflow:study-v1 --cluster dev
```

이 두 명령만으로 Deployment의 이미지가 바뀌지는 않는다. 새 태그를 Helm values에
반영하고 upgrade하는 단계가 추가로 필요하다. `IfNotPresent`와 동일 태그 재사용을
섞으면 오래된 이미지로 실행될 수 있으므로 새 내용에는 새 태그를 붙인다.

## 조회 실습

```sh
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker images finance-platform/airflow
kubectl --context k3d-dev -n finance-platform get deployment airflow-scheduler \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

컨테이너 전체 `inspect` 출력은 환경변수 등 민감한 내용을 포함할 수 있다.
학습 기록에는 필요한 필드만 선택한다. 이미지에도 `.env`, 개인 키, 인증 토큰을
복사하지 않는다.

## 확인 문제

1. 이미지를 빌드했는데 Pod가 예전 코드로 실행되는 이유 두 가지는?
2. ARM64 노드에 AMD64 전용 이미지를 넣으면 어떤 문제가 생길 수 있는가?

**해설:** 노드에 이미지가 없거나 Deployment의 태그가 이전 값일 수 있다.
아키텍처가 맞지 않으면 이미지 실행 실패나 `exec format error`가 발생할 수 있다.

참고: [Docker 이미지 개념](https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-an-image/).
