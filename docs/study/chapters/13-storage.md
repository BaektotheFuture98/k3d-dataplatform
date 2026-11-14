# 13장. 볼륨·PV·PVC와 실제 데이터 위치

## 왜 필요한가

Pod를 교체해도 DB 파일은 남아야 한다. 하지만 “PVC를 썼다”는 사실만으로 VM이나
디스크 장애에서도 복구된다고 결론 내릴 수 없다. 파일이 실제로 어디에 있는지 따라가자.

## 어떻게 동작하는가

**볼륨**은 Pod에 제공하는 저장 공간이다. `volumeMounts`는 그 공간을 컨테이너의
어느 경로에 연결할지 정한다. **PVC**는 저장소 사용 요청, **PV**는 그 요청에 연결된
실제 저장소를 나타내는 리소스다. **StorageClass**는 저장소를 제공하는 방식이다.
**provisioner**는 필요에 따라 저장소와 PV를 만드는 구성 요소다.

```text
컨테이너 /opt/airflow/logs
 → Pod의 logs 볼륨
 → PVC airflow-executor-logs
 → 연결된 PV
 → local-path가 사용하는 노드 측 실제 디렉터리
 → 그 디렉터리를 보관하는 VM 디스크 또는 별도 마운트
```

정확한 디렉터리와 바깥 마운트는 실제 PV·Docker 설정에 따라 달라진다.
Mac 프로젝트 폴더와 자동 동기화되는 경로라고 가정하지 않는다.

| 저장 방식 | 파일이 남는 범위 |
| --- | --- |
| 컨테이너 쓰기 계층 | 새 컨테이너에서 보존을 기대하지 않음 |
| emptyDir | 같은 Pod 수명 동안 유지, Pod 교체 시 소실 |
| PVC/PV | 해당 객체와 실제 저장소가 유지되고 재연결되면 사용 가능 |

**ReadWriteOnce(RWO)**는 한 노드에서 읽기·쓰기로 마운트하는 접근 모드다.
Pod 한 개만 사용한다는 뜻이 아니다. 단일 노드의 여러 Airflow Pod가 같은 PVC를
공유할 수 있다. 다중 노드로 늘릴 때에는 같은 구성이 그대로 가능한지 다시 검토해야 한다.

local-path는 노드 로컬 저장소다. PVC의 `2Gi` 요청이 실제 디스크 사용을 2Gi로
제한한다고 기대해서는 안 된다. PV reclaim policy가 Delete이면 PVC 삭제가 실제
저장소 삭제로 이어질 수도 있다. 이 실습에서는 어떤 PVC도 삭제하지 않는다.

## 우리 프로젝트에서는

Airflow 저장소 선언(로컬 파일 `deploy/k8s/helm/airflow/executor-resources.yaml`)은
DAG 1Gi·로그 2Gi, local-path/RWO다. [PostgreSQL](../../../deploy/k8s/manifests/postgres/statefulset.yaml)은
volumeClaimTemplates로 데이터 PVC를 요청한다. [Jupyter](../../../deploy/k8s/manifests/spark/jupyter.yaml)의
`/workspace`도 별도 PVC다. 세 종류의 파일은 서로 다른 저장 대상이다.

## 직접 확인하기

```sh
kubectl --context k3d-dev -n finance-platform get pvc
kubectl --context k3d-dev get pv
kubectl --context k3d-dev get storageclass
kubectl --context k3d-dev -n finance-platform describe pvc airflow-executor-logs
```

PVC의 VOLUME 열과 PV의 NAME을 연결한다. PV의 RECLAIM POLICY와 STORAGECLASS를
읽는다. `Bound`는 연결된 상태라는 뜻이며 백업 완료라는 뜻은 아니다.
PV/StorageClass는 namespace 밖의 리소스여서 조회 권한이 별도로 필요할 수 있다.

## 이해 확인

1. Airflow worker 두 개가 같은 노드에서 RWO 로그 PVC를 사용할 수 있는가?
2. PVC가 Bound이면 VM 디스크 삭제 후에도 데이터를 복구할 수 있는가?

**해설:** RWO의 기준은 노드이므로 가능하다. Bound는 저장소 연결 상태일 뿐이다.
실제 디스크 소실에 대비하려면 별도의 백업과 복원 검증이 필요하다.

근거: [PV·PVC](https://kubernetes.io/docs/concepts/storage/persistent-volumes/),
[local-path provisioner](https://github.com/rancher/local-path-provisioner).

---

[전체 목차](../README.md) · [이전: 12장. Service·DNS·Ingress로 요청 따라가기](12-services-dns-ingress.md) · [다음: 14장. 설정·인증정보·실행 신원·권한](14-configuration-and-access.md)
