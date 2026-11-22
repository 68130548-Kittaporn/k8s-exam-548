#!/usr/bin/env bash
# Deploy the iam-548 exam: 4 apps + RBAC + 2 Ingress rules.
# Run on k8s-control (or any machine whose kubectl points at the cluster):
#   bash scripts/deploy.sh
#   INGRESS_NODE=k8s-worker2 bash scripts/deploy.sh   # node that receives port 80 (default)
set -euo pipefail
cd "$(dirname "$0")/.."

NS=iam-548
INGRESS_VERSION=${INGRESS_VERSION:-controller-v1.11.3}
INGRESS_NODE=${INGRESS_NODE:-k8s-worker2}
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

step "Cluster nodes"
kubectl get nodes -o wide

# ---------------------------------------------------------------- 1. ingress controller
step "1. NGINX Ingress Controller"
if kubectl get ingressclass nginx >/dev/null 2>&1; then
  echo "ingressclass nginx already exists, skip install"
else
  kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_VERSION}/deploy/static/provider/baremetal/deploy.yaml"
  # Listen on port 80/443 of the node itself, so the URL has no :port
  kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=json -p='[
    {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
    {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
fi
# Keep the controller on one node, so the IP in the hosts file never changes
kubectl -n ingress-nginx patch deployment ingress-nginx-controller \
  -p "{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":{\"kubernetes.io/hostname\":\"$INGRESS_NODE\"}}}}}"
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=300s
kubectl get ingressclass

# ---------------------------------------------------------------- 2. apps + ingress
step "2. Apply manifests (kubectl apply -k .)"
# The admission webhook can need a few seconds after the controller is Ready
for i in 1 2 3 4 5 6; do
  kubectl apply -k . && break
  echo "apply failed (webhook not ready yet?), retry $i/6 in 10s"; sleep 10
done

step "3. Wait for the Deployments"
for d in portal-548 app-research api-548 admin-548; do
  kubectl -n "$NS" rollout status "deployment/$d" --timeout=180s
done

# ---------------------------------------------------------------- 3. status + hosts line
step "4. Status"
kubectl -n "$NS" get deploy,pods,svc,ingress -o wide

IP=$(kubectl -n ingress-nginx get pod -l app.kubernetes.io/component=controller \
      -o jsonpath='{.items[0].status.hostIP}')
cat <<EOF

Add this line to /etc/hosts (Linux) or C:\\Windows\\System32\\drivers\\etc\\hosts (Windows):

    $IP  www.iam-548.com www.id-548.com admin.iam-548.com

Then open:
    http://www.iam-548.com/
    http://www.iam-548.com/research
    http://www.iam-548.com/api-548/Hello%20I%27m%20June
    http://admin.iam-548.com/

Run: bash scripts/verify.sh   to check every route with curl.
EOF
