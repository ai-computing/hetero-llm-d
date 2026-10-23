#!/usr/bin/env python3
"""Exercise the real installer with an isolated, stateful kubectl executable (no cluster)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BASH = (str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
        if os.name == "nt" else shutil.which("bash"))


def posix(path):
    path = str(path).replace("\\", "/")
    return "/" + path[0].lower() + path[2:] if os.name == "nt" else path


FAKE_KUBECTL = r'''#!/usr/bin/env bash
set -eu
[[ "$1" != --request-timeout=* ]] || shift
echo "$*" >> "$TEST_DIR/calls"
case "$*" in
  'get --raw /readyz') exit 0 ;;
  'get configmap airm-placement '*)
    [[ "$SEED" != error ]] || { echo Forbidden >&2; exit 1; }
    if [[ "$*" == *'-o json'* ]]; then cat "$TEST_DIR/cm.json"
    elif [[ -f "$TEST_DIR/state" ]]; then echo configmap/airm-placement; fi
    exit 0 ;;
  *'/airm-placement.yaml'*)
    [[ "$*" == *'--dry-run=server'* ]] || echo seed-generation-zero > "$TEST_DIR/state"
    exit 0 ;;
  'create configmap grafana-dashboard-airm '*) echo 'kind: ConfigMap'; exit 0 ;;
  'label --local '*) cat; exit 0 ;;
  'apply -f -') cat >/dev/null; exit 0 ;;
  'apply --dry-run=server -f -') cat >/dev/null; exit 0 ;;
  'get deployments '*) cat "$TEST_DIR/deploy.json"; exit 0 ;;
  'api-resources '*)
    [[ "$KEDA" != discovery-error ]] || { echo Forbidden >&2; exit 1; }
    [[ "$KEDA" == absent ]] || echo scaledobjects.keda.sh
    exit 0 ;;
  'get scaledobjects.keda.sh '*)
    [[ "$KEDA" != read-error ]] || { echo Forbidden >&2; exit 1; }
    echo '{"items": []}'; exit 0 ;;
  'patch '*) exit 0 ;;
esac
'''


@unittest.skipUnless(BASH and Path(BASH).is_file(), "requires Bash")
class InstallTests(unittest.TestCase):
    def run_install(self, action="apply", target="manifests", seed="present", keda="present"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kubectl = root / "kubectl"
            kubectl.write_text(FAKE_KUBECTL, encoding="utf-8")
            kubectl.chmod(0o755)
            state = root / "state"
            if seed == "present":
                state.write_text('{"generation": 9, "decisions": ["keep"]}', encoding="utf-8")
            (root / "cm.json").write_text(json.dumps({"generation": 7, "decisions": [{
                "pool": "pool", "workload": {"kind": "serve"}, "acceleratorIds": ["node/furiosa:0"]}]}))
            (root / "deploy.json").write_text(json.dumps({"items": [{"metadata": {
                "name": "serve", "labels": {"airm.ai-computing.io/pool": "pool"}}, "spec": {}}]}))
            env = dict(os.environ, TEST_DIR=posix(root), SEED=seed, KEDA=keda)
            command = 'export PATH="$TEST_DIR:$PATH"; exec bash "$1" "$2" "$3"'
            result = subprocess.run([BASH, "-c", command, "test", posix(HERE / "airm-install.sh"), action, target],
                                    env=env, capture_output=True, text=True, timeout=20)
            calls = (root / "calls").read_text(encoding="utf-8")
            return result, calls, state.read_text(encoding="utf-8") if state.exists() else None

    def test_reinstall_preserves_existing_decisions_and_generation(self):
        result, calls, state = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state, '{"generation": 9, "decisions": ["keep"]}')

    def test_missing_seed_is_created_and_dry_run_does_not_create(self):
        result, calls, state = self.run_install(seed="missing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state.strip(), "seed-generation-zero")
        self.assertIn("create -f", calls)
        result, calls, state = self.run_install(action="dry-run", seed="missing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(state)
        self.assertIn("--dry-run=server", calls)

    def test_seed_read_failure_stops_without_overwriting_state(self):
        result, calls, state = self.run_install(seed="error")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("/airm-placement.yaml", calls)

    def test_keda_discovery_or_read_failure_aborts_without_patches(self):
        for keda in ("discovery-error", "read-error"):
            with self.subTest(keda=keda):
                result, calls, _ = self.run_install(target="placement", keda=keda)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("patch ", calls)

    def test_keda_absence_still_allows_deployment_placement(self):
        result, calls, _ = self.run_install(target="placement", keda="absent")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("patch deployment serve", calls)
        self.assertNotIn("get scaledobjects.keda.sh", calls)


if __name__ == "__main__":
    unittest.main()
