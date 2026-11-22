# Headlamp password login

Headlamp runs in the `dev` namespace of `k3d-dev`. The shared identity has
cluster-wide `view` access and the `edit` role in `dev`.

The requested shared login uses the `admin` username and the user-supplied
password, stored only as a local BCrypt hash. Tailscale HTTPS remains the
external entry point. Traefik BasicAuth checks every request, including API and
WebSocket requests, and strips its Authorization header before proxying.
Headlamp uses the existing `headlamp-user` ServiceAccount with its current
RBAC permissions, using Kubernetes' automatically rotated projected token.
All password-authenticated visitors therefore share that Kubernetes identity.
The internal Headlamp service also uses that identity without a separate login;
keep access through the authenticated ingress.

## Approach and application plan

An ingress password check alone would still require the old token login.
OIDC with a local password provider would require an additional identity service
and API server configuration. The selected configuration combines Traefik
BasicAuth with Headlamp's `unsafeUseServiceAccountToken` option, supported in
the pinned 0.46.0 chart and image.

1. Prepare a BCrypt password hash in an ignored, mode-600 local Secret file.
2. Apply the existing RBAC and the password Secret and middleware first.
3. Upgrade Headlamp 0.46.0 with the password-login settings in values.yaml.
4. Verify no/wrong credentials return 401; correct credentials return 200 for
   both the UI and `/clusters/k3d-dev/api/v1/namespaces/{namespace}/pods`
   for `dev`, `stage`, and `prod`.
5. Verify API access still works after token rotation, and test browser login.

## Apply

From the repository root, with Helm and access to the `k3d-dev` API:

```sh
kubectl --context k3d-dev -n dev apply -f deploy/k8s/helm/headlamp/access.yaml
kubectl --context k3d-dev -n dev apply -f configs/headlamp/basic-auth-secret.local.json
kubectl --context k3d-dev -n dev apply -f deploy/k8s/helm/headlamp/basic-auth.yaml
helm upgrade --install headlamp headlamp \
  --repo https://kubernetes-sigs.github.io/headlamp/ --version 0.46.0 \
  --kube-context k3d-dev --namespace dev \
  -f deploy/k8s/helm/headlamp/values.yaml \
  --atomic --wait --timeout 3m
```

Keep the values file on subsequent upgrades. The Secret's BCrypt hash is
stored only in `basic-auth-secret.local.json`, excluded by the existing
`**/*secret.local*` ignore rule. No non-expiring Kubernetes token is created.

## Rollback

To restore manual token login, upgrade the same chart and values file with
`--set config.unsafeUseServiceAccountToken=false --set serviceAccount.create=true
--set serviceAccount.name=headlamp --set ingress.annotations=null`.
Only after Headlamp has rolled out with token login, remove the middleware and
password Secret if no longer needed.

## References

- https://headlamp.dev/docs/latest/installation/in-cluster/basic-auth/
- https://github.com/kubernetes-sigs/headlamp/blob/v0.46.0/charts/headlamp/values.yaml
- https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/basicauth/
