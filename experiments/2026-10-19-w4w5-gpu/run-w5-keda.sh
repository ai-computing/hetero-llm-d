#!/usr/bin/env bash
# W5: KEDA ScaledObject on the A100 Deployment; drive the queue, record 1->2 and back to 1.
# Precondition: vLLM spec as committed, replicas 1 and Ready; EPP vllm-a100-epp on queue-kv; route /gpu/llama8b.
set -u
cd "$(git rev-parse --show-toplevel)"
E=experiments/2026-10-19-w4w5-gpu; R=$E/results/keda; mkdir -p $R
export GW=${GW:-http://<gateway>/gpu/llama8b}
NS=llm-serving; D=vllm-a100-llama31-8b
q() { kubectl get --raw "/api/v1/namespaces/monitoring/services/kube-prometheus-stack-prometheus:9090/proxy/api/v1/query?query=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$1")" | jq -r '.data.result[0].value[1] // "nan"'; }
watch() {  # one line per 5 s: time spec status hpa-desired waiting ttft-p90 pods
  while :; do
    s=$(kubectl -n $NS get deploy $D -o jsonpath='{.spec.replicas} {.status.readyReplicas}')
    h=$(kubectl -n $NS get hpa keda-hpa-$D -o jsonpath='{.status.desiredReplicas} {.status.currentReplicas}' 2>/dev/null)
    w=$(q 'sum(vllm:num_requests_waiting{namespace="llm-serving",service="vllm-a100-llama31-8b"})')
    t=$(q 'histogram_quantile(0.9, sum by (le) (rate(vllm:time_to_first_token_seconds_bucket{namespace="llm-serving",service="vllm-a100-llama31-8b"}[2m]))) > 0 or vector(0)')
    p=$(kubectl -n $NS get pod -l app=$D --no-headers 2>/dev/null | awk '{printf "%s:%s:%s ", substr($1,length($1)-4), $2, $3}')
    echo -e "$(date -u +%T)\tspec_ready=$s\thpa_desired_current=$h\twaiting=$w\tttft_p90=$t\t$p"
    sleep 5
  done
}
echo "== apply ScaledObject $(date -u +%T)"
kubectl apply --dry-run=server -f manifests/autoscaling/keda-vllm-a100.yaml
kubectl apply -f manifests/autoscaling/keda-vllm-a100.yaml
sleep 40
kubectl -n $NS get scaledobject,hpa
watch > $R/watch.tsv 2>&1 &
WP=$!
sleep 30
echo "== load start $(date -u +%T)"
MODE=unique PREFIX_WORDS=4600 N=1200 CONC=160 MAXTOK=256 SALT=keda python3 $E/prefix_load.py $R/keda-load.json > $R/keda-load.txt 2>&1
echo "== load end $(date -u +%T)"
# wait for scale-down to 1 (window 600 s + policy), at most 30 min
for i in $(seq 1 360); do
  r=$(kubectl -n $NS get deploy $D -o jsonpath='{.spec.replicas}')
  [ "$r" = 1 ] && [ $i -gt 6 ] && { echo "== back to 1 $(date -u +%T)"; break; }
  sleep 5
done
sleep 30
kill $WP
kubectl -n $NS describe hpa keda-hpa-$D > $R/hpa-describe.txt 2>&1
kubectl -n $NS get events --field-selector involvedObject.name=keda-hpa-$D -o json | jq -r '.items[] | [.firstTimestamp, .lastTimestamp, .reason, .message] | @tsv' > $R/hpa-events.tsv
kubectl -n $NS get events --field-selector involvedObject.name=$D -o json | jq -r '.items[] | [.firstTimestamp, .lastTimestamp, .reason, .message] | @tsv' > $R/deploy-events.tsv
kubectl -n $NS get scaledobject $D -o yaml > $R/scaledobject-status.yaml
echo ALLDONE $(date -u +%T)
