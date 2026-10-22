"""Offline adversarial tests. No sockets or instrument writes are made."""
import math
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from stm_bench.demo import DemoBackend, discover_channels, roi_frame, props_set
from stm_bench.demo_identity import verify_inventory
from stm_bench.demo_wire import encode, decode, ProtocolError


class TestDemoRecipes(unittest.TestCase):
    def test_dynamic_channels_and_ambiguity(self):
        names = ['Unused']*100
        names[4], names[89] = 'Current (A)', 'Z (m)'
        self.assertEqual(discover_channels(names, [4, 89]), {'current': 4, 'z': 89})
        names[30] = 'Z (m)'
        self.assertEqual(discover_channels(names, [4, 89])['z'], 89)
        with self.assertRaises(RuntimeError): discover_channels(names)

    def test_roi_rotates_and_stays_in_survey(self):
        frame = dict(cx_m=1e-9, cy_m=2e-9, width_m=10e-9, height_m=8e-9, angle_deg=90)
        detail = roi_frame(frame, dict(x=.7, y=.5, size=.3, basis='observed'))
        self.assertAlmostEqual(detail['cx_m'], 1e-9, places=18)
        self.assertAlmostEqual(detail['cy_m'], 4e-9, places=18)
        self.assertAlmostEqual(detail['width_m'], 3e-9, places=18)
        with self.assertRaises(ValueError): roi_frame(frame, dict(x=.95, y=.5, size=.3))
        with self.assertRaises(PermissionError): roi_frame(frame, dict(x=math.nan, y=.5, size=.3))

    def test_write_limits_and_exact_original_restoration(self):
        c = DemoBackend.__new__(DemoBackend)
        c.restore_values = {'ZCtrl.GainSet': [2e-10, .001, 2e-7]}
        c.channels = {'current': 0, 'z': 89}; c.pixels = 64
        with self.assertRaises(PermissionError): c._validate_write('Bias.Pulse', [1])
        with self.assertRaises(PermissionError): c._validate_write('ZCtrl.GainSet', [2e-10, .001, 2e-7])
        c._validate_write('ZCtrl.GainSet', [2e-10, .001, 2e-7], restoring=True)
        with self.assertRaises(PermissionError): c._validate_write('ZCtrl.GainSet', [3e-10, .001, 3e-7], restoring=True)
        with self.assertRaises(PermissionError): c._validate_write('Scan.Action', [0, 0])
        with self.assertRaises(PermissionError): c._validate_write('ZCtrl.Withdraw', [1, -1])
        with self.assertRaises(PermissionError): c._validate_write('Scan.BufferSet', [[0, 30], 64, 64])

    def test_props_enum_conversion(self):
        p = [0, 1, 2, 3, 'abc', 0, '', 0, 0, [], 0, [], 0, 0, {}, 2]
        self.assertEqual(props_set(p), [2, 1, 3, 'abc', '', [], 3])

    def test_protocol_rejects_truncated_body(self):
        self.assertEqual(encode(['H'], [1]), b'\x00\x01')
        with self.assertRaises(ProtocolError): decode(['f'], b'\0'*8)


class TestApproachEvidence(unittest.TestCase):
    def client(self, statuses):
        c = DemoBackend.__new__(DemoBackend)
        c.prepared = True; c.retracted = True; c.broken = False; c.owned_approach = False
        c._idle = lambda: None; c.event = lambda *a, **kw: None
        c.writes = []; c._write = lambda n, a, **kw: c.writes.append((n, a)); c._wait = lambda *a: 0
        seq = iter(statuses)
        def call(name):
            return next(seq) if name == 'AutoApproach.OnOffGet' else {'Current.Get': 5e-9, 'ZCtrl.ZPosGet': 0., 'ZCtrl.OnOffGet': 1}[name]
        c._call = call
        return c

    def test_actual_running_stopped_required(self):
        c = self.client([1, 0])
        with patch('stm_bench.demo.time.sleep'):
            result = c.approach()
        self.assertTrue(result['completed']); self.assertFalse(c.retracted)
        self.assertEqual([x['status'] for x in result['readings']], [1, 0])

    def test_ack_feedback_on_without_lifecycle_is_not_approach(self):
        c = self.client([0, 0])
        ticks = iter([0, 1, 2, 46])
        with patch('stm_bench.demo.time.monotonic', side_effect=lambda: next(ticks)), patch('stm_bench.demo.time.sleep'):
            with self.assertRaises(TimeoutError): c.approach()
        self.assertIn(('AutoApproach.OnOffSet', [0]), c.writes)
        self.assertTrue(c.retracted)


