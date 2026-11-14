# 1장. 내 컴퓨터 안의 플랫폼 전체 지도

## 왜 필요한가

“Airflow가 내 Mac에서 실행된다”는 설명만으로는 파일과 주소, 장애 범위를 알 수 없다.
Mac의 Python에서 실행되는지, Linux VM의 컨테이너에서 실행되는지부터 구분해야 한다.

## 어떻게 동작하는가

다음 상자는 **포함 관계**다. 네트워크 요청의 전달 순서를 나타낸 그림이 아니다.

```text
Mac
└─ Colima가 관리하는 Linux 가상 머신
   └─ Docker 엔진
      └─ k3d가 만든 K3s 노드 컨테이너
         ├─ K3s: Kubernetes를 동작시키는 구성 요소
         └─ containerd: 앱 컨테이너 실행을 관리
            ├─ Airflow API server Pod
            ├─ Airflow scheduler Pod
            ├─ PostgreSQL Pod
            └─ 그 밖의 앱 Pod
```

**클러스터**는 함께 관리하는 노드들의 집합이다. **노드**는 Kubernetes가 앱을
배치하는 실행 환경이다. 이 프로젝트에서는 Docker 컨테이너를 노드로 사용한다.
**Pod**는 Kubernetes가 하나 이상의 앱 컨테이너를 함께 배치하는 단위다.

VM은 별도의 운영체제와 커널을 실행한다. 컨테이너는 Linux 커널을 공유하며 실행
환경을 격리한다. 노드 컨테이너 안에서 앱 컨테이너를 실행한다고 앱마다 VM이 생기지는 않는다.

이제 **관리 요청**과 **앱 요청**을 구분한다.

```text
kubectl get pods → Kubernetes API server → Pod 목록 응답
브라우저        → Airflow API server    → Airflow 화면 응답
```

두 API server는 다른 프로그램이다. `kubectl`은 Kubernetes 리소스를 조회하고
변경하는 클라이언트다. Airflow 웹 화면에 접속하는 브라우저와 역할이 다르다.

## 우리 프로젝트에서는

기존 관측 기록에는 클러스터 `dev`, context `k3d-dev`, 단일 노드
`k3d-dev-server-0`가 나온다. `finance-platform`은 앱을 묶는 **namespace**다.
namespace는 VM이나 노드를 하나 더 만드는 기능이 아니다.

[deploy/k8s](../../../deploy/k8s/)의 YAML은 실행 중인 앱 자체가 아니라,
Kubernetes에 전달할 선언이다. 파일을 수정한 것과 실행 상태를 변경한 것은 다르다.

## 직접 확인하기

Mac 터미널에서 다음 두 조회 명령을 비교한다.

```sh
docker ps --format 'table {{.Names}}\t{{.Image}}'
kubectl --context k3d-dev -n finance-platform get pods
```

첫 명령은 선택된 Docker 엔진의 컨테이너를 보여 준다. `--format`은 이름·이미지
열만 고른다. k3d 노드나 serverlb가 보일 수 있다. 두 번째는 Kubernetes의 앱 Pod
목록이다. `--context`는 클러스터 연결 설정, `-n`은 namespace를 선택한다.

**서로 같은 목록이 나오지 않는 것**이 예상 결과다. 앱 컨테이너는 노드 안의
containerd가 관리한다. Docker 접속 실패와 Kubernetes 접속 실패도 구분해야 한다.

## 이해 확인

1. Airflow Pod 교체와 Colima VM 중지는 왜 영향 범위가 다른가?
2. namespace를 만들면 Linux VM도 생기는가?

**해설:** Pod 교체는 특정 실행 단위에, VM 중지는 그 위의 노드와 앱 전체에
영향을 준다. namespace는 클러스터 리소스의 이름·관리 범위를 나누는 개념이다.

---

[전체 목차](../README.md) · [다음: 2장. 프로세스·컨테이너·가상 머신](02-process-container-vm.md)
