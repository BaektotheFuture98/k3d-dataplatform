# Colima: Mac 안의 Linux 실행 환경

## 학습 목표

Colima, Docker, Kubernetes를 같은 프로그램으로 생각하지 않고 각 층의 책임을 구분한다.

## 개념과 현재 구성

Colima는 Mac에서 Linux VM과 컨테이너 실행 환경을 관리한다.
이 프로젝트에서는 Colima의 Docker runtime 위에 k3d 노드 컨테이너를 실행한다.
실제 조회 값은 profile `default`, `Running`, `aarch64`, CPU 2개, 메모리 24GiB,
디스크 100GiB다. Kubernetes 노드의 allocatable 메모리가 24GiB보다 작은 것은
VM·운영체제·Kubernetes 등이 자원을 사용하기 때문이다.

```text
Mac → Colima Linux VM → Docker → k3d 노드 → K3s/containerd → 앱 Pod
```

## 설정 방법

조회는 `colima list`, 상세 정보는 `colima status`로 확인한다.
새 환경의 VM 자원 지정 예시는 아래와 같다. 기존 환경에 무작정 적용하는 명령은 아니다.

```sh
# 변경 예시: VM 시작/자원 변경은 기존 서비스에 영향을 줄 수 있다.
colima start --cpu 2 --memory 24 --disk 100 --arch aarch64
```

CPU를 늘리면 처리 여유가 생기지만 Airflow의 `parallelism`이나 Pod의 `requests`
값이 자동으로 바뀌지는 않는다. VM 용량과 Kubernetes 스케줄링 설정은 별도다.
앱의 `limits.memory`가 너무 작으면 VM에 여유가 있어도 해당 컨테이너는 OOMKilled가 된다.

## 조회 실습

```sh
colima list
colima status
docker context show
kubectl --context k3d-dev get nodes -o wide
```

네 명령은 각각 VM, VM 상세 상태, Docker 접속 대상, Kubernetes 노드를 본다.
하나가 정상이더라도 나머지가 정상이라는 보장은 없다.

## 확인 문제

1. Mac이 켜져 있는데 Kubernetes가 접속되지 않을 수 있는 이유는?
2. Colima 메모리 24GiB와 Pod 메모리 limit 1Gi 중 어느 값이 컨테이너의 직접 한도인가?

**해설:** VM이나 Docker, k3d가 중지될 수 있다. 컨테이너의 직접 한도는 Pod spec의
컨테이너 memory limit이다. VM 메모리는 모든 워크로드가 공유하는 상위 자원이다.

참고: [Colima 공식 저장소](https://github.com/abiosoft/colima).
