# k3d/K3s부터 이해하는 내 데이터 플랫폼

이 교재의 목표는 **설정값을 외우는 대신 앱 하나가 어디서 어떻게 실행되는지
설명하는 것**이다. Kubernetes를 처음 공부하는 독자를 위해 실행 환경부터 시작한다.
Airflow는 Kubernetes를 배운 뒤 적용해 보는 사례로 다룬다.

## 어떻게 읽을까?

먼저 **1–6장**을 읽는다. Mac, VM, Docker, k3d 노드, K3s, Pod를 구분할 수 있으면
**7–17장**에서 실행·통신·저장·운영을 배운다. 이후 **18–24장**에서 Airflow와
데이터 도구를 연결한다. 낯선 용어는 처음 등장하는 장에서 정의한다.

각 장은 문제 → 원리 → 우리 설정 → 직접 확인 → 해설 순서다.
명령을 모두 실행할 필요는 없다. 결과를 먼저 예상하고 실제 조회와 비교해 보자.

## 전체 목차

### 1부. 실행 환경과 k3d/K3s — 가장 먼저

| 장 | 내용 | 답할 질문 |
| --- | --- | --- |
| 1 | [플랫폼 전체 지도](chapters/01-platform-map.md) | Mac에서 앱까지 어떤 실행 경계가 있는가? |
| 2 | [프로세스·컨테이너·VM](chapters/02-process-container-vm.md) | 실행 주체, 격리, 커널, 파일 수명은 어떻게 다른가? |
| 3 | [Colima와 Docker](chapters/03-colima-docker.md) | Linux VM과 Docker 엔진은 각각 무슨 일을 하는가? |
| 4 | [Kubernetes·K3s·k3d](chapters/04-kubernetes-k3s-k3d.md) | 배포판과 클러스터 생성 도구는 무엇이 다른가? |
| 5 | [k3d 클러스터의 구성](chapters/05-k3d-cluster.md) | server·agent·serverlb와 context는 무엇인가? |
| 6 | [K3s 내부 구조](chapters/06-k3s-internals.md) | 제어 평면과 노드 구성 요소는 어떻게 협력하는가? |

**통과 기준:** Docker의 노드 컨테이너와 Kubernetes의 앱 Pod가 왜 다른지,
Kubernetes API server와 Airflow API server가 무엇이 다른지 설명한다.

### 2부. Kubernetes가 앱을 실행하는 과정

| 장 | 내용 | 답할 질문 |
| --- | --- | --- |
| 7 | [선언에서 Pod 실행까지](chapters/07-declaration-to-pod.md) | apply 이후 누가 Pod를 만들고 실행하는가? |
| 8 | [Pod의 수명](chapters/08-pod-lifecycle.md) | 컨테이너 재시작과 Pod 교체는 어떻게 다른가? |
| 9 | [워크로드 컨트롤러](chapters/09-workload-controllers.md) | Deployment·StatefulSet·Job을 왜 구분하는가? |
| 10 | [이미지와 자원](chapters/10-images-and-resources.md) | 이미지와 CPU·메모리가 실행에 어떻게 관여하는가? |

**통과 기준:** Pod가 없어졌을 때 누가 다시 만드는지, Pending이면 무엇을 볼지 설명한다.

### 3부. 네트워크·저장소·권한

| 장 | 내용 | 답할 질문 |
| --- | --- | --- |
| 11 | [네트워크 경계](chapters/11-network-boundaries.md) | Mac·VM·노드·Pod의 localhost는 같은가? |
| 12 | [Service·DNS·Ingress](chapters/12-services-dns-ingress.md) | 서비스 이름과 웹 주소는 어떻게 Pod로 연결되는가? |
| 13 | [볼륨·PV·PVC](chapters/13-storage.md) | 파일은 어디에 있고 어떤 장애까지 남는가? |
| 14 | [설정·신원·권한](chapters/14-configuration-and-access.md) | 설정값과 인증정보, 실행 신원과 권한은 어떻게 다른가? |

**통과 기준:** Pod IP가 바뀌어도 접속되는 이유와 Pod 교체 뒤 파일이 남는 조건을 설명한다.

### 4부. 클러스터 읽기와 운영

| 장 | 내용 | 답할 질문 |
| --- | --- | --- |
| 15 | [상태 관찰과 장애 진단](chapters/15-observing-and-debugging.md) | 출력·이벤트·로그를 어떤 순서로 읽는가? |
| 16 | [Helm과 설정 적용](chapters/16-helm-and-changes.md) | 파일 수정과 실행 설정 변경 사이에 무엇이 있는가? |
| 17 | [장애와 복구](chapters/17-failure-and-recovery.md) | Pod·노드·데이터 장애는 복구 방법이 어떻게 다른가? |

**통과 기준:** 장애 계층을 좁혀 보고, 재시작과 데이터 복원을 구분한다.

### 5부. 배운 구조로 Airflow 이해하기

