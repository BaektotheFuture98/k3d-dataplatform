# 2장. 프로세스·컨테이너·가상 머신

## 왜 필요한가

“앱이 죽었다”는 말은 여러 상황을 가리킨다. Python 프로세스 종료, 컨테이너
재시작, VM 중지는 확인할 대상과 복구 범위가 다르다.

## 어떻게 동작하는가

**프로세스**는 실행 중인 프로그램이다. Python 파일은 코드이고, 그 파일을 읽어
실행하는 `python`은 프로세스다. 운영체제가 CPU 시간과 메모리·파일 접근을 관리한다.

**커널**은 운영체제의 핵심이다. **컨테이너**는 별도 커널을 부팅하지 않고 Linux
커널을 공유한다. namespace로 프로세스·네트워크·파일 경로 등이 보이는 범위를 나누고,
cgroup으로 자원 사용을 관리한다. 격리된 환경에서 실행되는 프로세스들의 묶음이다.

**가상 머신(VM)**은 가상 하드웨어 위에서 게스트 운영체제와 커널을 실행한다.
이 프로젝트의 Linux 컨테이너는 Mac에서 Colima의 Linux VM을 이용한다.

| 비교 | 프로세스 | 컨테이너 | VM |
| --- | --- | --- | --- |
| 핵심 | 프로그램 실행 | 격리된 프로세스 실행 | 게스트 운영체제 실행 |
| 커널 | 실행되는 OS의 커널 | Linux 호스트 커널 공유 | 게스트 커널 사용 |
| 파일 경로 | 프로세스의 파일 보기 | 이미지와 마운트로 구성 | 게스트 디스크 |
| 예 | Python 태스크 | worker의 base 컨테이너 | Colima Linux VM |

**이미지**는 컨테이너를 만들 때 사용하는 파일시스템과 실행 설정의 묶음이다.
이미지는 실행 중인 프로그램이 아니다. 같은 이미지로 여러 컨테이너를 만들 수 있다.

프로세스 메모리의 변수는 종료하면 사라진다. 컨테이너의 쓰기 계층은 새 컨테이너에서
보존을 기대할 수 없다. 외부 저장소를 **볼륨으로 마운트**하면 파일의 수명을 실행과
분리할 수 있다. 볼륨의 종류와 보존 범위는 13장에서 다룬다.

## 우리 프로젝트에서는

[Airflow Dockerfile](../../../docker/airflow/Dockerfile)은 Airflow와 라이브러리를
설치하지만 업무 DAG는 포함하지 않는다. [Jupyter 선언](../../../deploy/k8s/manifests/spark/jupyter.yaml)은
이미지와 `/workspace` 볼륨을 별도로 지정한다. 실행 도구와 작업 파일의 출처가 다르다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform get deployment jupyter \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl --context k3d-dev -n finance-platform get deployment jupyter \
  -o jsonpath='{.spec.template.spec.containers[0].volumeMounts}{"\n"}'
```

`deployment jupyter`는 앱의 실행 선언이다. `-o jsonpath=...`는 전체 응답에서
필요한 필드만 고른다. 첫 결과는 이미지 참조이고, 두 번째는 연결할 볼륨 경로 목록이다.
예를 들어 `/etc/spark`와 `/workspace`가 보이면 이미지와는 별도로 연결된 경로다.
정확한 출력은 현재 배포에 따라 달라진다.

## 이해 확인

1. 이미지를 빌드하면 Python 프로그램도 바로 실행되는가?
2. 노트북 파일은 남았는데 변수 `df`가 없을 수 있는가?

**해설:** 빌드는 실행에 사용할 이미지를 만든다. 컨테이너 실행은 별도다.
파일과 메모리는 수명이 다르므로 새 프로세스에서는 변수를 다시 계산해야 한다.

더 읽기: [Docker 컨테이너 개념](https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-container/).

---

[전체 목차](../README.md) · [이전: 1장. 내 컴퓨터 안의 플랫폼 전체 지도](01-platform-map.md) · [다음: 3장. Colima와 Docker의 역할](03-colima-docker.md)
