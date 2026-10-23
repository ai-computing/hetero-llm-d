#!/usr/bin/env python3
"""Turn ai-rm placement decisions (ConfigMap llm-serving/airm-placement, key decisions.json, written
by ai-rm rm-controller) into scheduling constraints on the serving Deployments. Stdlib only, 3.6+.

A decision names a pool, a workload kind (prefill / decode / serve ...) and accelerator ids
`<node>/<vendor>:<index>`. For the Deployment of that pool and role it yields:

  - required node affinity: the nodes in acceleratorIds (matchFields metadata.name) AND the node
    summary label `airm.ai-computing.io/<vendor>.<model>` (Exists), the same `vendor.model` string
    rm-controller filtered on (workload.labels["airm.ai-computing.io/accelerator"]);
  - for a KEDA ScaledObject scaling that Deployment: maxReplicaCount = placed cards / cards per pod,
    so autoscaling never asks for a pod the placement has no card for;
  - annotation airm.ai-computing.io/placement-generation = the document's generation.

Which card index a pod gets is still the device plugin's choice; the decision pins node and kind.
Deployments opt in with the label `airm.ai-computing.io/pool=<InferencePool name>`; the role comes
from their `llm-d.ai/role` label (absent = serve). Readers' rules from deploy/airm/README.md hold:
an empty decisions list, or no decision for a pool, changes nothing; an empty acceleratorIds (nothing
fits) changes nothing and is reported; matching objects are skipped and newer generations protected.

    # patches for scripts/airm-install.sh (tab-separated: kind, name, merge-patch JSON)
    airm-placement.py plan --decisions cm.json --deployments deploy.json [--scaledobjects so.json]
    # the nodeAffinity value for a Helm install (e.g. ai-rm rngd-pd `nodeAffinity`)
    airm-placement.py affinity --decisions cm.json --pool llama8b-pd-pool [--role prefill]

Inputs are `kubectl get -o json` output (a ConfigMap or the bare document; a List of objects).
"""
import argparse
import json
import sys

PREFIX = "airm.ai-computing.io/"
ACCEL_LABEL = PREFIX + "accelerator"          # rm-controller: Workload.labels key, "vendor.model"
POOL_LABEL = PREFIX + "pool"                  # Deployment opt-in: InferencePool name
GEN_ANNOTATION = PREFIX + "placement-generation"
ROLE_LABEL = "llm-d.ai/role"
KEY = "decisions.json"
# Device-plugin resources per vendor, to count cards per pod.
VENDOR_RESOURCES = {"furiosa": "furiosa.ai/rngd", "rebellions": "rebellions.ai/ATOM",
                    "nvidia": "nvidia.com/gpu"}


def load_document(obj):
    """The decisions document from a ConfigMap object, the bare document, or None."""
    if not obj:
        return {"protocol": "0.1", "generation": 0, "decisions": []}
    if obj.get("kind") == "ConfigMap":
        raw = (obj.get("data") or {}).get(KEY)
        return json.loads(raw) if raw else {"protocol": "0.1", "generation": 0, "decisions": []}
    return obj


def split_id(acc_id):
    """'<node>/<vendor>:<index>' -> (node, vendor, index)."""
    node, _, rest = acc_id.rpartition("/")
    vendor, _, index = rest.partition(":")
    if not node or not vendor:
        raise ValueError("bad accelerator id %r (want <node>/<vendor>:<index>)" % acc_id)
    return node, vendor, int(index) if index.isdigit() else 0


def role_of(deploy):
    return ((deploy.get("metadata") or {}).get("labels") or {}).get(ROLE_LABEL) or "serve"


def kind_to_role(kind):
    return kind if kind in ("prefill", "decode") else "serve"


def node_affinity(decisions):
    """Required nodeAffinity for one or more decisions of a pool (None if nothing to pin).

    One term: node name in the union of the decisions' nodes, plus the vendor.model label when all
    decisions agree on it (a shared Helm value for prefill on RNGD and decode on ATOM only pins nodes).
    """
    nodes, kinds = set(), set()
    for d in decisions:
        for acc in d.get("acceleratorIds") or []:
            nodes.add(split_id(acc)[0])
        kinds.add(((d.get("workload") or {}).get("labels") or {}).get(ACCEL_LABEL))
    if not nodes:
        return None
    term = {"matchFields": [{"key": "metadata.name", "operator": "In", "values": sorted(nodes)}]}
    if len(kinds) == 1 and None not in kinds:
        term["matchExpressions"] = [{"key": PREFIX + kinds.pop(), "operator": "Exists"}]
    return {"requiredDuringSchedulingIgnoredDuringExecution": {"nodeSelectorTerms": [term]}}


def cards_per_pod(deploy, vendor):
    res = VENDOR_RESOURCES.get(vendor)
    total = 0
    for c in (((deploy.get("spec") or {}).get("template") or {}).get("spec") or {}).get("containers") or []:
        lim = ((c.get("resources") or {}).get("limits") or {}).get(res)
        if lim is not None:
            total += int(str(lim))
    return total or 1


