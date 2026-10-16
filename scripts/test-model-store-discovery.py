#!/usr/bin/env python3
"""Offline scanner regression tests. Requires Python 3, PyYAML and bash."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = Path(__file__).resolve().parents[1] / 'manifests/model-store-discovery.yaml'
        documents = list(yaml.safe_load_all(manifest.read_text()))
        job = next(doc for doc in documents if doc and doc.get('kind') == 'CronJob')
        cls.script = job['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['args'][0]
        subprocess.run(['bash', '-n'], input=cls.script, text=True, check=True)

    def exercise(self, case):
        with tempfile.TemporaryDirectory(prefix='lmd-discovery-test-') as directory:
            root = Path(directory)
            store = root / 'store'
            if case != 'missing-root':
                (store / 'hub/models--org--model/snapshots/revision').mkdir(parents=True)
                # Old artifacts lacking provenance must not make optional probes fatal.
                (store / 'compiled/org--model/rbln/tp1').mkdir(parents=True)
                (store / 'compiled/org--model/furiosa/tp1').mkdir(parents=True)
            binaries = root / 'bin'
            binaries.mkdir()
            trace = root / 'trace.jsonl'
            kubectl = binaries / 'kubectl'
            kubectl.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['SCAN_TRACE'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1] == 'create':
    if os.environ['SCAN_CASE'] == 'create-failure': sys.exit(1)
    print('kind: ConfigMap')
if sys.argv[1] == 'apply' and os.environ['SCAN_CASE'] == 'apply-failure': sys.exit(1)
''')
            kubectl.chmod(0o700)
            for case_name, command in [('du-failure', 'du'), ('df-failure', 'df')]:
                if case == case_name:
                    fake = binaries / command
                    fake.write_text('#!/bin/sh\nexit 1\n')
                    fake.chmod(0o700)
            script = self.script.replace('/tmp/', directory + '/').replace('/mnt/store', str(store))
            result = subprocess.run(
                ['bash', '-c', script], capture_output=True, text=True, timeout=15,
                env=dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                         SCAN_TRACE=str(trace), SCAN_CASE=case))
            calls = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
            expected = [] if case in ('du-failure', 'missing-root') else ['create']
            if case not in ('du-failure', 'missing-root', 'create-failure'):
                expected.append('apply')
            self.assertEqual([call[0] for call in calls], expected, result.stderr)
            self.assertEqual(result.returncode == 0, case in ('success', 'df-failure'), result.stderr)
            if calls:
                timestamp = next(arg.split('=', 2)[2] for arg in calls[0] if arg.startswith('--from-literal=scanned_at='))
                self.assertGreater(int(timestamp), 0)
            if result.returncode == 0:
                inventory = (root / 'inventory').read_text()
                self.assertIn('org/model | revision | hf', inventory)
                self.assertIn('org/model | - | rbln', inventory)
                self.assertIn('org/model | - | furiosa', inventory)
                if case == 'df-failure':
                    self.assertEqual((root / 'capacity').read_text(), '')

    def test_publication_and_failure_boundaries(self):
        for case in ('success', 'du-failure', 'create-failure', 'apply-failure', 'missing-root', 'df-failure'):
            with self.subTest(case=case):
                self.exercise(case)


if __name__ == '__main__':
    unittest.main()
