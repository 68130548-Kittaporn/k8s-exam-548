#!/usr/bin/env bash
# Remove the exam apps (namespace iam-548). The Ingress controller is kept.
set -euo pipefail
cd "$(dirname "$0")/.."
kubectl delete -k . --ignore-not-found
