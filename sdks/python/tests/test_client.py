import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from asgard_sdk import Client, ScanError

ENGINE = r'''
import json, os, subprocess, sys, time
request = json.load(sys.stdin)
mode = sys.argv[1]
if mode == 'sleep':
    time.sleep(60)
if mode == 'flood':
    sys.stdout.write('x' * 200000); sys.stdout.flush(); time.sleep(60)
if mode == 'stderr':
    sys.stderr.write('x' * 200000); sys.stderr.flush(); time.sleep(60)
if mode == 'malformed':
    print('{}'); sys.exit(0)
if mode == 'child':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    with open(sys.argv[2], 'w') as f: f.write(str(child.pid))
    time.sleep(60)
response = dict(protocol_version=1, engine_version='fixture-1',
    scan_id='scan-1', correlation_id=request['correlation_id'], state='ready',
    complete=True, truncated=False, findings=[], errors=[],
    capabilities=dict(profiles=['quality.file-length'], transport='single-request-stdio'))
code = 0
if request['operation'] == 'scan':
    response['state'] = 'complete'
    if mode == 'finding':
        response['findings'] = [dict(relative_path='test.py', line_count=301)]
        code = 1
    if mode == 'incomplete':
        response.update(state='incomplete', complete=False, truncated=True)
        code = 1
    if mode == 'error':
        response.update(state='error', complete=False, errors=[dict(code='invalid_request')])
        code = 2
    if mode == 'lying':
        response['errors'] = [dict(code='missing_tool')]
if mode == 'wrong-version': response['engine_version'] = 'other'
if mode == 'wrong-correlation': response['correlation_id'] = 'other'
print(json.dumps(response)); sys.exit(code)
'''


class ClientTests(unittest.TestCase):
    def client(self, mode='clean', **kwargs):
        return Client([sys.executable, '-c', ENGINE, mode], engine_version='fixture-1', **kwargs)

    def scan(self, client, **kwargs):
        return client.scan(authorized_root='/fixture', target='/fixture/source', **kwargs)

    def test_findings_and_incomplete_truth(self):
        for mode in ('clean', 'finding', 'incomplete'):
            with self.client(mode) as client:
                result = self.scan(client)
                self.assertEqual(result['complete'], mode != 'incomplete')
                self.assertEqual(bool(result['findings']), mode == 'finding')

    def test_protocol_and_engine_failures(self):
        for mode, expected in [('malformed', 'version_mismatch'), ('lying', 'malformed_response'),
            ('wrong-version', 'engine_version_mismatch'), ('wrong-correlation', 'malformed_response'),
            ('error', 'engine_error')]:
            with self.client(mode) as client, self.assertRaises(ScanError) as caught:
                self.scan(client)
            self.assertEqual(caught.exception.code, expected)
            if mode == 'error':
                self.assertEqual(caught.exception.response['errors'][0]['code'], 'invalid_request')

    def test_timeout_and_both_output_bounds(self):
        for mode, expected in [('sleep', 'timeout'), ('flood', 'output_limit'), ('stderr', 'output_limit')]:
            with self.client(mode, timeout=0.3, max_output_bytes=1024) as client:
                with self.assertRaises(ScanError) as caught:
                    self.scan(client)
                self.assertEqual(caught.exception.code, expected)
                self.assertFalse(client._active)

    def test_cancel_and_close_active_work(self):
        for close in (False, True):
            client, cancel, errors = self.client('sleep'), threading.Event(), []
            def run():
                try: self.scan(client, cancel=cancel)
                except ScanError as error: errors.append(error.code)
            thread = threading.Thread(target=run)
            thread.start()
            deadline = time.monotonic() + 3
            while not client._active and time.monotonic() < deadline: time.sleep(.005)
            self.assertTrue(client._active)
            client.close() if close else cancel.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, ['closed' if close else 'cancelled'])
            client.close()
            with self.assertRaises(ScanError) as caught: self.scan(client)
            self.assertEqual(caught.exception.code, 'closed')

    def test_child_process_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'child.pid'
            with Client([sys.executable, '-c', ENGINE, 'child', str(marker)],
                        engine_version='fixture-1', timeout=.5) as client:
                with self.assertRaises(ScanError): self.scan(client)
            pid = int(marker.read_text())
            # Linux can briefly retain a terminated orphan as a zombie.
            stat = Path(f'/proc/{pid}/stat')
            deadline = time.monotonic() + 2
            while stat.exists() and stat.read_text().split()[2] != 'Z' and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(not stat.exists() or stat.read_text().split()[2] == 'Z')

    def test_unsupported_and_missing_executable(self):
        with self.client() as client, self.assertRaises(ScanError) as caught:
            self.scan(client, profile='not-advertised')
        self.assertEqual(caught.exception.code, 'unsupported_operation')
        with Client(['/nonexistent/asgard'], engine_version='1') as client:
            with self.assertRaises(ScanError) as caught: client.handshake()
        self.assertEqual(caught.exception.code, 'engine_unavailable')

    def test_independent_instances_and_precancel(self):
        cancel = threading.Event(); cancel.set()
        with self.client() as first, self.client() as second:
            with self.assertRaises(ScanError) as caught: self.scan(first, cancel=cancel)
            self.assertEqual(caught.exception.code, 'cancelled')
            first.close()
            self.assertTrue(self.scan(second)['complete'])


if __name__ == '__main__': unittest.main()
