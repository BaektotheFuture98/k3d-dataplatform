# Airflow 파일 계약

2026-10-18 기반 서비스 전용 이미지를 빌드·반입·설치했다. API/scheduler/dag-processor Ready, FAB 로그인·인증된 API 및 DAG 0개를 확인했다. 업무 DAG와 Job 실행은 제외했다. [실행 검증](../runtime/VALIDATION.md)을 참조한다. 공식 Helm chart **1.18.0**, Airflow **3.0.2**, `apache-airflow-providers-cncf-kubernetes==10.24.0`을 고정한다. Provider의 최소 Airflow 요구는 2.11.0이므로 3.0.2는 범위에 포함된다. 이미지 dependency resolution/pip check, KJO import와 chart 렌더링은 통과했다. 업무 DAG import/실행은 제외했다.

- [고정 chart values 원본](https://github.com/apache/airflow/blob/helm-chart/1.18.0/chart/values.yaml)
- [chart 1.18.0 parameters](https://airflow.apache.org/docs/helm-chart/1.18.0/parameters-ref.html)
- [provider 10.24.0 requirements](https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/10.24.0/index.html)
- [KubernetesJobOperator import와 인자](https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/10.24.0/_api/airflow/providers/cncf/kubernetes/operators/job/index.html)

`AIRFLOW_IMAGE`는 tag를 포함하는 전체 이미지 참조이며 renderer가 repository/tag로 나눈다.
현재 `docker/airflow/Dockerfile`은 Airflow/provider만 포함하며 업무 DAG/Job template을 복사하지 않는다.
Git sync/PVC 전달도 비활성화했다. 나중에 pipeline을 연결할 때 DAG를 `/opt/airflow/dags/`,
Job template을 `/opt/airflow/job-templates/article-collector.yaml`에 전달하는 절차를 추가해야 한다.
chart values만으로 로컬 파일이 전송되지 않는다.

LocalExecutor는 scheduler 안에서 task를 실행한다. 외부 PostgreSQL은 `postgres:5432`, DB `airflow_meta`, user `airflow_user`. 사전에 외부 Secret `airflow-metadata`의 **connection** 키에 URL-encoded password를 포함한 `postgresql://airflow_user:<encoded-password>@postgres:5432/airflow_meta` 연결 URL을 준비해야 한다. 비밀번호 원천은 `postgres-credentials/airflow-password`이며 Kubernetes가 서로 다른 Secret 키를 자동 조합하지 않는다. 실제 Secret 값이나 생성 명령은 여기에 넣지 않는다.

Chart 1.18.0 설치와 DB migration hook이 성공했다. 차트 기본 테스트 계정 생성은 끈다.
`configs/runtime/provision-airflow-admin.py`로 누락된 Admin을 생성하고 `airflow-admin` Secret에
자격증명을 보관했다. 기존 Secret/사용자는 재사용하며 비밀번호를 회전하거나 출력하지 않는다.
chart가 생성한 Fernet/JWT/API Secret을 유지한다. 운영용 Secret 전환 시 `fernetKeySecretName`,
`jwtSecretName`, `apiSecretKeySecretName`을 검토한다. 로그는 현재 ephemeral이다.

`deploy/k8s/manifests/pipelines/airflow-rbac.yaml`은 scheduler의 `airflow-jobs` SA에 namespace 내 Jobs 생성/조회/삭제/patch, Pods 조회/삭제/patch 및 log 읽기만 허용한다. ClusterRole/Secret 읽기 권한은 없다. KJO는 Job을 생성한 후 완료를 기다린다. `keep_pod`로 완료 로그를 남기고 Job TTL 24시간이 Job/Pod를 정리한다. 취소 시 Foreground 삭제가 종속 Pod를 정리한다. 다른 워크로드 Pod를 이름별로 제한할 수 없는 list 권한 한계가 있으므로 이 namespace는 신뢰 경계다.

나중에 Scheduler에 `airflow-jobs` ServiceAccount/RBAC와 환경변수를 연결해야 한다. 현재 values에는 업무 실행 설정이 없고 pipeline RBAC도 배포하지 않았다. `ARTICLE_COLLECTOR_IMAGE` 환경변수 토큰을 실제 **전체 이미지 참조**로 치환해야 DAG가 실행된다. 미설정은 DAG parsing을 깨뜨리지 않고 task 실행에서 명확하게 실패한다. Airflow task retry=0, Job backoffLimit=1, 30분 deadline으로 재실행을 제한한다. DAG는 최초 paused, `schedule=None`이다. 수동 실행을 먼저 검증한 뒤 사용자가 일정을 명시적으로 정하고 unpause한다. 이미 존재하는 DAG의 pause 상태는 `is_paused_upon_creation`으로 재설정되지 않는다.

Migration 대기 init container는 chart 구현상 각 scheduler/apiServer/dagProcessor의 resources를 상속한다. 별도의 지원되지 않는 waitForMigrations.resources 값을 사용하지 않는다.


이미지 Dockerfile은 `docker/airflow/Dockerfile` 한 곳에 있다. 나중에 repository root context에서 `docker build -f docker/airflow/Dockerfile -t <DockerHub-repository>:<tag> .`로 빌드하는 계약이다. 기반 서비스 전용 이미지 빌드·반입을 완료했다.

인증은 chart 1.18.0 원본의 기본값과 동일한 `config.core.auth_manager=airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager`를 명시한다. Airflow 3.0.2 공식 표준 이미지의 기본 extras에는 `fab`이 포함된다. 이미지 확장 후에도 해당 provider가 유지되어야 한다. SimpleAuthManager의 자동 비밀번호 발급/로그 출력 경로에 의존하지 않는다. `apiServer.defaultUser.enabled`와 `webserver.defaultUser.enabled`를 모두 false로 두어 chart 사용자 생성 Job을 막는다. 배포 전에 운영자가 선택한 안전한 FAB 계정/SSO provisioning 절차를 준비하고, 실제 자격증명을 values/이미지/명령 기록에 넣지 않는다. 현재는 안전한 stdin 기반 provisioning helper로 Admin 계정을 생성했고 실제 로그인을 검증했다.

공식 코드 확인: [Airflow 3.0.2 이미지 Dockerfile](https://github.com/apache/airflow/blob/3.0.2/Dockerfile), [KJO request 구성](https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/10.24.0/_modules/airflow/providers/cncf/kubernetes/operators/job.html), [KPO request 구성](https://airflow.apache.org/docs/apache-airflow-providers-cncf-kubernetes/10.24.0/_modules/airflow/providers/cncf/kubernetes/operators/pod.html). KJO는 Job template을 읽고 KPO의 `build_pod_request_obj`로 만든 Pod spec을 우선순위 높게 reconcile한다. KPO가 container `image=self.image`를 사용하므로 execute 직전 검증한 image가 template의 image를 덮어쓴다. Job controller가 Pod를 생성하므로 scheduler Role에는 pods/create가 필요하지 않다. `get_logs`는 Pod 조회 및 pods/log get 권한을 사용한다.
