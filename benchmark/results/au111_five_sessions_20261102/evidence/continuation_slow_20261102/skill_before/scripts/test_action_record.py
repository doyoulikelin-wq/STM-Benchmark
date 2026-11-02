"""Offline behavioral tests. All authorization, budgets, and files are synthetic."""
import ast
import contextlib
import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import action_record as tool


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clock = datetime(2026, 11, 1, 1, 0, 0, tzinfo=timezone.utc)
        self.evidence = self.root / "synthetic_evidence.txt"
        self.evidence.write_text("SYNTHETIC TEST EVIDENCE; NOT AN INSTRUMENT RECORD\n")
        self.ref = {"path": self.evidence.name, "sha256": tool.digest(self.evidence)}
        for name in ("socket", "create_connection", "getaddrinfo"):
            guard = patch.object(socket, name, side_effect=AssertionError("Network is forbidden"))
            guard.start(); self.addCleanup(guard.stop)
        self.r = self.valid_ready()

    def ts(self, seconds=0):
        return (self.clock + timedelta(seconds=seconds)).isoformat()

    def valid_ready(self):
        r = tool.load_json(tool.TEMPLATE)
        r.update(event_id="TEST-E01", session_id="TEST-S01", state_segment_id="TEST-state", operator="test", created_utc=self.ts(-10))
        r["authorization"].update(confirmed=True, evidence="Synthetic test authorization", exclusive_writer_confirmed=True,
            target_id="TEST-controller",
            commands=["Bias.Pulse"], bounds={"voltage_V": [-7, -4], "width_s": [.02, .1],
            "preparation_current_A": [1e-9, 1e-9], "resting_bias_V": [-1, -1], "x_m": [-40e-9, -20e-9], "y_m": [0, 20e-9]})
        r["budget"].update(confirmed=True, evidence="Test-only limits; not recommended defaults", max_actions_per_session=2,
            max_actions_per_stage=2, stage_id="TEST-stage", failure_definition="Unassessed or no desired effect counts as failure",
            max_consecutive_failures=2, max_session_elapsed_s=600, max_action_elapsed_s=60,
            session_started_utc=self.ts(-60), reservation_id="synthetic-only", counter_evidence=copy.deepcopy(self.ref))
        r["previous_action"].update(outcome="none", evidence="New synthetic session")
        r["target"].update(target_id="TEST-controller", controller_identity="Synthetic controller", sample_id="TEST-Au", tip_id="unknown",
            identity_evidence=copy.deepcopy(self.ref))
        r["history"].update(checked_utc=self.ts(-.5), evidence="Test history checked", manual_intervention_since_baseline=False)
        b = r["baseline"]
        b.update(state_segment_id="TEST-state", snapshot=copy.deepcopy(self.ref), image=copy.deepcopy(self.ref), interval_native_review=copy.deepcopy(self.ref),
            snapshot_utc=self.ts(-1), image_completed_utc=self.ts(-20), native_reviewed_through_utc=self.ts(-1), fresh_verified_utc=self.ts(-.5),
            max_age_s=2, full_configuration_verified=True, baseline_is_immediate=True, imaging_bias_V=-1, imaging_setpoint_A=1e-9,
            z_limits_m=[-150e-9, 0], z_margin_m=5e-9,
            signed_current_band_A=[-1.25e-9, -.75e-9], stable_observation_s=5.5, required_stable_s=5)
        b["readback"].update(bias_V=-1, setpoint_A=tool.float32(1e-9), current_A=-1e-9, xy_m=[-30e-9, 10e-9], z_m=-70e-9,
            feedback_status="On2", scan_idle=True, other_actions_idle=True, safetip_state="off",
            safetip_properties={"stored_threshold_A": 500e-12}, gain_readback={"index": 0, "filter_index": -1})
        r["prior_clipping"].update(status="none_detected", review=copy.deepcopy(self.ref))
        r["action"].update(voltage_V=-4, width_s=.02, preparation_current_A=1e-9, resting_bias_V=-1,
            stage_id="TEST-stage",
            xy_m=[-30e-9, 10e-9], estimated_elapsed_s=40, rationale="Test single exposure", hypothesis="Synthetic response test")
        r["recording"].update(sample_rate_hz=2000, sample_rate_basis="verified_native_header", logger_verified_utc=self.ts(-.5),
            module="Nanonis.DataLog", unknown_chain_limitations="Unknown physical range/bandwidth; sampled extrema are not bounds",
            configuration=copy.deepcopy(self.ref), configuration_readback=copy.deepcopy(self.ref),
            logger_max_age_s=2, estimated_remaining_s=120, required_coverage_s=60)
        r["recovery"].update(max_wait_s=30, required_stable_s=5, expected_bias_V=-1, expected_setpoint_A=1e-9,
            signed_current_band_A=[-1.25e-9, -.75e-9], max_abs_z_trend_m_per_s=10e-12, max_z_span_m=100e-12, z_trend_window_s=5)
        return r

    def completed(self):
        r = copy.deepcopy(self.r)
        r["execution"].update(attempted=True, claim_utc=self.ts(), ack_utc=self.ts(.1), observation_ended_utc=self.ts(30), elapsed_s=30,
            native_end_basis="waiting_ack_upper_bound", feedback_restored_utc=self.ts(.2), reference_returned_utc=self.ts(.3),
            recovery_elapsed_s=29.9, recovery_z_trend_m_per_s=1e-12, recovery_z_span_m=10e-12, recovery_z_observation_s=5,
            reference_return_evidence=copy.deepcopy(self.ref),
            ack_status="zero_error_waiting_ack", native_end_known=True, bias_restored=True, feedback_restored=True,
            claim=copy.deepcopy(self.ref), ack=copy.deepcopy(self.ref), immediate_readback=copy.deepcopy(self.ref), final_readback=copy.deepcopy(self.ref),
            final_state=copy.deepcopy(r["baseline"]["readback"]), effective_stable_window_s=5.1, required_final_stable_s=5)
        r["budget"].update(actions_attempted_after=1, stage_actions_attempted_after=1, consecutive_failures_after=1)
        r["recording"].update(complete=True, files=[copy.deepcopy(self.ref)])
        return r

    def check(self, r=None, phase="ready", clock=None):
        return tool.validate(self.r if r is None else r, phase, base_dir=self.root, now=clock or self.clock)

    def reject(self, change, phrase):
        r = copy.deepcopy(self.r); change(r)
        errors, _ = self.check(r)
        self.assertTrue(any(phrase in e for e in errors), errors)

    def test_template_shape_valid_but_never_ready(self):
        template = tool.load_json(tool.TEMPLATE)
        self.assertEqual(tool.structural_errors(template, tool.load_json(tool.SCHEMA)), [])
        errors, _ = self.check(template)
        self.assertTrue(any("budget" in x for x in errors))
        self.assertTrue(any("authorization" in x for x in errors))

    def test_valid_record_and_offline_boundaries(self):
        self.assertEqual(self.check()[0], [])
        imports = [n for n in ast.walk(ast.parse(Path(tool.__file__).read_text())) if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name.split('.')[0] for n in imports for a in (n.names if isinstance(n, ast.Import) else [])}
        self.assertFalse(names & {"socket", "subprocess", "requests", "urllib", "http"})

    def test_all_missing_budgets_reject(self):
        for k in ("max_actions_per_session", "max_actions_per_stage", "max_consecutive_failures", "max_session_elapsed_s", "max_action_elapsed_s"):
            with self.subTest(k=k):
                self.reject(lambda r: r["budget"].update({k: None}), "budget." + k)

    def test_budget_limits_and_stop(self):
        for values, phrase in [({"actions_attempted_before": 2}, "session action"),
                ({"stage_actions_attempted_before": 2, "actions_attempted_before": 2, "max_actions_per_session": 3}, "stage action"),
                ({"consecutive_failures_before": 2, "actions_attempted_before": 2, "max_actions_per_session": 3}, "consecutive failure"),
                ({"max_session_elapsed_s": 90}, "session time"), ({"max_action_elapsed_s": 30}, "duration"),
                ({"stop_requested": True}, "stop condition"), ({"repair_success_already_achieved": True}, "stop condition")]:
            with self.subTest(values=values): self.reject(lambda r: r["budget"].update(values), phrase)

    def test_authorization_required_and_bounds(self):
        self.reject(lambda r: r["authorization"].update(confirmed=False), "authorization")
        self.reject(lambda r: r["authorization"].update(commands=[]), "scope")
        self.reject(lambda r: r["action"].update(voltage_V=-8), "outside bounds")
        self.reject(lambda r: r["action"].update(xy_m=[0, 0]), "XY outside")
        self.reject(lambda r: r["action"].update(width_s=.001), "20–100 ms")

    def test_no_missing_or_unknown_previous_execution(self):
        self.reject(lambda r: r["previous_action"].update(outcome="unknown"), "previous action outcome unknown")
        self.reject(lambda r: r["execution"].update(claim_utc=self.ts(-1)), "must count as attempted")

    def test_unknown_ack_consumes_budget_and_never_replays(self):
        r = self.completed(); r["execution"].update(ack_status="timeout", native_end_known=None)
        r["budget"].update(actions_attempted_after=0, consecutive_failures_after=0)
        errors, _ = self.check(r, "draft", self.clock + timedelta(seconds=60))
        self.assertTrue(any("consume one action" in e for e in errors))
        self.assertTrue(any("consecutive failure" in e for e in errors))
        r["budget"].update(actions_attempted_after=1, consecutive_failures_after=1)
        self.assertEqual(self.check(r, "draft")[0], [])
        self.assertTrue(any("no replay" in e for e in self.check(r, "ready")[0]))
        r["labels"]["L0"].update(status="supported", evidence=[copy.deepcopy(self.ref)])
        self.assertTrue(any("L0" in e for e in self.check(r, "draft")[0]))

    def test_manual_intervention_requires_new_image(self):
        for flag in (True, None):
            self.reject(lambda r: r["history"].update(manual_intervention_since_baseline=flag), "manual intervention")
        self.reject(lambda r: r["history"].update(last_manual_intervention_utc=self.ts(-5)), "predates last manual")
        self.reject(lambda r: r["baseline"].update(baseline_is_immediate=False), "immediate pre-action")

    def test_clipping_handled_requires_new_baseline(self):
        self.reject(lambda r: r["prior_clipping"].update(status="unknown"), "not reviewed")
        self.reject(lambda r: r["prior_clipping"].update(status="detected", last_detected_utc=self.ts(-5)), "unresolved")
        self.reject(lambda r: r["prior_clipping"].update(status="detected", handled=True, resolution="Reviewed", last_detected_utc=self.ts(-5)), "no new post-event")
        r = copy.deepcopy(self.r)
        r["prior_clipping"].update(status="detected", handled=True, resolution="New post-event baseline established; peaks censored", last_detected_utc=self.ts(-30))
        self.assertEqual(self.check(r)[0], [])

    def test_freshness_and_coverage(self):
        self.reject(lambda r: r["baseline"].update(snapshot_utc=self.ts(-10)), "snapshot stale")
        self.reject(lambda r: r["baseline"].update(native_reviewed_through_utc=self.ts(-10)), "interval review stale")
        self.reject(lambda r: r["recording"].update(logger_verified_utc=self.ts(-3)), "stale")
        self.reject(lambda r: r["recording"].update(estimated_remaining_s=20), "coverage")

    def test_sample_rate_and_no_peak_bound_claim(self):
        self.reject(lambda r: r["recording"].update(sample_rate_hz=999), "less than 1 kHz")
        r = copy.deepcopy(self.r); r["recording"]["sample_rate_hz"] = 1000
        errors, warnings = self.check(r)
        self.assertFalse(errors); self.assertTrue(any("coarsely" in w for w in warnings))
        self.reject(lambda r: r["recording"].update(sampled_extrema_are_physical_bounds=True), "constant")

    def test_readback_and_preparation_are_separate(self):
        self.reject(lambda r: r["baseline"]["readback"].update(setpoint_A=20e-12), "setpoint mismatch")
        self.reject(lambda r: r["baseline"].update(imaging_setpoint_A=100e-12), "preparation_changes_review")
        r = copy.deepcopy(self.r); r["baseline"].update(imaging_setpoint_A=100e-12, preparation_changes_review="Documented preparation interval")
        r["recovery"]["expected_setpoint_A"] = 100e-12
        self.assertEqual(self.check(r)[0], [])

    def test_nominal_authorization_exact_binary32_readback(self):
        self.assertEqual(self.r["authorization"]["bounds"]["preparation_current_A"], [1e-9, 1e-9])
        self.assertNotEqual(self.r["baseline"]["readback"]["setpoint_A"], 1e-9)
        self.assertEqual(self.check()[0], [])
        self.reject(lambda r: r["baseline"]["readback"].update(setpoint_A=1e-9), "exact binary32")
        self.reject(lambda r: r["action"].update(voltage_V=1e300), "not representable")

    def test_schema_rejects_bool_as_number_negative_nan_inf_and_duplicate(self):
        for value in (True, float('nan'), float('inf')):
            self.reject(lambda r: r["action"].update(width_s=value), "expected")
        self.reject(lambda r: r["budget"].update(actions_attempted_before=-1), "minimum")
        for raw in ('{"x":NaN}', '{"x":1e400}', '{"x":1,"x":2}'):
            f = self.root / "bad.json"; f.write_text(raw)
            with self.assertRaises(ValueError): tool.load_json(f)

    def test_hash_and_unknown_field_rejection(self):
        self.reject(lambda r: r["baseline"]["snapshot"].update(sha256="0" * 64), "SHA256")
        self.reject(lambda r: r["action"].update(unreviewed_writer=True), "unexpected field")

    def test_l3_independent_of_l4(self):
        r = self.completed(); r["labels"]["L3"].update(status="supported", evidence=[copy.deepcopy(self.ref)])
        self.recheck(r)
        self.assertEqual(self.check(r, "completed", self.clock + timedelta(seconds=60))[0], [])
        r["labels"]["L4"].update(status="supported", evidence=[copy.deepcopy(self.ref)])
        self.assertTrue(any("independent chemical" in e for e in self.check(r, "completed")[0]))

    def test_cycle_claim_rejects_intervention_and_l4_only(self):
        r = self.completed(); r["decision"]["verified_repair_cycle"] = True
        self.assertTrue(any("repair cycle" in e for e in self.check(r, "draft")[0]))
        r["intent"] = "repair"; r["decision"].update(before_bad_established=True, matched_imaging_conditions=True)
        r["decision"].update(causal_valid=True, causal_evidence=copy.deepcopy(self.ref))
        self.recheck(r)
        for k in ("L2", "L3"): r["labels"][k].update(status="supported", evidence=[copy.deepcopy(self.ref)])
        self.assertEqual(self.check(r, "completed", self.clock + timedelta(seconds=60))[0], [])
        r["history"]["manual_intervention_since_baseline"] = True
        self.assertTrue(any("repair cycle" in e for e in self.check(r, "draft")[0]))

    def recheck(self, r):
        r["execution"]["scan_started_utc"] = self.ts(31)
        r["decision"].update(task_criteria="Synthetic matched two-feature task", matched_task_criteria=True,
            independent_recheck_without_intervention=True, recheck_evidence=copy.deepcopy(self.ref), recheck_completed_utc=self.ts(50))

    def test_target_stage_z_and_acquisition_evidence(self):
        self.reject(lambda r: r["authorization"].update(target_id="another"), "target identity mismatch")
        self.reject(lambda r: r["action"].update(stage_id="another"), "stage mismatch")
        self.reject(lambda r: r["baseline"]["readback"].update(z_m=-1e-9), "Z endpoint")
        self.reject(lambda r: r["recording"]["configuration_readback"].update(sha256="0"*64), "SHA256")
        self.reject(lambda r: r["recording"].update(unknown_chain_limitations=None), "unknown_chain_limitations")

    def test_native_end_timing_is_not_post_observation(self):
        r = self.completed(); r["execution"].update(native_end_basis="observed_native_end", native_end_utc=self.ts(.02))
        self.assertEqual(self.check(r, "completed", self.clock+timedelta(seconds=60))[0], [])
        r["execution"]["native_end_utc"] = self.ts(1)
        self.assertTrue(any("between claim and waiting ACK" in e for e in self.check(r, "completed", self.clock+timedelta(seconds=60))[0]))
        r["execution"].update(native_end_basis="waiting_ack_upper_bound", native_end_utc=self.ts(.02))
        self.assertTrue(any("not an exact" in e for e in self.check(r, "completed", self.clock+timedelta(seconds=60))[0]))

    def test_recovery_timeout_z_trend_and_scan_order(self):
        for values, phrase in [({"recovery_elapsed_s":31}, "recovery_elapsed_s"), ({"recovery_z_trend_m_per_s":1e-9}, "Z trend"),
                              ({"scan_started_utc":self.ts(1)}, "scan before recovery")]:
            r=self.completed();r["execution"].update(values)
            self.assertTrue(any(phrase in e for e in self.check(r,"completed",self.clock+timedelta(seconds=60))[0]))

    def test_timestamp_and_scope_cross_field_regressions(self):
        for values, phrase in [({"observation_ended_utc":self.ts(1000)}, "timestamp-derived action budget"),
                              ({"recovery_elapsed_s":.001}, "recovery_elapsed_s inconsistent"),
                              ({"recovery_z_observation_s":500}, "exceeds observed feedback-on span")]:
            with self.subTest(values=values):
                r=self.completed();r["execution"].update(values)
                self.assertTrue(any(phrase in e for e in self.check(r,"completed",self.clock+timedelta(seconds=2000))[0]))
        self.reject(lambda r:r["budget"].update(stage_actions_attempted_before=1), "stage attempts exceed")
        self.reject(lambda r:r["budget"].update(consecutive_failures_before=1), "consecutive failures exceed")

    def test_no_unattempted_success_or_ack_only_failure_reset(self):
        self.reject(lambda r: r["execution"].update(native_end_known=True), "result fields")
        r=self.completed();r["budget"].update(consecutive_failures_before=1,consecutive_failures_after=0)
        r["labels"]["L2"]["status"]="not_supported"
        self.assertTrue(any("consecutive failure" in e for e in self.check(r,"draft")[0]))
        r["decision"]["assessment_for_budget"]="successful"
        self.assertTrue(any("not evidenced success" in e for e in self.check(r,"draft")[0]))

    def test_completed_restoration_and_stable_window(self):
        r = self.completed(); r["execution"]["final_state"]["safetip_state"] = "on"
        self.assertTrue(any("safetip_state" in e for e in self.check(r, "completed", self.clock+timedelta(seconds=60))[0]))
        r = self.completed(); r["execution"]["effective_stable_window_s"] = 4
        self.assertTrue(any("stable window" in e for e in self.check(r, "completed", self.clock+timedelta(seconds=60))[0]))

    def test_cli_init_prepare_and_no_overwrite(self):
        output, source, receipt = [self.root / x for x in ("init.json", "source.json", "receipt.json")]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), patch.object(tool, "utc_now", return_value=self.clock):
            self.assertEqual(tool.main(["init", str(output), "--event-id", "TEST", "--session-id", "TEST"]), 0)
            self.assertEqual(tool.main(["init", str(output), "--event-id", "TEST", "--session-id", "TEST"]), 2)
            self.assertEqual(tool.main(["prepare", str(output), "--output", str(receipt)]), 1)
            self.assertFalse(receipt.exists())
            tool.write_new(source, self.r)
            self.assertEqual(tool.main(["prepare", str(source), "--output", str(receipt)]), 0)
            self.assertEqual(tool.main(["prepare", str(source), "--output", str(receipt)]), 2)
        data = tool.load_json(receipt)
        self.assertFalse(data["execution_permitted"])
        self.assertEqual(data["hardware_commands_performed"], 0)
        self.assertFalse(data["attempt_budget_reservation"]["global_ledger_atomically_reserved"])
        self.assertEqual(data["command_for_review_only"], ["Bias.Pulse", [1, .02, -4, 1, 2]])

    def local_record(self):
        r = tool.apply_profile(copy.deepcopy(self.r), "local-au111")
        r["action"]["strategy_id"] = "pulse-strategy-A"
        return r

    def local_history(self, r, pulses, total=None, boundary=0, pulse_boundary=None):
        total = pulses if total is None else total
        pulse_boundary = boundary if pulse_boundary is None else pulse_boundary
        r["budget"].update(actions_attempted_before=total, consecutive_failures_before=total-boundary)
        r["local_au111"].update(pulse_attempts_before=pulses, consecutive_no_improvement_before=pulses-pulse_boundary,
            last_improvement_action_attempt_before=boundary,last_improvement_pulse_attempt_before=pulse_boundary)
        if boundary:
            r["local_au111"]["last_improvement_evidence"] = copy.deepcopy(self.ref)

    def local_review(self, r, through, pulses=None, strategy="pulse-strategy-A"):
        pulses=through if pulses is None else pulses
        r["local_au111"]["strategy_review"].update(evidence=copy.deepcopy(self.ref), reviewed_utc=self.ts(-2),
            reviewed_through_action_attempt=through, reviewed_through_pulse_attempt=pulses,
            consecutive_no_improvement_at_review=pulses-r["local_au111"]["last_improvement_pulse_attempt_before"],
            decision="continue_pulse", next_strategy_id=strategy, rationale="Synthetic strategy review, no automatic execution")

    def test_local_init_policy_does_not_authorize_event_or_invent_shaper(self):
        f=self.root/"local.json"
        with contextlib.redirect_stdout(io.StringIO()), patch.object(tool,"utc_now",return_value=self.clock):
            self.assertEqual(tool.main(["init",str(f),"--event-id","TEST","--session-id","TEST","--profile","local-au111"]),0)
        r=tool.load_json(f);local=r["local_au111"]
        self.assertEqual((local["max_pulses_per_session"],local["review_after_consecutive_no_improvement"],local["required_safetip_state"]),(6,2,"off"))
        self.assertIsNone(r["budget"]["max_actions_per_session"])
        self.assertIsNone(r["authorization"]["confirmed"])
        self.assertTrue(self.check(r)[0])
        self.assertIsNone(tool.load_json(tool.LOCAL_PROFILE)["default_tipshaper_displacement_m"])

    def test_local_require_profile_and_generic_legacy_preservation(self):
        legacy=copy.deepcopy(self.r);legacy.pop("profile");legacy["action"].pop("strategy_id",None)
        self.assertFalse(self.check(legacy)[0])
        self.assertTrue(tool.validate(legacy,"ready",base_dir=self.root,now=self.clock,required_profile="local-au111")[0])
        legacy["baseline"]["readback"]["safetip_state"]="on"
        self.assertFalse(self.check(legacy)[0])
        r=self.local_record();r["baseline"]["readback"]["safetip_state"]="on"
        self.assertTrue(any("SafeTip must already be Off" in e for e in self.check(r)[0]))
        r["profile"]="generic"
        self.assertTrue(any("downgraded" in e for e in self.check(r)[0]))

    def test_local_two_without_improvement_requires_review_not_hard_stop(self):
        r=self.local_record();self.local_history(r,2)
        self.assertTrue(any("require strategy review" in e for e in self.check(r)[0]))
        self.local_review(r,2)
        self.assertEqual(self.check(r)[0],[])
        self.local_history(r,3)
        self.assertEqual(self.check(r)[0],[])
        self.local_history(r,4)
        self.assertTrue(any("require strategy review" in e for e in self.check(r)[0]))
        self.local_review(r,4)
        self.assertEqual(self.check(r)[0],[])

    def test_local_six_pulse_cap_survives_new_strategy_and_other_actions(self):
        r=self.local_record();self.local_history(r,5,total=7);self.local_review(r,7,pulses=5)
        self.assertEqual(self.check(r)[0],[])  # Two other audited conditioning actions are not pulses.
        self.local_history(r,6,total=8);self.local_review(r,8,pulses=6,strategy="new-voltage")
        r["action"].update(strategy_id="new-voltage",voltage_V=-6,stage_id="new-stage")
        r["budget"]["stage_id"]="new-stage"
        self.assertTrue(any("six-pulse session cap" in e for e in self.check(r)[0]))
        r["action"]["command"]="TipShaper.Start"
        self.assertTrue(any("constant" in e for e in self.check(r)[0]))

    def test_local_shaper_is_not_a_failed_pulse_and_can_establish_improvement_boundary(self):
        r=self.local_record();self.local_history(r,1,total=2)
        self.assertEqual(r["local_au111"]["consecutive_no_improvement_before"],1)
        self.assertEqual(self.check(r)[0],[])  # A separate shaper attempt does not trigger the two-pulse review.
        self.local_history(r,2,total=3)
        self.assertTrue(any("require strategy review" in e for e in self.check(r)[0]))
        self.local_review(r,3,pulses=2)
        self.assertEqual(self.check(r)[0],[])
        self.local_history(r,2,total=4,boundary=4,pulse_boundary=2)  # Evidenced external improvement, not a pulse reset.
        self.assertTrue(any("improvement boundary" in e for e in self.check(r)[0]))  # Old review cannot cross it.
        r["local_au111"]["strategy_review"]=tool.load_json(tool.LOCAL_PROFILE)["local_record_defaults"]["strategy_review"]
        self.assertEqual(self.check(r)[0],[])
        self.assertEqual(r["local_au111"]["pulse_attempts_before"],2)

    def test_local_review_hash_time_boundary_and_decision(self):
        r=self.local_record();self.local_history(r,2);self.local_review(r,2)
        for change,phrase in [(lambda x:x["local_au111"]["strategy_review"]["evidence"].update(sha256="0"*64),"SHA256"),
                (lambda x:x["local_au111"]["strategy_review"].update(reviewed_utc=self.ts(1)),"precede"),
                (lambda x:x["local_au111"]["strategy_review"].update(reviewed_through_action_attempt=3),"future attempt"),
                (lambda x:x["local_au111"]["strategy_review"].update(decision="consider_other_strategy"),"did not select"),
                (lambda x:x["action"].update(strategy_id="unreviewed"),"differs")]:
            bad=copy.deepcopy(r);change(bad)
            self.assertTrue(any(phrase in e for e in self.check(bad)[0]))
        self.local_history(r,5,boundary=3)  # Old review at attempt2 cannot cover new streak after improvement3.
        self.assertTrue(any("improvement boundary" in e for e in self.check(r)[0]))

    def test_local_counters_only_evidenced_improvement_can_reset_streak(self):
        r=tool.apply_profile(self.completed(),"local-au111");r["action"]["strategy_id"]="pulse-strategy-A"
        self.local_history(r,2);self.local_review(r,2)
        r["budget"].update(actions_attempted_after=3,consecutive_failures_after=3)
        r["local_au111"].update(pulse_attempts_after=3,consecutive_no_improvement_after=3,last_improvement_action_attempt_after=0,last_improvement_pulse_attempt_after=0)
        self.assertEqual(self.check(r,"completed",self.clock+timedelta(seconds=60))[0],[])
        bad=copy.deepcopy(r);bad["local_au111"]["pulse_attempts_after"]=0
        self.assertTrue(any("cumulative pulse" in e for e in self.check(bad,"draft")[0]))
        bad=copy.deepcopy(r);bad["local_au111"].update(consecutive_no_improvement_after=0,last_improvement_action_attempt_after=3,last_improvement_pulse_attempt_after=3)
        self.assertTrue(any("only evidenced L2" in e for e in self.check(bad,"draft")[0]))
        r["labels"]["L2"].update(status="supported",evidence=[copy.deepcopy(self.ref)])
        r["local_au111"].update(consecutive_no_improvement_after=0,last_improvement_action_attempt_after=3,last_improvement_pulse_attempt_after=3)
        self.assertEqual(self.check(r,"completed",self.clock+timedelta(seconds=60))[0],[])
        self.assertEqual(r["budget"]["consecutive_failures_after"],3)  # Partial improvement is not L3 task success.
        r["execution"].update(ack_status="unknown",native_end_known=None)
        self.assertTrue(self.check(r,"completed",self.clock+timedelta(seconds=60))[0])


if __name__ == "__main__":
    unittest.main()