def find(decisions, pool, role):
    return [d for d in decisions
            if d.get("pool") == pool and kind_to_role((d.get("workload") or {}).get("kind")) == role]


def plan(doc, deployments, scaledobjects=(), log=sys.stderr):
    """[(kind, name, merge_patch)] that make the Deployments follow the document."""
    out = []
    generation = int(doc.get("generation") or 0)
    decisions = doc.get("decisions") or []
    if not decisions:
        print("airm-placement: no decisions (generation %d); nothing to apply" % generation, file=log)
        return out
    by_target = {}
    for so in scaledobjects:
        target = ((so.get("spec") or {}).get("scaleTargetRef") or {}).get("name")
        if target:
            by_target[target] = so
    for dep in deployments:
        meta = dep.get("metadata") or {}
        name, pool, role = meta.get("name"), (meta.get("labels") or {}).get(POOL_LABEL), role_of(dep)
        if not pool:
            continue
        mine = find(decisions, pool, role)
        if not mine:
            print("airm-placement: %s: no %s decision for pool %s; left as is" % (name, role, pool), file=log)
            continue
        ids = [a for d in mine for a in d.get("acceleratorIds") or []]
        if not ids:
            why = "; ".join(d.get("reason") or "" for d in mine)
            print("airm-placement: %s: pool %s %s placed nowhere (%s); left as is" % (name, pool, role, why),
                  file=log)
            continue
        applied = (meta.get("annotations") or {}).get(GEN_ANNOTATION)
        if applied is not None and applied.isdigit() and int(applied) > generation:
            print("airm-placement: %s: newer generation %s; left as is" % (name, applied), file=log)
            continue
        pod_spec = ((dep.get("spec") or {}).get("template") or {}).get("spec") or {}
        if pod_spec.get("nodeName"):
            print("airm-placement: %s: pinned by nodeName=%s, which bypasses affinity; left as is"
                  % (name, pod_spec["nodeName"]), file=log)
            continue
        affinity = node_affinity(mine)
        if applied != str(generation) or (pod_spec.get("affinity") or {}).get("nodeAffinity") != affinity:
            out.append(("deployment", name, {
                "metadata": {"annotations": {GEN_ANNOTATION: str(generation)}},
                "spec": {"template": {"spec": {"affinity": {"nodeAffinity": affinity}}}}}))
        else:
            print("airm-placement: %s: generation %s already applied" % (name, applied), file=log)
        so = by_target.get(name)
        if so:
            so_applied = ((so.get("metadata") or {}).get("annotations") or {}).get(GEN_ANNOTATION)
            if so_applied is not None and so_applied.isdigit() and int(so_applied) > generation:
                print("airm-placement: %s: newer generation %s; left as is"
                      % (so["metadata"]["name"], so_applied), file=log)
                continue
            vendor = split_id(ids[0])[1]
            cap = max(1, len(ids) // cards_per_pod(dep, vendor))
            spec = so.get("spec") or {}
            if (so_applied == str(generation) and spec.get("maxReplicaCount") == cap
                    and int(spec.get("minReplicaCount", 0)) <= cap):
                continue
            patch = {"metadata": {"annotations": {GEN_ANNOTATION: str(generation)}},
                     "spec": {"maxReplicaCount": cap}}
            if int(spec.get("minReplicaCount", 0)) > cap:
                patch["spec"]["minReplicaCount"] = cap
            out.append(("scaledobject", so["metadata"]["name"], patch))
    return out


def _load(path):
    if not path:
        return None
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    return json.loads(text) if text.strip() else None


def _items(obj):
    if not obj:
        return []
    return obj.get("items", []) if obj.get("kind", "").endswith("List") or "items" in obj else [obj]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan", help="merge patches for Deployments / ScaledObjects (tab-separated)")
    p.add_argument("--decisions", required=True)
    p.add_argument("--deployments", required=True)
    p.add_argument("--scaledobjects")
    a = sub.add_parser("affinity", help="nodeAffinity JSON for one pool (and role)")
    a.add_argument("--decisions", required=True)
    a.add_argument("--pool", required=True)
    a.add_argument("--role", choices=("prefill", "decode", "serve"))
    args = ap.parse_args(argv)
    doc = load_document(_load(args.decisions))
    if args.cmd == "plan":
        for kind, name, patch in plan(doc, _items(_load(args.deployments)), _items(_load(args.scaledobjects))):
            print(kind, name, json.dumps(patch, separators=(",", ":"), sort_keys=True), sep="\t")
        return 0
    if args.cmd == "affinity":
        mine = [d for d in doc.get("decisions") or [] if d.get("pool") == args.pool
                and (not args.role or kind_to_role((d.get("workload") or {}).get("kind")) == args.role)]
        aff = node_affinity(mine)
        if aff is None:
            print("airm-placement: no placed decision for %s%s" % (args.pool, " " + args.role if args.role else ""),
                  file=sys.stderr)
            print("{}")
            return 1
        print(json.dumps(aff, sort_keys=True))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
