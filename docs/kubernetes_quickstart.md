# Kubernetes quickstart

## Local (kind/minikube)
1. Build image: `make build`
2. Load image into cluster (`kind load docker-image citeshield-api:local` if using kind).
3. Deploy: `make k8s-deploy`
4. Smoke test: `make k8s-smoke`
5. Cleanup: `make k8s-clean`

Use `deploy/k8s/overlays/prod-template` as a production template and create real secrets out-of-band.
