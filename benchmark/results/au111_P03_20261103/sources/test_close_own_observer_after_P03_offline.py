"""No real ps, signals, control writes or real stop-claim creation."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name('close_own_observer_after_P03.py')
spec = importlib.util.spec_from_file_location('close_candidate', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CloseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='offline_close_test_')
        self.addCleanup(self.tmp.cleanup)
        n = Path(self.tmp.name).resolve()
        c = n / 'continuation_slow_20261102'
        s = n / 'session_02'
        l = s / 'logger_06'
        l.mkdir(parents=True)
        (c / 'R06_pulse_P03').mkdir(parents=True)
        (n / 'globalclaims').mkdir()
        updates = dict(N=n, C=c, S=s, LOGGER=l, SCANNER=s / 'after_R06_P03_full',
                       PINS_PATH=c / 'R06_pulse_P03/close_observer_frozen_inputs.json', PINS_SHA='h',
                       STOP_CLAIM=c / 'stop_R06_root_signal.json',
                       SCANNER_SOURCE=c / 'scan_full50nm_fast_R06_after_induction_P03_once.py')
        patch = mock.patch.multiple(m, **updates)
        patch.start()
        self.addCleanup(patch.stop)
        self.data = {}
        pins = {'continuation_slow_20261102/R06_repair/close_own_observer.py': 'h'}
        for ordinal in (2, 3, 4, 5):
            rel = f'globalclaims/continuing_20261101_1939__pulse_{ordinal:02d}.claim'
            (n / rel).write_text('mock only')
            pins[rel] = 'h'
        self.data[m.PINS_PATH] = pins
        for stage, mode, target in [('prepare_induction_P03', 'prepare', 9.999999717180685e-10),
                                    ('return_induction_P03', 'return', 1.000000013351432e-10),
                                    ('recovery_return_P02_01', 'recover_return', 1.000000013351432e-10)]:
            self.data[s / stage / 'outcome.json'] = dict(status='completed', mode=mode,
                attempted_sets=11, acknowledged_sets=11, final_target_A=target)
        self.data[s / 'pulse_induction_P03/outcome.json'] = dict(status='single_pulse_knownend_30s_observed',
            pulse_ordinal=5, pulse_attempted=True, native_end_confirmed=True, writer_outcome_unknown=False,
            post_metrics={'elapsed_s': 30.0}, automatic_On=False, automatic_retry=False)
        self.data[s / 'pulse_induction_P03/feedback_readiness.json'] = dict(ready=True, error=None, writes=[])
        self.data[s / 'pulse_induction_P02/outcome.json'] = dict(status='uncertain_or_recovery_failed',
            native_end_confirmed=True, writer_outcome_unknown=False, pulse_ordinal=4)
        self.data[c / 'R06_pulse_P02/independent_readonly_recovery30/outcome.json'] = dict(
            status='completed_readonly_30s_original_guards', readonly=True, writes=[], duration_s=30.0416)
        for stage in ('repair_A05', 'induction_R06_I02', 'induction_R06_I03'):
            self.data[s / stage / 'outcome.json'] = dict(native_end_confirmed=True, writer_outcome_unknown=False)
        for stage, number in [('after_R06_P02_recovery_full', 212), ('after_R06_P03_full', 213)]:
            self.data[s / stage / 'outcome.json'] = dict(status='completed', completed_frame_confirmed=True,
                native_file_path=f'local/BM261029_{number:05d}.sxm', monotonic_ns=50)
        self.data[m.SCANNER / 'analysis/quality_report.json'] = {'integrity': dict(completed_outcome=True,
            native_TCP_wire_bitmatch=True, matched_float32_values=345600)}
        self.data[m.SCANNER / 'native_sxm_receipt.json'] = dict(outcome_sha256='h', source_double_read_sha_equal=True,
            local_reread_sha_equal=True, destination=str(m.SCANNER / 'native/file.sxm'), sha256='h')
        self.args = ['/mock/python', str(c / 'logger_fullcycle_segment06_observe_once.py')]
        self.data[c / 'R06_logger_launch.json'] = {'pid': 57780, 'args': self.args}
        self.data[l / 'READY.json'] = {'native_start_identity': 'same_native_start'}
        self.decision = c / 'R06_pulse_P03/root_stop_decision.json'
        self.data[self.decision] = dict(schema='local-au111-R06-P03-close-observer-v1', allow_stop=True,
            task_usable=True, no_further_action_chosen=True, sole_writer_confirmed=True,
            final_stage='after_R06_P03_full', scan_number=213, logger_pid=57780, scanner_pid=72085,
            scanner_source={'path': str(m.SCANNER_SOURCE), 'sha256': m.SCANNER_SHA},
            monotonic_ns=75, reason='mock completion', image_review={'path': str(c/'image.json'), 'sha256':'h'},
            native_review={'path': str(c/'native.json'), 'sha256':'h'})
        self.data[c/'image.json'] = {}; self.data[c/'native.json'] = {}
        values = {k:[0] for k in ('Scan.StatusGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','AutoApproach.OnOffGet')}
        values.update({'ZCtrl.OnOffGet':[1], 'ZCtrl.StatusGet':[2], 'Bias.Get':[-1.0],
            'ZCtrl.SetpntGet':[1.000000013351432e-10], 'SafeTip.OnOffGet':[0], 'Current.Get':[-1e-10], 'ZCtrl.ZPosGet':[-1e-7]})
        self.events = [dict(kind='datalog_status', monotonic_ns=100, parsed={'start':'same_native_start','stop':''}),
                       dict(kind='dynamic_state_poll', monotonic_ns=100, values=values)]
        self.write_events()
        self.patches = [mock.patch.object(m, 'load', side_effect=lambda p: copy.deepcopy(self.data[Path(p)])),
                        mock.patch.object(m, 'sha', return_value='h'),
                        mock.patch.object(m.time, 'monotonic_ns', return_value=100),
                        mock.patch.object(m.subprocess, 'run', side_effect=self.fake_ps),
                        mock.patch.object(m.os, 'kill')]
        self.mocks = [p.start() for p in self.patches]
        for p in self.patches: self.addCleanup(p.stop)
        self.kill = self.mocks[-1]

    def fake_ps(self, args, **kwargs):
        pid = int(args[2])
        return subprocess.CompletedProcess(args, 0 if pid == 57780 else 1,
            stdout=' '.join(self.args) if pid == 57780 else '', stderr='')

    def write_events(self):
        (m.LOGGER/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in self.events))

    def rejected(self):
        with self.assertRaises((RuntimeError, KeyError, FileExistsError)):
            m.run(self.decision, 'h')
        self.kill.assert_not_called()
        self.assertFalse(m.STOP_CLAIM.exists())

    def test_known_complete_one_signal_and_no_replay(self):
        receipt = m.run(self.decision, 'h')
        self.kill.assert_called_once_with(57780, signal.SIGINT)
        self.assertTrue(receipt['native_logger_closure_not_yet_confirmed'])
        with self.assertRaises(RuntimeError): m.run(self.decision, 'h')
        self.kill.assert_called_once()

    def test_reject_unknown_or_incomplete_history(self):
        scenarios = [('pulse_induction_P03','writer_outcome_unknown',True),
                     ('pulse_induction_P03','native_end_confirmed',False),
                     ('pulse_induction_P03','automatic_retry',True),
                     ('pulse_induction_P02','status','completed'),
                     ('pulse_induction_P02','writer_outcome_unknown',True),
                     ('return_induction_P03','acknowledged_sets',10),
                     ('prepare_induction_P03','status','failed'),
                     ('recovery_return_P02_01','status','failed'),
                     ('after_R06_P03_full','completed_frame_confirmed',False),
                     ('after_R06_P02_recovery_full','status','failed')]
        for stage,key,value in scenarios:
            with self.subTest(stage=stage,key=key):
                p=m.S/stage/'outcome.json';old=self.data[p][key];self.data[p][key]=value
                self.rejected();self.data[p][key]=old

    def test_root_decision_rejections(self):
        for key,value in [('allow_stop',False),('task_usable',False),('no_further_action_chosen',False),
                          ('sole_writer_confirmed',False),('logger_pid',1),('scanner_pid',1),('monotonic_ns',40)]:
            with self.subTest(key=key):
                old=self.data[self.decision][key];self.data[self.decision][key]=value
                self.rejected();self.data[self.decision][key]=old

    def test_live_scanner(self):
        with mock.patch.object(m,'process_command',return_value=' '.join(self.args)):self.rejected()

    def test_changed_logger_identity(self):
        with mock.patch.object(m,'process_command',return_value='other process'):self.rejected()

    def test_stale_observation(self):
        with mock.patch.object(m.time,'monotonic_ns',return_value=2000000100):self.rejected()

    def test_state_rejections(self):
        for key,value in [('Scan.StatusGet',[1]),('ZCtrl.StatusGet',[3]),('ZCtrl.OnOffGet',[0]),
                          ('SafeTip.OnOffGet',[1]),('Bias.Get',[-6.0]),('ZCtrl.SetpntGet',[1e-9])]:
            with self.subTest(key=key):
                old=self.events[1]['values'][key];self.events[1]['values'][key]=value;self.write_events()
                self.rejected();self.events[1]['values'][key]=old;self.write_events()

    def test_changed_native_start(self):
        self.events[0]['parsed']['start']='other';self.write_events();self.rejected()

    def test_sixth_pulse_rejects_old_close_plan(self):
        (m.N/'globalclaims/continuing_20261101_1939__pulse_06.claim').write_text('mock only');self.rejected()

    def test_decision_hash_mismatch(self):
        with self.assertRaises(RuntimeError):m.run(self.decision,'changed')
        self.kill.assert_not_called()

    def test_failed_signal_claim_remains_no_second_attempt(self):
        self.kill.side_effect=ProcessLookupError('mock exited')
        with self.assertRaises(ProcessLookupError):m.run(self.decision,'h')
        self.assertTrue(m.STOP_CLAIM.exists())
        with self.assertRaises(RuntimeError):m.run(self.decision,'h')
        self.kill.assert_called_once()

    def test_cli_requires_execute_and_exact_source(self):
        args = ['close', '--source-sha256', 'wrong', '--decision-json', str(self.decision),
                '--decision-sha256', 'h']
        with mock.patch.object(sys, 'argv', args), mock.patch.object(sys, 'stderr', io.StringIO()):
            with self.assertRaises(SystemExit): m.main()
        with mock.patch.object(sys, 'argv', args + ['--execute']):
            with self.assertRaisesRegex(RuntimeError, 'source SHA'): m.main()
        self.kill.assert_not_called()
        self.assertFalse(m.STOP_CLAIM.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
