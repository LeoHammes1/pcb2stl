# Deploying pcb2stl

On every push to `main`, `.github/workflows/release.yml` runs the test suite and then
**builds a multi-arch (`linux/amd64` + `linux/arm64`) image and pushes it to GHCR**
(`ghcr.io/<owner>/pcb2stl:latest` and `:<sha>`), gated on the tests. It does **not**
deploy — the cluster's Kubernetes API is not reachable from GitHub Actions.

The **live deployment** is managed in the cluster repo (a homelab k3s cluster):
`apps/pcb2stl.yaml`, applied with the cluster's own tooling. pcb2stl runs in the
`production` namespace behind Traefik + cert-manager, on `https://pcb2stl.online`.
`deploy/k8s.yaml` in this repo is a standalone reference of the same manifest for
deploying elsewhere.

## One-time setup

1. **GHCR image — make it public.** The first push to `main` builds
   `ghcr.io/<owner>/pcb2stl`. Make the package **public** (GitHub → Packages → pcb2stl
   → Package settings → Change visibility → Public) so the cluster pulls it without an
   image-pull secret. The image is multi-arch, so it runs on both amd64 and arm64 nodes.

2. **DNS / TLS (Cloudflare).** Add the `pcb2stl.online` zone to Cloudflare. Create an
   `A` record `pcb2stl.online` → your cluster's Traefik ingress IP (`AAAA` too if IPv6).
   Make sure the cert-manager `cloudflare-api-token` secret (namespace `cert-manager`)
   has DNS-edit permission for the `pcb2stl.online` zone — cert-manager then issues the
   TLS certificate via DNS-01 automatically. Check it:
   `kubectl -n production get certificate pcb2stl-tls`. In Cloudflare, set the record to
   **DNS-only** (grey cloud), or **proxied** with SSL mode *Full (strict)* to avoid
   double TLS termination.

## Tuning

All limits are env vars in `deploy/k8s.yaml` (`PCB2STL_*`): pool workers, max
concurrent, conversion timeout, complexity caps, allowed CORS origins. Resources and
replicas are sized for a small node — adjust to your budget.

## Manual deploy / update

```sh
kubectl apply -f deploy/k8s.yaml
# The :latest tag is reused on every build, so to roll out a freshly pushed image:
kubectl -n production rollout restart deployment/pcb2stl
```
