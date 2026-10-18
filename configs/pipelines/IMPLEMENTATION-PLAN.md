# Article pipeline implementation plan

User-approved scope: import Bronze→Silver and Silver→Gold from the original
data_platform project, with Kubernetes-managed runtime configuration. Execution
method: implement in the current checkout while preserving the earlier pending changes.
No real Gemini calls or production activation in this task.

## Constraints

- Spark 4.1.2 / Iceberg 1.11.0 / Hadoop 3.4.2 S3A base image; separate Python 3.13 environment.
- Copy only Python source and ontology TTL assets. Never copy `.env` or credentials.
- Existing article schema, identity and version semantics remain compatible.
- Application ConfigMaps supply table identifiers, polling/batch limits and isolated checkpoints.
- Spark ConfigMap supplies shared runtime settings. Garage and Gemini credentials use named Secret keys.
- Both Deployments remain at replicas=0. Integration probes use isolated tables and checkpoint prefixes.

## Tasks

- [x] Import existing source and tests; add failing environment validation tests.
- [x] Add validated settings and explicit repository table parameters; preserve processing semantics.
- [x] Add signal handling and finite/validation execution paths without constructing a remote client in validation mode.
- [x] Pin dependencies and build two runtime images plus an offline test target.
- [x] Add per-pipeline ConfigMaps and named Secret refs; build/import/render/apply dormant Deployments.
- [x] Run original/new tests and isolated Garage/Iceberg integration: Bronze filtering/latest MERGE/restart, Gold async state/result validation/replay with an in-process fake external service.
- [x] Review, clean only owned probe data, and document exact verification plus activation steps.

## Review focus

- Invalid table/URI or missing credentials fail before processing, without leaking values.
- Equal/older Bronze ingestions cannot replace newer Silver; creation time is retained.
- Gold preserves article/ontology pairs; stale remote results and SHACL failures never enter Gold.
- Batch quota/restart/replay reuse durable state instead of silently resubmitting processed articles.
- SIGTERM stops an active query and releases Spark resources; production checkpoints are never used by tests.

## Verification outcome

Network-disabled container: 13 tests and 6 subtests passed. Kubernetes Job
`article-pipeline-offline-mnpv6` completed in 33 seconds with all six behavior PASS
markers, `NO_REAL_GEMINI_CALLS`, and owned-data cleanup. Both actual Deployments
are prepared at zero replicas. Final focused review found no blocking defects.
The initial probe exposed cross-session Iceberg cache staleness; explicit metadata
refresh fixed the probe and guards Gold cross-process reads.
