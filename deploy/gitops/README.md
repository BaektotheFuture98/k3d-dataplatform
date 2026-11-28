# Jenkins와 Argo CD

`k3d-dev` 클러스터에서 Jenkins 컨트롤러와 Argo CD는 `platform-tools`에 설치한다.
Jenkins 컨트롤러의 Pod 생성 권한은 `ci-builds`에만 부여하며, Kubernetes agent도 그곳에서 실행한다.

`platform-data` AppProject는 `lakehouse`와 `pipelines`만 배포 대상으로 허용한다.
데이터 기반과 Airflow는 Kubernetes와 Helm으로 직접 적용했다. Argo CD 검증 앱은 `platform-data-smoke`다.

| 릴리스 | Helm 저장소 | 차트 버전 |
| --- | --- | --- |
| Argo CD | `https://argoproj.github.io/argo-helm` | `10.18.0` |
| Jenkins | `https://charts.jenkins.io` | `5.13.3` |

저장소 루트에서 실행한다.

```sh
kubectl --context k3d-dev apply -f deploy/k8s/namespace.yaml
helm upgrade --install argocd argo-cd --repo https://argoproj.github.io/argo-helm \
  --version 10.18.0 --kube-context k3d-dev -n platform-tools \
  -f deploy/k8s/helm/argocd/values.yaml --wait --timeout 6m
helm upgrade --install jenkins jenkins --repo https://charts.jenkins.io \
  --version 5.13.3 --kube-context k3d-dev -n platform-tools \
  -f deploy/k8s/helm/jenkins/values.yaml --wait --timeout 8m
kubectl --context k3d-dev apply -f deploy/gitops/projects.yaml
```

## 접속과 검증

UI 점검에는 각 명령을 별도 터미널에서 실행한다.

```sh
kubectl --context k3d-dev -n platform-tools port-forward svc/argocd-server 18443:443
kubectl --context k3d-dev -n platform-tools port-forward svc/jenkins 18081:8080
```

Argo CD는 `https://127.0.0.1:18443`, Jenkins는 `http://127.0.0.1:18081`에서
열린다. 초기 계정 정보는 `argocd-initial-admin-secret`, Jenkins 릴리스의 `jenkins`
Secret을 사용한다. 자격증명은 셸 출력 공유나 Git에 포함하지 않는다.

2026-11-23 Jenkins의 `platform-validation`을 `main`으로 전환하고 빌드 #2에서
Python 단위 테스트 12개와 YAML 정적 검사를 확인했다. 재설치 시에는
[작업 정의](jenkins-validation-job.xml)로 Pipeline을 등록하고 한 번 실행한다.
이후 Jenkinsfile의 SCM polling이 `main`의 변경을 확인한다.

```sh
kubectl --context k3d-dev apply -f deploy/gitops/smoke-application.yaml
kubectl --context k3d-dev -n platform-tools get application platform-data-smoke
kubectl --context k3d-dev -n pipelines get configmap platform-gitops-smoke
```

`platform-data-smoke`는 `main`에서 `pipelines`의 ConfigMap 한 개를 자동 동기화한다.
Application의 소스 경로 `deploy/gitops/dev/smoke`는 Git 경로이며, 배포 위치는 Application의
`spec.destination.namespace`로 지정한다. 이미지 빌드·푸시와 Git 기반 버전 승격에는 레지스트리 및 Git 쓰기
자격증명, 환경별 앱 매니페스트가 필요하다.
