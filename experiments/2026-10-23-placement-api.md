# Placement partial-apply recovery on the live API

- **Date**: 2026-10-23
- **Task**: Fix placement installer and partial apply recovery
- **Host / device**: cluster control plane; KEDA 2.19.0; no accelerator workload
- **Commit**: `b56e59b5c995b1b81f896948eea55eaefec89dc6`

## Question

Does the planner retry an unfinished ScaledObject update after the Deployment generation was committed,
and does it preserve a newer generation when talking to actual Kubernetes objects?

## Setup

An isolated namespace contained a zero-replica Deployment labelled for pool `verify-pool`, role `decode`,
and a paused KEDA ScaledObject with maximum 4. The document placed two ATOM IDs at generation 7.
Only the new namespace was mutated. No accelerator was requested and no serving Pod was launched.

The ServiceAccount/Role/RoleBinding came from the AI-RM Helm chart with `controller.apply=true`; only
namespaced resources were installed. This also verified the follow-up `get,list,patch` Role needed by
`kubectl patch`, which first reads the object. Cross-namespace list/patch and delete remained forbidden.

## Command

The owning local scratch harness `controlplane.py` was sent through research-hub `run_remote` and used
the following operations (with the isolated namespace and newly created ServiceAccount):

```sh
kubectl auth can-i list deployments.apps -n "$NS" --as="$SERVICEACCOUNT"
kubectl auth can-i patch deployments.apps -n "$NS" --as="$SERVICEACCOUNT"
kubectl get deployments -n "$NS" -o json --as="$SERVICEACCOUNT"
kubectl patch deployment decode -n "$NS" --type=merge -p "$DEPLOYMENT_PATCH" --as="$SERVICEACCOUNT"
# The same account has no KEDA permission: this operation returned HTTP 403.
kubectl patch scaledobject decode -n "$NS" --type=merge -p "$SCALEDOBJECT_PATCH" --as="$SERVICEACCOUNT"
# Replan from fresh API objects, then apply only the unfinished ScaledObject as the test administrator.
kubectl patch scaledobject decode -n "$NS" --type=merge -p "$RETRY_PATCH"
```

Each plan was produced by the exact checked-out `scripts/airm-placement.py::plan` using freshly retrieved
Deployment and ScaledObject JSON. Assertions checked the emitted resource kinds, final cap, subsequent
empty plan, newer generation, zero replicas, and UID-guarded namespace cleanup.

The CPU-trigger fixture needed a CPU request and `minReplicaCount: 1` to pass admission. It used
`autoscaling.keda.sh/paused: "true"` to retain the zero-replica Deployment. Earlier fixture submissions
without those CPU prerequisites were rejected and cleaned up before the successful run.

## Results

| configuration | check | result |
|---|---|---|
| Deployment and ScaledObject at old state | initial plan | Deployment + ScaledObject |
| Deployment generation 7 committed; KEDA operation HTTP 403 | retry plan | ScaledObject only |
| Retried ScaledObject patch | maximum replicas | 4 → 2 |
| Both objects match generation 7 | next plan | empty |
| Deployment generation 8; document 7 | next plan | empty; newer object preserved |
| Apply Role removed | ServiceAccount patch permission | revoked |
| Fixture Deployment | replicas | stayed 0 |
| Cleanup | namespace UID guard and absence | passed |

Raw API results: [placement-api-20261023.json](data/placement-api-20261023.json).

## Conclusion

The partial-update retry and generation protection work against the live API. The validation also found
and fixed a separate AI-RM kubectl permission gap. This run does not validate placement quality, automatic
serving restarts or load-driven autoscaling; the ScaledObject was deliberately paused. Existing production
Deployments, placement data and node state were unchanged.
