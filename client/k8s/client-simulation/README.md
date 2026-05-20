# Client Simulation Kubernetes Manifests

These manifests deploy the mock error generator to the client GKE cluster.

The deployment uses the `:latest` image tag with `imagePullPolicy: Always`, so
new pods pull the newest pushed image whenever they start.

```bash
gcloud container clusters get-credentials mock-gke-standard \
  --region europe-central2 \
  --project aegis-client-420

kubectl apply -f client/k8s/client-simulation/
kubectl rollout restart deployment/aegis-error-generator -n aegis-simulation
```
