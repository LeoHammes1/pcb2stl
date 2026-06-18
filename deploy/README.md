# Deploying pcb2stl

Auto-deploys to a Kubernetes cluster (Traefik ingress + cert-manager) on every push to
`main` via `.github/workflows/release.yml`: **build → GHCR → `kubectl apply` + rolling
update**, gated on the test suite.

## One-time setup

1. **DNS / TLS (Cloudflare).** Add the `pcb2stl.online` zone to Cloudflare. Create an
   `A` record `pcb2stl.online` → your cluster's Traefik ingress IP (`AAAA` too if IPv6).
   Make sure the cert-manager `cloudflare-api-token` secret (namespace `cert-manager`)
   has DNS-edit permission for the `pcb2stl.online` zone — cert-manager then issues the
   TLS certificate via DNS-01 automatically. Check it:
   `kubectl -n production get certificate pcb2stl-tls`. In Cloudflare, set the record to
   **DNS-only** (grey cloud), or **proxied** with SSL mode *Full (strict)* to avoid
   double TLS termination.

2. **GHCR image.** The first push to `main` builds `ghcr.io/<owner>/pcb2stl`. Make the
   package **public** (GitHub → Packages → pcb2stl → Package settings → Change
   visibility → Public) so the cluster pulls it without an image-pull secret.

3. **`KUBE_CONFIG` secret.** Add a repository secret `KUBE_CONFIG` = base64 of a
   kubeconfig (`base64 -w0 kubeconfig.yaml`). Prefer a **namespace-scoped
   ServiceAccount** token with edit rights on `production` only — not cluster-admin.

## Tuning

All limits are env vars in `deploy/k8s.yaml` (`PCB2STL_*`): pool workers, max
concurrent, conversion timeout, complexity caps, allowed CORS origins. Resources and
replicas are sized for a small node — adjust to your budget.

## Manual deploy

```sh
kubectl apply -f deploy/k8s.yaml
# the CI pins the image per commit; for a manual apply, set it first:
kubectl -n production set image deployment/pcb2stl pcb2stl=ghcr.io/<owner>/pcb2stl:latest
```
