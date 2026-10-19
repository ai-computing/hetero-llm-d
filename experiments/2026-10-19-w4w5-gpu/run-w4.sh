#!/usr/bin/env bash
# W4 sequence of 2026-10-19 in one script (it ran in several parts; control-plane node, repo root as cwd,
# vLLM at 2 replicas). The precise-prefix part shows the final engine setting (3.).
# GW = gateway base + the temporary route /gpu/llama8b (-> /v1 on InferencePool vllm-a100-pool).
set -u
E=experiments/2026-10-19-w4w5-gpu; R=$E/results; mkdir -p $R
export GW=${GW:-http://<gateway>/gpu/llama8b}
# approx-prefix-w3 = approx-prefix with prefix weight 3 (committed afterwards as approx-prefix-gpu)
sed 's/^    weight: 1$/    weight: 3/' manifests/epp/profiles/approx-prefix.yaml > manifests/epp/profiles/approx-prefix-w3.yaml
load() { local name=$1; shift; env "$@" SALT=$prof-$name python3 $E/prefix_load.py $R/$prof-$name.json; }
for prof in queue-kv approx-prefix approx-prefix-w3; do
  EPP_PROFILE=$prof manifests/epp/make-epp.sh vllm-a100-pool /gpu
  kubectl -n llm-serving rollout restart deploy/vllm-a100-epp      # ConfigMap changes need a restart
  kubectl -n llm-serving rollout status deploy/vllm-a100-epp --timeout=200s; sleep 20
  load probe1 MODE=shared PREFIXES=1 N=20 CONC=1
  load probe8-c1 MODE=shared PREFIXES=8 N=64 CONC=1
  for rep in a b; do
    load shared8-$rep MODE=shared N=256 CONC=16
    [ $prof = approx-prefix-w3 ] || load unique-$rep MODE=unique N=128 CONC=16
  done
  load pressure220 MODE=shared PREFIXES=220 PREFIX_WORDS=2300 N=1100 CONC=32
  load pressure220-b MODE=shared PREFIXES=220 PREFIX_WORDS=2300 N=1100 CONC=32
done
rm -f manifests/epp/profiles/approx-prefix-w3.yaml

# precise-prefix: three engine settings, same loads (profile names precise-prefix / precise-fixed / precise-bs64)
#  1. topic kv@$(POD_IP)@<model>, vLLM default block 16
#  2. topic kv@$(POD_IP):8000@<model>, block 16
#  3. topic kv@$(POD_IP):8000@<model>, --block-size=64
kubectl -n llm-serving patch deploy vllm-a100-llama31-8b --type=json -p '[
 {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kv-events-config={\"enable_kv_cache_events\":true,\"publisher\":\"zmq\",\"endpoint\":\"tcp://*:5557\",\"topic\":\"kv@$(POD_IP):8000@meta-llama/Llama-3.1-8B-Instruct\"}"},
 {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--block-size=64"},
 {"op":"add","path":"/spec/template/spec/containers/0/env/-","value":{"name":"POD_IP","valueFrom":{"fieldRef":{"fieldPath":"status.podIP"}}}},
 {"op":"add","path":"/spec/template/spec/containers/0/ports/-","value":{"name":"kv-events","containerPort":5557}}]'
kubectl -n llm-serving rollout status deploy/vllm-a100-llama31-8b --timeout=600s
EPP_PROFILE=precise-prefix manifests/epp/make-epp.sh vllm-a100-pool /gpu
kubectl -n llm-serving logs deploy/vllm-a100-epp -c epp | grep 'Connected subscriber socket'
prof=precise-bs64
load probe1 MODE=shared PREFIXES=1 N=20 CONC=1
load probe8-c1 MODE=shared PREFIXES=8 N=64 CONC=1
load shared8-a MODE=shared N=256 CONC=16; load shared8-b MODE=shared N=256 CONC=16
load pressure220 MODE=shared PREFIXES=220 PREFIX_WORDS=2300 N=1100 CONC=32
load pressure220-b MODE=shared PREFIXES=220 PREFIX_WORDS=2300 N=1100 CONC=32
# EPP index counters per run (results/precise-*-index-deltas.txt): llm_d_epp_kv_cache_index_{lookup_requests,
# lookup_hits,admissions,evictions}_total and llm_d_epp_prefix_{predicted_cached,prompt}_tokens_sum from the
# EPP's :9090/metrics (needs a bearer token, e.g. kubectl -n monitoring create token kube-prometheus-stack-prometheus).
