# Infrastructure Helm preparation

No Helm release or Kubernetes resource was installed by the preparation step.
All releases target `finance-platform`.

## Verified local tools and charts

- CLI: `/private/tmp/finance-platform-tools/helm`, official Helm v3.19.0 darwin-arm64.
  Official SHA256: `31513e1193da4eb4ae042eb5f98ef9aca7890cfa136f4707c8d4f70e2115bef6`.
- Airflow 1.18.0: `/private/tmp/finance-platform-tools/airflow`.
  Archive SHA256 verified against official repository index:
  `8286a11351af1b874a08395e7bfa73f32d9694977e24496b516b4c2561e0a622`.
- Neo4j 5.26.32: `/private/tmp/finance-neo4j5/neo4j`.
- Strimzi 0.51.0: `/private/tmp/finance-platform-tools/strimzi-kafka-operator`.
  Archive SHA256 verified against official repository index:
  `1ec8bbffe5e40d645635ace9c439ac54b39639af243bae6ce5b1f9eabfc07e9b`.

Offline renders succeeded for all three pinned charts. Rendered manifests live
only under the temporary tools directory with restrictive file permissions;
Airflow renders contain chart-generated Secrets and must not be committed or
printed. Neo4j offline rendering needs `--set disableLookups=true`, because the
normal chart verifies the existing Secret through Kubernetes lookup. Keep the
normal lookup enabled during installation. Existing `neo4j-auth` must contain
`NEO4J_AUTH` with the `neo4j/` prefix.

## Resource review

- Neo4j requests and limits: 500m CPU and 2Gi memory, no sidecar/init container.
  This chart explicitly rejects requests below 500m CPU.
- Airflow steady requests: 350m CPU / 1Gi memory across scheduler (150m/512Mi),
  API server (100m/256Mi), DAG processor (100m/256Mi).
  Wait-for-migrations init containers request the same resources as their main
  container, so they do not increase per-pod scheduling requests.
  Migration hook Job adds 100m CPU / 256Mi while running.
- Strimzi operator: 100m CPU / 384Mi memory, no sidecars/init containers.
- Neo4j renders only a ClusterIP Service; no external LoadBalancer.

Airflow uses chart-created ServiceAccounts and renders no RBAC resources.
The scheduler collector image environment variable and custom job-launching
ServiceAccount were removed. LocalExecutor, disabled pod launching, no DAG
mounts, disabled examples and disabled Git sync keep this release infrastructure
only. The separate image build must exclude project DAG files.

## Strimzi cluster-scope approval boundary

`strimzi-cluster-resources.yaml` is a concrete review artifact generated from
the official 0.51.0 chart with `createGlobalResources=true`, aggregate roles
false, watched namespace `finance-platform`, and included CRDs. It contains
10 CRDs, 7 ClusterRoles and 3 ClusterRoleBindings. Explicit approval is required
before applying this file. Its ClusterRoleBindings bind the operator
ServiceAccount in `finance-platform`.

The normal values set `createGlobalResources=false`, `watchAnyNamespace=false`
and `createAggregateRoles=false`. That namespaced render contains only one
ServiceAccount, one ConfigMap, four RoleBindings and one Deployment. It still
requires the reviewed cluster roles and global/delegation bindings to exist.
The namespaced chart does not own the separately applied cluster resources.
