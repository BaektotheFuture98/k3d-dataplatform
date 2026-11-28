# Jenkins와 Argo CD

`k3d-dev` 클러스터에서 Jenkins는 `jenkins`, Argo CD는 `argocd`에 설치한다.
`dev`, `stage`, `prod`는 애플리케이션 배포 대상이다. Jenkins의 Kubernetes agent는
`jenkins`에서 작업하고, Argo CD는 Git에서 선언을 읽어 각 환경으로 동기화한다.

`platform-data` AppProject는 `lakehouse`와 `pipelines`만 배포 대상으로 허용한다.
데이터 기반과 Airflow의 첫 이전은 Kubernetes와 Helm으로 직접 적용했으며, 현재 Argo CD의
검증 앱은 기존 `platform-dev-smoke`다.

| 릴리스 | Helm 저장소 | 차트 버전 |
| --- | --- | --- |
| Argo CD | `https://argoproj.github.io/argo-helm` | `10.18.0` |
| Jenkins | `https://charts.jenkins.io` | `5.13.3` |

저장소 루트에서 실행한다.

```sh
helm upgrade --install argocd argo-cd --repo https://argoproj.github.io/argo-helm \
  --version 10.18.0 --kube-context k3d-dev -n argocd --create-namespace \
  -f deploy/k8s/helm/argocd/values.yaml --wait --timeout 6m
helm upgrade --install jenkins jenkins --repo https://charts.jenkins.io \
  --version 5.13.3 --kube-context k3d-dev -n jenkins --create-namespace \
  -f deploy/k8s/helm/jenkins/values.yaml --wait --timeout 8m
kubectl --context k3d-dev apply -f deploy/gitops/projects.yaml
```

## 접속과 검증

UI 점검에는 각 명령을 별도 터미널에서 실행한다.

```sh
kubectl --context k3d-dev -n argocd port-forward svc/argocd-server 18443:443
kubectl --context k3d-dev -n jenkins port-forward svc/jenkins 18081:8080
```

Argo CD는 `https://127.0.0.1:18443`, Jenkins는 `http://127.0.0.1:18081`에서
열린다. 초기 계정 정보는 `argocd-initial-admin-secret`, Jenkins 릴리스의 `jenkins`
Secret을 사용한다. 자격증명은 셸 출력 공유나 Git에 포함하지 않는다.

2026-11-23 Jenkins의 `platform-validation`을 `main`으로 전환하고 빌드 #2에서
Python 단위 테스트 12개와 YAML 정적 검사를 확인했다. 재설치 시에는
[작업 정의](jenkins-validation-job.xml)로 Pipeline을 등록하고 한 번 실행한다.
이후 Jenkinsfile의 SCM polling이 `main`의 변경을 확인한다.

```sh
kubectl --context k3d-dev apply -f deploy/gitops/dev/application.yaml
kubectl --context k3d-dev -n argocd get application platform-dev-smoke
kubectl --context k3d-dev -n dev get configmap platform-gitops-smoke
```

`platform-dev-smoke`는 `main`에서 `dev`의 ConfigMap 한 개를 자동 동기화한다.
2026-11-24 조회 시 `Synced / Healthy`였다. `stage`와 `prod`에는
배포 가능 경로만 설정한다. 애플리케이션을 등록할 때는 해당 `AppProject`를 지정하고
수동 동기화로 시작한다. 이미지 빌드·푸시와 Git 기반 버전 승격에는 레지스트리 및 Git 쓰기
자격증명, 환경별 앱 매니페스트가 필요하다.
