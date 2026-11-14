# 3장. Colima와 Docker의 역할

## 왜 필요한가

Mac에 `docker` 명령이 있어도 Linux 컨테이너가 Mac 커널에서 직접 실행되는 것은
아니다. **명령을 보내는 프로그램**과 **실행을 관리하는 프로그램**을 구분하자.

## 어떻게 동작하는가

Docker CLI는 클라이언트다. Docker 엔진은 요청을 받아 이미지·컨테이너 등을 관리하는
서비스다. 둘은 다른 컴퓨터에 있을 수도 있다. 여기서는 Colima가 Linux VM과
그 안의 Docker 실행 환경을 관리한다.

```text
Mac의 docker CLI
   → Docker context의 연결 주소
      → Colima VM의 Docker 엔진
         → k3d 노드 컨테이너
```

Docker **context**는 CLI가 어느 엔진에 연결할지 정한다. Kubernetes context는
`kubectl`의 클러스터·사용자·기본 namespace를 정한다. 이름이 같아도 별도 설정이다.
Docker context를 바꾼다고 kubectl context가 바뀌지 않는다.

Docker는 여기서 앱 이미지를 빌드하고, k3d가 요청한 노드 컨테이너를 실행한다.
노드 안에서 앱을 실행하는 containerd는 별도다. 그래서 Docker 이미지 저장소와
K3s 노드의 이미지 저장소를 같은 것으로 생각하면 안 된다.

VM에 제공한 CPU·메모리는 그 안의 노드와 앱들이 공유한다. Pod memory limit은
특정 컨테이너의 한도다. VM에 여유가 있어도 컨테이너가 자기 한도를 넘으면 종료될 수 있다.

## 우리 프로젝트에서는

기존 기록의 Colima 프로필은 `default`, 아키텍처는 `aarch64`(ARM64), 자원은
CPU 2개·메모리 24GiB·디스크 100GiB다. 이번 집필에서 새로 조회한 값은 아니다.
다음 명령으로 현재 값을 읽고 비교한다. 새 VM 생성이나 자원 변경은 하지 않아도 된다.

## 직접 확인하기

```sh
colima list
colima status
docker context show
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

| 명령 | 확인할 것 | 해석 |
| --- | --- | --- |
| colima list | 프로필·상태·자원 | VM이 있고 실행 중인가? |
| colima status | 프로필 상세 | runtime과 VM 상태는 무엇인가? |
| docker context show | 엔진 연결 이름 | 의도한 Docker 엔진인가? |
| docker ps | 실행 중인 컨테이너 | k3d 노드가 실행 중인가? |

예를 들어 VM은 Running인데 Docker 접속 오류가 나면 엔진 연결부터 본다.
Docker는 정상인데 앱 화면만 실패하면 네트워크·앱까지 범위를 좁혀야 한다.
한 명령의 성공이 전체 플랫폼 성공을 뜻하지 않는다.

## 이해 확인

1. Docker CLI 명령이 끝나면 실행 중인 컨테이너도 모두 종료되는가?
2. VM 메모리를 늘리면 Airflow 동시 실행 수나 Pod limit도 자동으로 바뀌는가?

**해설:** 클라이언트와 엔진의 수명은 별개다. 상위 자원 용량과 앱의 동시성,
개별 컨테이너 한도도 별도로 설정한다.

더 읽기: [Colima](https://github.com/abiosoft/colima),
[Docker context](https://docs.docker.com/engine/manage-resources/contexts/).

---

[전체 목차](../README.md) · [이전: 2장. 프로세스·컨테이너·가상 머신](02-process-container-vm.md) · [다음: 4장. Kubernetes·K3s·k3d는 무엇이 다른가](04-kubernetes-k3s-k3d.md)