| 장 | 내용 | 답할 질문 |
| --- | --- | --- |
| 18 | [DAG·Task·실행 기록](chapters/18-airflow-concepts.md) | 작업 정의와 한 번의 실행은 어떻게 다른가? |
| 19 | [두 작업을 연결하는 첫 DAG](chapters/19-first-dag.md) | 의존성과 성공·실패를 코드와 화면에서 어떻게 읽는가? |
| 20 | [Kubernetes 위의 Airflow](chapters/20-airflow-on-kubernetes.md) | 태스크 하나가 worker Pod가 되기까지 누가 관여하는가? |
| 21 | [DAG 배포와 실행 운영](chapters/21-airflow-operations.md) | DAG·로그·동시성·대기를 어떻게 관리하는가? |

**통과 기준:** 두 scheduler의 역할과, 성공 worker 삭제 후 실행 기록·로그 위치를 설명한다.

### 6부. 데이터 플랫폼으로 확장하기

| 장 | 내용 | 답할 질문 |
| --- | --- | --- |
| 22 | [데이터 저장 계층](chapters/22-data-storage.md) | PostgreSQL·Garage·Iceberg는 각각 무엇을 저장하는가? |
| 23 | [데이터 처리 도구](chapters/23-data-processing.md) | Jupyter·Spark·Neo4j는 어떻게 연결되는가? |
| 24 | [전체 경로 복습](chapters/24-end-to-end.md) | 요청 하나와 데이터 작업 하나를 끝까지 설명하는가? |

## 실습 전에 읽기

- 명령은 프로젝트 루트의 **Mac 터미널**에서 실행한다. `exec`가 있으면 지정한
  컨테이너 안에서 뒤쪽 명령을 실행한다. 출력 예시는 실제 관측 결과와 구분한다.
- `--context k3d-dev`는 대상 클러스터 연결, `-n finance-platform`은 namespace다.
  Docker 접근이나 조회 권한이 없으면 설명과 예시 출력을 먼저 읽는다.
- `port-forward`는 임시 연결이다. 터미널을 유지하고 끝낼 때 `Ctrl+C`로 종료한다.
- 상태를 바꾸는 실습은 별도 표시한다. 문서 작성 중 배포·재시작·DAG 실행은 하지 않았다.

## 원리·선언·관측 구분

| 표시 | 의미 |
| --- | --- |
| 일반 원리 | 동작 설명. 기본값은 설치 옵션과 버전에 따라 달라질 수 있다. |
| 저장소 선언 | 현재 로컬 파일을 읽은 값. 실행 중인 값과 항상 같지는 않다. |
| 과거 관측 | 기존 문서가 2026-11-13 등에 확인한 기록. 현재 상태를 보장하지 않는다. |
| 예시 | 개념 설명용 코드·출력. 이 문서 작성 중 실행한 결과가 아니다. |

이 교재는 **2026-11-14**에 재구성했다. 클러스터를 새로 조회한 검증 보고서는 아니다.
현재 K3s datastore 종류와 시스템 Pod 전체 상태는 여기서 새로 확인하지 않았다.
과거 기록상 Airflow는 KubernetesExecutor이며 Helm 기록에는 이전 설정이 남아 있었다.
재배포 시에는 [16장](chapters/16-helm-and-changes.md)의 대조 절차를 따른다.
일부 executor 리소스·전환 기록·검증 DAG는 아직 게시되지 않은 로컬 파일이다.
해당 자료는 클릭 링크 대신 프로젝트 루트 기준 경로로 표시했다. GitHub 사본만
읽는 경우 그 파일이 없을 수 있으며, 본문의 개념 설명과 학습용 DAG로 먼저 공부할 수 있다.

## 기존 도구별 문서: 설정 참고 자료

아래 자료는 세부 설정과 과거 검증 기록을 찾을 때 사용한다. 처음 읽는 순서는 위 목차다.

- 기반: [Colima](colima/README.md), [Docker](docker/README.md), [k3d](k3d/README.md)
- Kubernetes: [리소스](kubernetes/README.md), [네트워크](kubernetes/02-networking.md),
  [저장소·권한](kubernetes/03-storage-and-security.md), [장애 진단](kubernetes/04-troubleshooting.md)
- Airflow: [구조](airflow/README.md), [설정](airflow/02-configuration.md),
  [executor](airflow/03-kubernetes-executor.md), [검증 DAG](airflow/04-dags-and-practice.md),
  [triggerer](airflow/05-triggerer.md), [운영](airflow/06-operations.md)
- 접속: [Traefik](traefik/README.md), [Tailscale](tailscale/README.md), [Headlamp](headlamp/README.md)
- 데이터: [PostgreSQL](postgresql/README.md), [Garage](garage/README.md), [Iceberg](iceberg/README.md),
  [Jupyter](jupyter/README.md), [Spark](spark/README.md), [Neo4j](neo4j/README.md)

시작: **[1장 — 플랫폼 전체 지도](chapters/01-platform-map.md)**.
