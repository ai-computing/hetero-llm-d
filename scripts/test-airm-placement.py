#!/usr/bin/env python3
"""Offline tests for scripts/airm-placement.py and scripts/check-epp-config.py. Requires Python 3.6+,
PyYAML for the EPP part."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def _module(name, file):
    spec = importlib.util.spec_from_file_location(name, str(HERE / file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ap = _module("airm_placement", "airm-placement.py")

# Produced by ai-rm rm-controller (controller.plan + document.build/configmap, policy `topology`) for
# a lab-shaped node (3 RNGD + 4 ATOM) and a second RNGD node; node names are placeholders. The second
# pool asks for more RNGD than one node has, so its decisions are empty with a reason.
DOC = {
    "protocol": "0.1", "generation": 7, "updatedAt": "2026-10-19T00:00:00Z", "placement": "topology",
    "decisions": [
        {"pool": "llama8b-pd-pool",
         "workload": {"kind": "prefill", "model": "meta-llama/Llama-3.1-8B-Instruct",
                      "slo": {"tpot_p90_ms": 100}, "labels": {"airm.ai-computing.io/accelerator": "furiosa.RNGD"}},
         "acceleratorIds": ["npu-node-a/furiosa:0"], "kvTransport": "shm",
         "reason": "topology: prefill npu-node-a/furiosa:0 (furiosa.RNGD, highest peak) on npu-node-a"},
        {"pool": "llama8b-pd-pool",
         "workload": {"kind": "decode", "model": "meta-llama/Llama-3.1-8B-Instruct",
                      "slo": {"tpot_p90_ms": 100}, "labels": {"airm.ai-computing.io/accelerator": "rebellions.ATOM"}},
         "acceleratorIds": ["npu-node-a/rebellions:0", "npu-node-a/rebellions:1"], "kvTransport": "shm",
         "reason": "topology: decode npu-node-a/rebellions:0, npu-node-a/rebellions:1 on npu-node-a"},
        {"pool": "nofit-pool",
         "workload": {"kind": "prefill", "model": "m", "slo": {},
                      "labels": {"airm.ai-computing.io/accelerator": "furiosa.RNGD"}},
         "acceleratorIds": [], "kvTransport": "shm", "reason": "no free furiosa.RNGD x4 for prefill"},
    ],
}
CM = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "airm-placement"},
      "data": {"decisions.json": json.dumps(DOC)}}


def deploy(name, role, pool, resource, n=1, **pod):
    spec = {"containers": [{"name": "worker", "resources": {"limits": {resource: str(n)}}}]}
    spec.update(pod)
    labels = {"airm.ai-computing.io/pool": pool} if pool else {}
    if role:
        labels["llm-d.ai/role"] = role
    return {"kind": "Deployment", "metadata": {"name": name, "labels": labels},
            "spec": {"template": {"spec": spec}}}


def scaled(name, target, lo=1, hi=4):
    return {"kind": "ScaledObject", "metadata": {"name": name},
            "spec": {"scaleTargetRef": {"name": target}, "minReplicaCount": lo, "maxReplicaCount": hi}}


PREFILL = deploy("rngd-pd-prefill", "prefill", "llama8b-pd-pool", "furiosa.ai/rngd")
DECODE = deploy("rngd-pd-decode", "decode", "llama8b-pd-pool", "rebellions.ai/ATOM")


class PlacementTests(unittest.TestCase):
    def plan(self, doc=DOC, deps=(PREFILL, DECODE), sos=()):
        log = io.StringIO()
        return {(k, n): p for k, n, p in ap.plan(doc, list(deps), list(sos), log=log)}, log.getvalue()

    def test_configmap_and_bare_document_load_alike(self):
        self.assertEqual(ap.load_document(CM), DOC)
        self.assertEqual(ap.load_document(DOC), DOC)
        self.assertEqual(ap.load_document(None)["decisions"], [])

    def test_affinity_pins_node_and_vendor_model_label(self):
        out, _ = self.plan()
        term = out[("deployment", "rngd-pd-prefill")]["spec"]["template"]["spec"]["affinity"]["nodeAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]
        self.assertEqual(term, [{
            "matchFields": [{"key": "metadata.name", "operator": "In", "values": ["npu-node-a"]}],
            "matchExpressions": [{"key": "airm.ai-computing.io/furiosa.RNGD", "operator": "Exists"}]}])
        dec = out[("deployment", "rngd-pd-decode")]["spec"]["template"]["spec"]["affinity"]["nodeAffinity"]
        self.assertEqual(dec["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"][0][
            "matchExpressions"][0]["key"], "airm.ai-computing.io/rebellions.ATOM")
        self.assertEqual(out[("deployment", "rngd-pd-decode")]["metadata"]["annotations"],
                         {"airm.ai-computing.io/placement-generation": "7"})

    def test_scaledobject_capped_at_placed_cards(self):
        sos = [scaled("rngd-pd-prefill", "rngd-pd-prefill", 1, 3), scaled("rngd-pd-decode", "rngd-pd-decode", 1, 4)]
        out, _ = self.plan(sos=sos)
        self.assertEqual(out[("scaledobject", "rngd-pd-prefill")]["spec"], {"maxReplicaCount": 1})
        self.assertEqual(out[("scaledobject", "rngd-pd-decode")]["spec"], {"maxReplicaCount": 2})
        two_card = deploy("rngd-pd-decode", "decode", "llama8b-pd-pool", "rebellions.ai/ATOM", n=2)
        out, _ = self.plan(deps=[two_card], sos=[scaled("d", "rngd-pd-decode", 2, 4)])
        self.assertEqual(out[("scaledobject", "d")]["spec"], {"maxReplicaCount": 1, "minReplicaCount": 1})

    def test_empty_document_changes_nothing(self):
        out, log = self.plan(doc={"protocol": "0.1", "generation": 0, "decisions": []})
        self.assertEqual(out, {})
        self.assertIn("no decisions", log)

    def test_unplaced_pool_and_unlabelled_or_unmatched_deployments_left_alone(self):
        nofit = deploy("nofit-prefill", "prefill", "nofit-pool", "furiosa.ai/rngd")
        other = deploy("vllm-x", None, None, "nvidia.com/gpu")
        serve = deploy("serve-x", None, "llama8b-pd-pool", "nvidia.com/gpu")   # no serve decision
        out, log = self.plan(deps=[nofit, other, serve])
        self.assertEqual(out, {})
        self.assertIn("placed nowhere (no free furiosa.RNGD x4 for prefill)", log)
        self.assertIn("no serve decision", log)

    def test_applied_generation_and_nodename_skipped(self):
        done = copy.deepcopy(PREFILL)
        done["metadata"]["annotations"] = {"airm.ai-computing.io/placement-generation": "7"}
        done["spec"]["template"]["spec"]["affinity"] = {"nodeAffinity": ap.node_affinity([DOC["decisions"][0]])}
        pinned = deploy("rngd-pd-decode", "decode", "llama8b-pd-pool", "rebellions.ai/ATOM", nodeName="n1")
        out, log = self.plan(deps=[done, pinned])
        self.assertEqual(out, {})
        self.assertIn("generation 7 already applied", log)
        self.assertIn("nodeName=n1", log)

    def test_partial_apply_retries_scaledobject_after_deployment_succeeded(self):
        done = copy.deepcopy(PREFILL)
        done["metadata"]["annotations"] = {ap.GEN_ANNOTATION: "7"}
        done["spec"]["template"]["spec"]["affinity"] = {"nodeAffinity": ap.node_affinity([DOC["decisions"][0]])}
        out, _ = self.plan(deps=[done], sos=[scaled("scale", "rngd-pd-prefill")])
        self.assertEqual(set(out), {("scaledobject", "scale")})
        self.assertEqual(out[("scaledobject", "scale")]["spec"], {"maxReplicaCount": 1})

    def test_same_generation_repairs_drift_and_is_quiet_when_both_objects_match(self):
        dep, so = copy.deepcopy(PREFILL), scaled("scale", "rngd-pd-prefill", hi=4)
        for obj in (dep, so):
            obj["metadata"]["annotations"] = {ap.GEN_ANNOTATION: "7"}
        out, _ = self.plan(deps=[dep], sos=[so])
        self.assertEqual(set(out), {("deployment", "rngd-pd-prefill"), ("scaledobject", "scale")})
        dep["spec"]["template"]["spec"]["affinity"] = {"nodeAffinity": ap.node_affinity([DOC["decisions"][0]])}
        so["spec"]["maxReplicaCount"] = 1
        self.assertEqual(self.plan(deps=[dep], sos=[so])[0], {})

    def test_newer_deployment_generation_protects_its_placement_and_scaling(self):
        dep = copy.deepcopy(PREFILL)
        dep["metadata"]["annotations"] = {ap.GEN_ANNOTATION: "8"}
        self.assertEqual(self.plan(deps=[dep], sos=[scaled("scale", "rngd-pd-prefill")])[0], {})

    def test_newer_scaledobject_generation_is_not_rolled_back(self):
        so = scaled("scale", "rngd-pd-prefill")
        so["metadata"]["annotations"] = {ap.GEN_ANNOTATION: "8"}
        out, _ = self.plan(deps=[PREFILL], sos=[so])
        self.assertEqual(set(out), {("deployment", "rngd-pd-prefill")})

    def test_shared_helm_value_pins_nodes_only(self):
        both = ap.node_affinity([d for d in DOC["decisions"] if d["pool"] == "llama8b-pd-pool"])
        term = both["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"][0]
        self.assertNotIn("matchExpressions", term)   # RNGD prefill + ATOM decode share one value
        self.assertEqual(term["matchFields"][0]["values"], ["npu-node-a"])

    def test_bad_id_rejected(self):
        with self.assertRaises(ValueError):
            ap.split_id("furiosa:0")


class EppConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ck = _module("check_epp_config", "check-epp-config.py")
        import yaml
        cls.base = yaml.safe_load((HERE.parent / "manifests/epp/profiles/precise-prefix.yaml").read_text(encoding="utf-8"))

    def errors(self, mutate):
        cfg = copy.deepcopy(self.base)
        mutate(cfg)
        return self.ck.check_config(cfg)

    def test_shipped_configs_pass(self):
        for f in self.ck.default_files():
            for label, cfg in self.ck.configs_in(f):
                self.assertEqual(self.ck.check_config(cfg), [], label)

    def test_unknown_type_and_key_caught(self):
        self.assertTrue(self.errors(lambda c: c["plugins"].append({"type": "prefix-scorer"})))
        self.assertTrue(self.errors(lambda c: c["plugins"][1]["parameters"]["kvEventsConfig"].update(port=1)))

    def test_dangling_refs_caught(self):
        self.assertTrue(self.errors(lambda c: c["schedulingProfiles"][0]["plugins"].append({"pluginRef": "nope"})))
        self.assertTrue(self.errors(lambda c: c["plugins"][2]["parameters"].update(prefixMatchInfoProducerName="x")))

    def test_precise_needs_real_tokens_and_event_wiring(self):
        self.assertTrue(self.errors(lambda c: c["plugins"].pop(0)))       # no token-producer
        self.assertTrue(self.errors(lambda c: c.pop("dataLayer")))         # no subscriber wiring


if __name__ == "__main__":
    unittest.main()