class TestCleanup(unittest.TestCase):
    def test_retraction_requires_numerical_endpoint(self):
        c = DemoBackend.__new__(DemoBackend)
        c.initial = {'original': True}; c.restore_values = {'original': True}
        c.owned_approach = False; c.owned_scan = False
        c._idle = lambda: None; c._wait = lambda *a: None; c.event = lambda *a, **kw: None
        writes = []; c._write = lambda *a, **kw: writes.append((a, kw))
        c._call = lambda name: 7.5e-7 if name == 'ZCtrl.ZPosGet' else [3e-6, 3e-6, 1.5e-6]
        self.assertTrue(c.retract()['verified_endpoint'])
        self.assertTrue(writes[0][1]['restoring'])
        c._call = lambda name: 0 if name == 'ZCtrl.ZPosGet' else [3e-6, 3e-6, 1.5e-6]
        with self.assertRaises(RuntimeError): c.retract()
        self.assertFalse(c.retracted)

    def test_public_mutations_require_saved_initial_state(self):
        c = DemoBackend.__new__(DemoBackend)
        c.initial = None; c.restore_values = {}; c.prepared = False
        c._idle = lambda: self.fail('No instrument access before reset guard')
        with self.assertRaises(PermissionError): c.configure({'setpoint_A': 5e-9})
        with self.assertRaises(PermissionError): c.scan('survey')
        with self.assertRaises(PermissionError): c.retract()

    def test_reserved_budget_allows_only_validated_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            c = DemoBackend.__new__(DemoBackend)
            c.out = Path(directory); (c.out/'raw').mkdir()
            c.lock = threading.RLock(); c.broken = False; c.closed = False
            c.write_count = 224; c.sequence = 0; c.restore_values = {}
            c._guard = lambda: {'verified': True}; c.event = lambda *a, **kw: None
            class Transport:
                response_header = b'\0'*40
                def exchange(self, *args): return b'\0'*8, .1
            c.transport = Transport()
            with self.assertRaises(PermissionError): c._write('ZCtrl.OnOffSet', [1])
            c._write('ZCtrl.Withdraw', [1, 5000], restoring=True)
            self.assertEqual(c.write_count, 225)
            with self.assertRaises(PermissionError): c._write('ZCtrl.Withdraw', [1, -1], restoring=True)
            c.write_count = 256
            with self.assertRaises(PermissionError): c._write('ZCtrl.Withdraw', [1, 5000], restoring=True)

    def test_reset_channel_failure_closes_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            c = DemoBackend.__new__(DemoBackend)
            c.out = Path(directory); c.prepared = False; c.initial = None; c.restore_values = {}
            c.broken = False; c.closed = False; c.write_count = 0; c.cleanup_result = None
            c._idle = lambda: None; c._state = lambda: {'Scan.BufferGet': [1, [0], 64, 64]}
            c._call = lambda *a: [0, 0, []]; c.event = lambda *a, **kw: None
            c._write = lambda *a, **kw: self.fail('No writes allowed after channel discovery failure')
            class Transport:
                def __exit__(self): pass
            c.transport = Transport()
            with self.assertRaises(RuntimeError): c.reset()
            result = c.close()
            self.assertTrue(result['restored']); self.assertEqual(result['write_count'], 0)

    def test_uncertain_transport_cleanup_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            c = DemoBackend.__new__(DemoBackend)
            c.out = Path(directory); c.closed = False; c.broken = True; c.write_count = 3
            c.event = lambda *a, **kw: None
            class Transport:
                def __exit__(self): pass
            c.transport = Transport()
            with self.assertRaises(ConnectionError): c.close()
            result = json.loads((c.out/'cleanup.json').read_text())
            self.assertFalse(result['restored']); self.assertTrue(c.closed)


class TestIdentity(unittest.TestCase):
    def inventory(self):
        procs = {1: dict(pid=1, name='Nanonis Mimea.exe', exe=r'C:\Nanonis\Mimea\Nanonis Mimea.exe', create_time=10),
                 2: dict(pid=2, name='Sim-Engine.exe', exe=r'C:\Nanonis\Mimea\RT-Engine\Sim\Sim-Engine.exe', create_time=11)}
        conns = [dict(pid=1, status='LISTEN', local_ip='127.0.0.1', local_port=6501, remote_ip='', remote_port=0)]
        for port in range(6555, 6558):
            conns += [dict(pid=1, status='ESTABLISHED', local_ip='127.0.0.1', local_port=port+10000, remote_ip='127.0.0.1', remote_port=port),
                      dict(pid=2, status='ESTABLISHED', local_ip='127.0.0.1', local_port=port, remote_ip='127.0.0.1', remote_port=port+10000)]
        return procs, conns

    def test_good_identity_and_rejections(self):
        p, c = self.inventory(); identity = verify_inventory(p, c)
        self.assertEqual(identity['reciprocal_connections'], 3)
        with self.assertRaises(PermissionError): verify_inventory(p, c, host='192.168.1.2')
        changed = dict(identity, sim_created=12)
        with self.assertRaises(PermissionError): verify_inventory(p, c, expected=changed)
        c.append(dict(pid=1, status='ESTABLISHED', local_ip='127.0.0.1', local_port=6502, remote_ip='127.0.0.1', remote_port=54321))
        with self.assertRaises(PermissionError): verify_inventory(p, c, client_port=12345)

    def test_remote_sim_link_and_wrong_install_blocked(self):
        p, c = self.inventory(); c[1]['remote_ip'] = '10.0.0.1'
        with self.assertRaises(PermissionError): verify_inventory(p, c)
        p, c = self.inventory(); p[2]['exe'] = r'C:\Other\Mimea\RT-Engine\Sim\Sim-Engine.exe'
        with self.assertRaises(PermissionError): verify_inventory(p, c)


if __name__ == '__main__': unittest.main()
