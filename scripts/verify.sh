#!/usr/bin/env bash
# Show the state of every object and test every route through the Ingress.
#   bash scripts/verify.sh                        # uses /etc/hosts
#   IP=192.168.88.130 bash scripts/verify.sh      # bypass /etc/hosts with curl --resolve
set -uo pipefail
NS=iam-548
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

step "kubectl get (namespace $NS)"
kubectl get nodes -o wide
kubectl -n $NS get all -o wide
kubectl -n $NS get configmap,ingress,serviceaccount,role,rolebinding

step "kubectl describe ingress"
kubectl -n $NS describe ingress www-ingress admin-ingress

step "Service endpoints (pods behind each Service)"
kubectl -n $NS get endpoints portal-548 app-research api-548 admin-548

step "RBAC of admin-548 (yes = allowed, no = denied)"
SA=system:serviceaccount:$NS:admin-548
for check in "patch configmap/portal-data" "patch configmap/research-data" \
             "patch deployment/portal-548" "delete configmap/portal-data" \
             "patch configmap/site-config" "delete pods"; do
  printf '  %-34s %s\n' "$check" "$(kubectl auth can-i $check -n $NS --as=$SA 2>/dev/null)"
done

HOSTS=(www.iam-548.com www.id-548.com admin.iam-548.com)
RESOLVE=()
if [[ -n "${IP:-}" ]]; then
  for h in "${HOSTS[@]}"; do RESOLVE+=(--resolve "$h:80:$IP"); done
fi

pass=0; fail=0
check() { # url  expected-text
  local body code
  body=$(curl -s -m 10 "${RESOLVE[@]}" -w '\n%{http_code}' "$1")
  code=${body##*$'\n'}; body=${body%$'\n'*}
  if [[ "$code" == 200 && "$body" == *"$2"* ]]; then
    printf '  \033[32mPASS\033[0m %-55s %s  (contains "%s")\n' "$1" "$code" "$2"; pass=$((pass+1))
  else
    printf '  \033[31mFAIL\033[0m %-55s %s\n' "$1" "$code"; fail=$((fail+1))
  fi
}

step "HTTP checks through the Ingress"
W=http://www.iam-548.com; A=http://admin.iam-548.com
check "$W/"                               "68130548"
ctype=$(curl -s -o /dev/null -m 10 "${RESOLVE[@]}" -w '%{http_code} %{content_type}' "$W/photo")
if [[ "$ctype" == "200 image/"* ]]; then printf '  \033[32mPASS\033[0m %-55s %s\n' "$W/photo" "$ctype"; pass=$((pass+1))
else printf '  \033[31mFAIL\033[0m %-55s %s\n' "$W/photo" "$ctype"; fail=$((fail+1)); fi
check "$W/research"                       "Last updated"
check "$W/api-548/Hello%20I%27m%20June"   "Hello I&#x27;m June"
check "http://www.id-548.com/"            "68130548"
check "$A/"                               "แก้ไข Portal"
check "$A/portal"                         "แก้ไขข้อมูล Portal"
check "$A/research"                       "แก้ไขสรุปงานวิจัย"

step "Edit round-trip: save on admin.iam-548.com, read back on www.iam-548.com/research"
STAMP="verify-$(date +%s)"
BACKUP=$(kubectl -n $NS get configmap research-data -o jsonpath='{.data.research\.json}')
curl -s -o /dev/null "${RESOLVE[@]}" -X POST --data-urlencode "title=$STAMP" \
     --data-urlencode "body=round trip test" "$A/research"
kubectl -n $NS rollout status deployment/app-research --timeout=120s
# The Ingress needs a moment to drop the old pods from its endpoints, and the
# Service spreads requests over 2 replicas, so wait for 6 hits in a row.
ok=0
for i in $(seq 1 90); do
  if curl -s "${RESOLVE[@]}" "$W/research" | grep -q "$STAMP"; then ok=$((ok+1)); else ok=0; fi
  [[ $ok -ge 6 ]] && break
  sleep 1
done
echo "  new data served by every pod after ${i}s"
check "$W/research" "$STAMP"

# put the real summary back
PATCH=$(python3 -c 'import json,sys; print(json.dumps({"data":{"research.json":sys.stdin.read()}}))' <<<"$BACKUP")
kubectl -n $NS patch configmap research-data --type merge -p "$PATCH" >/dev/null
kubectl -n $NS rollout restart deployment/app-research >/dev/null
kubectl -n $NS rollout status deployment/app-research --timeout=120s >/dev/null
echo "  original summary restored"

printf '\nResult: %d passed, %d failed\n' "$pass" "$fail"
[[ $fail -eq 0 ]]
