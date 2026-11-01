#!/usr/bin/env python3
"""Standard-library, local-file-only pulse record preparation; NEVER an executor.

init creates an unconfigured record; validate checks draft/ready/completed records;
prepare writes a non-overwriting offline review receipt after ready validation.
No instrument imports, sockets, shell commands, retries, or hardware permission.
Readiness is an audit of supplied evidence, not verification of live hardware,
authorization authenticity, exclusive ownership, or a global action counter.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ASSETS = Path(__file__).resolve().parents[1] / "assets"
SCHEMA = ASSETS / "action-record.schema.json"
TEMPLATE = ASSETS / "action-record.template.json"
LOCAL_PROFILE = ASSETS / "local-au111.profile.json"


def apply_profile(record, name):
    """Initialize only local policy values; never authorize an event or target."""
    record["profile"] = name
    if name == "local-au111":
        policy = load_json(LOCAL_PROFILE)
        if (policy["max_pulses_per_session"], policy["review_after_consecutive_no_improvement"],
                policy["required_safetip_state"]) != (6, 2, "off"):
            raise ValueError("Local policy differs from the user-confirmed 6/2/Off scope")
        record["local_au111"] = policy["local_record_defaults"]
        record["budget"].update(confirmed=True, evidence=policy["source"],
            max_actions_per_session=None, max_actions_per_stage=None, max_consecutive_failures=None,
            failure_definition="No ACK/strategy-change reset. The separate local L2 improvement streak triggers strategy review after two; pulse cap remains six.")
    elif name != "generic":
        raise ValueError("Unknown profile")
    return record


def load_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key: " + key)
            value[key] = item
        return value
    def bad_constant(value):
        raise ValueError("Nonfinite JSON number: " + value)
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Nonfinite JSON number: " + value)
        return result
    data = Path(path).read_bytes()
    if len(data) > 2_000_000:
        raise ValueError("Record/schema exceeds 2 MB")
    return json.loads(data, object_pairs_hook=unique, parse_constant=bad_constant, parse_float=finite_float)


def stamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamp must include timezone")
    return result.astimezone(timezone.utc)


def utc_now():
    return datetime.now(timezone.utc)


def float32(value):
    """Exact Nanonis scalar encoding expectation; never a physical tolerance."""
    return None if value is None else struct.unpack(">f", struct.pack(">f", value))[0]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def structural_errors(value, schema, path="$", root=None):
    """Validate only the deliberately small JSON Schema subset used by this asset.

    Unknown schema keywords fail closed; this is not a general JSON Schema engine.
    The asset is also consumable by standard Draft 2020-12 validators.
    """
    root = schema if root is None else root
    allowed = {"$schema", "$id", "$defs", "$ref", "title", "description", "type",
               "properties", "required", "additionalProperties", "items", "enum",
               "const", "minimum", "exclusiveMinimum", "maximum", "minItems",
               "maxItems", "minLength", "pattern", "format"}
    unknown = set(schema) - allowed
    if unknown:
        return [f"{path}: unsupported schema keywords {sorted(unknown)}"]
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/") or ref[8:] not in root.get("$defs", {}):
            return [f"{path}: unsupported schema reference"]
        return structural_errors(value, root["$defs"][ref[8:]], path, root)
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {"null": lambda x: x is None, "boolean": lambda x: type(x) is bool,
              "string": lambda x: isinstance(x, str), "object": lambda x: isinstance(x, dict),
              "array": lambda x: isinstance(x, list), "integer": lambda x: type(x) is int,
              "number": lambda x: type(x) is int or (type(x) is float and math.isfinite(x))}
    if kinds and not any(checks.get(k, lambda _: False)(value) for k in kinds):
        return [f"{path}: expected {kinds}, got {type(value).__name__}"]
    errors = []
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        errors.append(f"{path}: unexpected constant")
    if "enum" in schema and not any(type(value) is type(x) and value == x for x in schema["enum"]):
        errors.append(f"{path}: outside enum")
    if value is None:
        return errors
    if isinstance(value, dict):
        props = schema.get("properties", {})
        errors += [f"{path}.{k}: missing" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            errors += [f"{path}.{k}: unexpected field" for k in value if k not in props]
        for key, item in value.items():
            if key in props:
                errors += structural_errors(item, props[key], path + "." + key, root)
    if isinstance(value, list):
        for key, op in (("minItems", lambda a, b: a < b), ("maxItems", lambda a, b: a > b)):
            if key in schema and op(len(value), schema[key]):
                errors.append(f"{path}: violates {key}")
        for i, item in enumerate(value):
            errors += structural_errors(item, schema.get("items", {}), f"{path}[{i}]", root)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string too short")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: invalid pattern")
        if schema.get("format") == "date-time":
            try:
                stamp(value)
            except ValueError:
                errors.append(f"{path}: invalid timezone-aware timestamp")
    if type(value) in (int, float):
        for key, op in (("minimum", lambda a, b: a < b), ("maximum", lambda a, b: a > b),
                        ("exclusiveMinimum", lambda a, b: a <= b)):
            if key in schema and op(value, schema[key]):
                errors.append(f"{path}: violates {key}")
    return errors


def validate(record, phase="draft", *, base_dir=None, now=None, required_profile=None):
    errors = structural_errors(record, load_json(SCHEMA))
    warnings = ["Offline record audit only; no hardware permission or live-state guarantee.",
                "1 kHz only coarsely segments a 20–100 ms platform; neither 1 nor 2 kHz bounds fast-edge peaks."]
    if phase not in ("draft", "ready", "completed"):
        errors.append("Unknown validation phase")
    if errors:
        return errors, warnings
    profile = record.get("profile", "generic")
    local = record.get("local_au111") if profile == "local-au111" else None
    if required_profile is not None and profile != required_profile:
        errors.append("profile: required " + required_profile + "; do not bypass local policy with generic")
    if profile == "local-au111" and local is None:
        errors.append("profile: local-au111 policy record missing")
    if profile != "local-au111" and "local_au111" in record:
        errors.append("profile: local policy record cannot be downgraded to generic")
    if errors:
        return errors, warnings
    for section, fields in (("action", ("voltage_V", "width_s", "preparation_current_A", "resting_bias_V")),
                            ("baseline", ("imaging_bias_V", "imaging_setpoint_A")),
                            ("recovery", ("expected_bias_V", "expected_setpoint_A"))):
        for key in fields:
            try:
                value = float32(record[section][key])
                if value is not None and not math.isfinite(value):
                    raise OverflowError("not finite")
            except (OverflowError, struct.error):
                errors.append(section + "." + key + ": not representable as finite binary32")
    if errors:
        return errors, warnings
    ex, counters, labels = record["execution"], record["budget"], record["labels"]
    decision = record["decision"]
    if counters["stage_actions_attempted_before"] > counters["actions_attempted_before"]:
        errors.append("budget: stage attempts exceed total session attempts")
    if counters["consecutive_failures_before"] > counters["actions_attempted_before"]:
        errors.append("budget: consecutive failures exceed total session attempts")
    if local is not None:
        total = counters["actions_attempted_before"]
        boundary = local["last_improvement_action_attempt_before"]
        pulse_boundary = local["last_improvement_pulse_attempt_before"]
        if local["pulse_attempts_before"] > total:
            errors.append("local-au111: pulse attempts exceed total conditioning attempts")
        if (boundary > total or pulse_boundary > min(local["pulse_attempts_before"], boundary)
                or local["consecutive_no_improvement_before"] != local["pulse_attempts_before"] - pulse_boundary
                or local["consecutive_no_improvement_before"] > total - boundary):
            errors.append("local-au111: no-improvement streak disagrees with last improvement boundary")
        if ex["attempted"]:
            improved = labels["L2"]["status"] == "supported"
            if local["pulse_attempts_after"] != local["pulse_attempts_before"] + 1:
                errors.append("local-au111: each claimed pulse consumes one cumulative pulse, even with unknown ACK")
            expected_streak = 0 if improved else local["consecutive_no_improvement_before"] + 1
            expected_boundary = total + 1 if improved else boundary
            expected_pulse_boundary = local["pulse_attempts_before"] + 1 if improved else pulse_boundary
            if (local["consecutive_no_improvement_after"] != expected_streak
                    or local["last_improvement_action_attempt_after"] != expected_boundary
                    or local["last_improvement_pulse_attempt_after"] != expected_pulse_boundary):
                errors.append("local-au111: only evidenced L2 improvement resets its streak; review/ACK/strategy does not")
        elif any(local[k] is not None for k in ("pulse_attempts_after", "consecutive_no_improvement_after",
                                               "last_improvement_action_attempt_after", "last_improvement_pulse_attempt_after")):
            errors.append("local-au111: result counters populated before an attempted pulse")
    if ex["claim_utc"] is not None or ex["ack_status"] != "not_attempted":
        if ex["attempted"] is not True:
            errors.append("execution: claimed/acknowledged event must count as attempted")
    if ex["attempted"]:
        if counters["actions_attempted_after"] != counters["actions_attempted_before"] + 1:
            errors.append("budget: claimed attempt must consume one action even if ACK is unknown")
        if counters["stage_actions_attempted_after"] != counters["stage_actions_attempted_before"] + 1:
            errors.append("budget: claimed attempt must consume one stage action even if ACK is unknown")
        successful = decision["assessment_for_budget"] == "successful"
        if successful:
            established = (ex["native_end_known"] is True and ex["ack_status"] == "zero_error_waiting_ack"
                           and decision["success_criterion"] and decision["success_evidence"]["path"])
            if record["intent"] == "induction":
                established = established and decision["desired_degradation_established"] and labels["L1"]["status"] == "supported"
            else:
                established = established and labels["L2"]["status"] == labels["L3"]["status"] == "supported"
            if not established:
                errors.append("budget: ACK or no improvement is not evidenced success; cannot reset failures")
        expected_failures = 0 if successful else counters["consecutive_failures_before"] + 1
        if counters["consecutive_failures_after"] != expected_failures:
            errors.append("budget: unassessed/unsuccessful attempt consumes a consecutive failure; only evidenced success resets")
    else:
        result_fields = ("ack_utc", "observation_ended_utc", "native_end_utc", "feedback_restored_utc", "reference_returned_utc",
                         "scan_started_utc", "elapsed_s", "native_end_known", "bias_restored", "feedback_restored")
        if any(ex[k] is not None for k in result_fields) or ex["native_end_basis"] != "unknown":
            errors.append("execution: result fields populated before an attempted action")
        if decision["assessment_for_budget"] != "unassessed" or decision["verified_repair_cycle"]:
            errors.append("decision: outcome populated before an attempted action")
        if any(labels[k]["status"] == "supported" for k in ("L0", "L1", "L2", "L3")):
            errors.append("labels: action outcome supported before an attempted action")
    if labels["L0"]["status"] == "supported" and not (
            ex["attempted"] and ex["native_end_known"] is True and ex["ack_status"] == "zero_error_waiting_ack"):
        errors.append("L0: this profile requires a known, zero-error waiting completion")
    if labels["L4"]["status"] == "supported" and not (
            record["decision"]["independent_chemical_evidence"] and record["decision"]["chemical_evidence_method"]):
        errors.append("L4: independent chemical evidence and method required; L0–L3 do not imply chemistry")
    if labels["L3"]["status"] == "supported" and not (
            record["decision"]["task_criteria"] and record["decision"]["matched_task_criteria"]
            and record["decision"]["independent_recheck_without_intervention"]
            and record["decision"]["recheck_evidence"]["path"] and record["decision"]["recheck_completed_utc"]):
        errors.append("L3: matched task criteria and independent no-intervention recheck are required")
    if record["decision"]["verified_repair_cycle"] and not (
            record["intent"] == "repair" and record["decision"]["before_bad_established"]
            and record["decision"]["matched_imaging_conditions"]
            and labels["L2"]["status"] == labels["L3"]["status"] == "supported"
            and ex["attempted"] and ex["ack_status"] == "zero_error_waiting_ack"
            and ex["native_end_known"] is True and record["history"]["manual_intervention_since_baseline"] is False
            and record["decision"]["causal_valid"] is True and record["decision"]["causal_evidence"]["path"]):
        errors.append("repair cycle: bad→known intervention→matched task usability without intervening manual action is not established")
    for key, label in labels.items():
        if label["status"] == "supported" and not label["evidence"]:
            errors.append("labels." + key + ": supported claim lacks evidence")
    if errors or phase == "draft":
        return errors, warnings
    base_dir = Path(base_dir or ".").resolve()
    now = utc_now() if now is None else now
    # Result audits use the actual claim as the admission clock, while later
    # timestamps are checked against the audit clock. Never refresh old evidence.
    admission = (stamp(record["execution"]["claim_utc"])
                 if phase == "completed" and record["execution"]["claim_utc"] else now)

    def need(ok, message):
        if not ok:
            errors.append(message)
        return bool(ok)

    def present(value, name):
        return need(value is not None and value != "" and value != [], name + ": unconfigured")

    def time_value(value, name):
        if not present(value, name):
            return None
        parsed = stamp(value)
        need(parsed <= now, name + ": in the future")
        return parsed

    def fresh(value, max_age, name):
        when = time_value(value, name)
        if present(max_age, name + ".max_age_s") and when:
            need(0 <= (admission - when).total_seconds() <= max_age, name + ": stale")
        return when

    def artifact(ref, name):
        if not present(ref["path"], name + ".path") or not present(ref["sha256"], name + ".sha256"):
            return
        p = ref["path"]
        if not need(not p.startswith(("//", "\\\\")) and "://" not in p, name + ": local file required"):
            return
        path = Path(p) if Path(p).is_absolute() else base_dir / p
        try:
            need(path.is_file() and digest(path) == ref["sha256"], name + ": missing file or SHA256 mismatch")
        except OSError as exc:
            need(False, name + ": " + str(exc))

    def nonempty_evidence(items, name):
        if need(bool(items), name + ": missing evidence"):
            for i, ref in enumerate(items):
                artifact(ref, f"{name}[{i}]")

    a, auth, budget = record["action"], record["authorization"], record["budget"]
    recovery, target = record["recovery"], record["target"]
    baseline, hist, clip = record["baseline"], record["history"], record["prior_clipping"]
    native, ex, labels = record["recording"], record["execution"], record["labels"]
    state = baseline["readback"]
    for name in ("event_id", "session_id", "state_segment_id", "operator"):
        present(record[name], name)
    time_value(record["created_utc"], "created_utc")
    need(auth["confirmed"] is True, "authorization: not confirmed")
    present(auth["evidence"], "authorization.evidence")
    need(auth["exclusive_writer_confirmed"] is True, "authorization: exclusive writer not confirmed")
    for key in ("target_id", "controller_identity"):
        present(target[key], "target." + key)
    need(auth["target_id"] == target["target_id"] and auth["target_id"] is not None, "authorization: target identity mismatch")
    artifact(target["identity_evidence"], "target.identity_evidence")
    need(a["command"] in auth["commands"], "authorization: command not in scope")
    for param in ("voltage_V", "width_s", "preparation_current_A", "resting_bias_V"):
        value, bounds = a[param], auth["bounds"][param]
        if present(value, "action." + param) and all(present(x, "authorization.bounds." + param) for x in bounds):
            need(bounds[0] <= value <= bounds[1], "authorization: " + param + " outside bounds")
    for i, axis in enumerate(("x_m", "y_m")):
        bounds, value = auth["bounds"][axis], a["xy_m"][i]
        if present(value, "action." + axis) and all(present(x, "authorization.bounds." + axis) for x in bounds):
            need(bounds[0] <= value <= bounds[1], "authorization: XY outside bounds")
    if a["width_s"] is not None:
        need(.020 <= a["width_s"] <= .100, "record profile supports only 20–100 ms pulses")
    for key in ("rationale", "hypothesis"):
        present(a[key], "action." + key)
    if a["physical_polarity"] != "unknown":
        present(a["physical_polarity_evidence"], "action.physical_polarity_evidence")
    need(a["preserve_safetip"] and not a["retry_on_unknown"] and not a["automatic_on"],
         "action: preserve SafeTip; no unknown-outcome retry or automatic On")
    need(budget["confirmed"] is True, "budget: limits not confirmed")
    present(budget["evidence"], "budget.evidence")
    present(budget["failure_definition"], "budget.failure_definition")
    present(budget["reservation_id"], "budget.reservation_id")
    artifact(budget["counter_evidence"], "budget.counter_evidence")
    mandatory_limits = ("max_session_elapsed_s", "max_action_elapsed_s")
    if local is None:
        mandatory_limits += ("max_actions_per_session", "max_actions_per_stage", "max_consecutive_failures")
    for key in mandatory_limits:
        present(budget[key], "budget." + key)
    present(budget["stage_id"], "budget.stage_id")
    need(a["stage_id"] == budget["stage_id"] and a["stage_id"] is not None, "budget: action stage mismatch")
    need(not budget["stop_requested"] and not budget["repair_success_already_achieved"], "budget: stop condition reached")
    if budget["max_actions_per_session"] is not None:
        need(budget["actions_attempted_before"] < budget["max_actions_per_session"], "budget: session action limit reached")
    if budget["max_actions_per_stage"] is not None:
        need(budget["stage_actions_attempted_before"] < budget["max_actions_per_stage"], "budget: stage action limit reached")
    if budget["max_consecutive_failures"] is not None:
        need(budget["consecutive_failures_before"] < budget["max_consecutive_failures"], "budget: consecutive failure limit reached")
    if local is not None:
        need(local["pulse_attempts_before"] < 6, "local-au111: six-pulse session cap reached; strategy changes cannot reset it")
        need(state["safetip_state"] == "off", "local-au111: SafeTip must already be Off and read back; this tool cannot switch it")
        present(a.get("strategy_id"), "action.strategy_id")
        if local["last_improvement_action_attempt_before"]:
            artifact(local["last_improvement_evidence"], "local_au111.last_improvement_evidence")
        review = local["strategy_review"]
        checkpoint = 0
        if review["reviewed_through_action_attempt"] is not None:
            artifact(review["evidence"], "local_au111.strategy_review.evidence")
            reviewed = time_value(review["reviewed_utc"], "local_au111.strategy_review.reviewed_utc")
            need(reviewed is not None and reviewed <= admission, "local-au111: review must precede this action/admission")
            reviewed_action = review["reviewed_through_action_attempt"]
            need(local["last_improvement_action_attempt_before"] < reviewed_action <= budget["actions_attempted_before"],
                 "local-au111: review predates the improvement boundary or covers a future attempt")
            reviewed_pulse = review["reviewed_through_pulse_attempt"]
            nonpulse_before = budget["actions_attempted_before"] - local["pulse_attempts_before"]
            need(reviewed_pulse is not None and max(0, reviewed_action-nonpulse_before) <= reviewed_pulse <= min(local["pulse_attempts_before"], reviewed_action),
                 "local-au111: review pulse index missing or in the future")
            checkpoint = review["consecutive_no_improvement_at_review"]
            need(checkpoint is not None and reviewed_pulse is not None
                 and checkpoint == reviewed_pulse - local["last_improvement_pulse_attempt_before"]
                 and checkpoint <= local["consecutive_no_improvement_before"], "local-au111: review streak checkpoint inconsistent")
            present(review["rationale"], "local_au111.strategy_review.rationale")
            need(review["decision"] == "continue_pulse", "local-au111: review did not select a next pulse; other strategies need separate review/implementation")
            need(review["next_strategy_id"] is not None and review["next_strategy_id"] == a.get("strategy_id"),
                 "local-au111: next strategy differs from the recorded review")
        if checkpoint is not None:
            need(local["consecutive_no_improvement_before"] - checkpoint < 2,
                 "local-au111: two further no-improvement attempts require strategy review, not automatic escalation")
    started = time_value(budget["session_started_utc"], "budget.session_started_utc")
    estimate = a["estimated_elapsed_s"]
    if present(estimate, "action.estimated_elapsed_s"):
        if budget["max_action_elapsed_s"] is not None:
            need(estimate <= budget["max_action_elapsed_s"], "budget: action duration exceeds limit")
        if started and budget["max_session_elapsed_s"] is not None:
            need(0 <= (admission - started).total_seconds()
                 and (admission - started).total_seconds() + estimate <= budget["max_session_elapsed_s"],
                 "budget: insufficient session time")
    need(record["previous_action"]["outcome"] != "unknown", "previous action outcome unknown; no replay or next action")
    present(record["previous_action"]["evidence"], "previous_action.evidence")
    need(hist["manual_intervention_since_baseline"] is False, "baseline: manual intervention unknown or occurred; rebuild baseline")
    present(hist["evidence"], "history.evidence")
    history_time = time_value(hist["checked_utc"], "history.checked_utc")
    need(baseline["state_segment_id"] == record["state_segment_id"], "baseline: state segment mismatch")
    need(baseline["baseline_is_immediate"] is True, "baseline: immediate pre-action state not established")
    present(baseline["imaging_bias_V"], "baseline.imaging_bias_V")
    present(baseline["imaging_setpoint_A"], "baseline.imaging_setpoint_A")
    if (baseline["imaging_bias_V"] != a["resting_bias_V"]
            or baseline["imaging_setpoint_A"] != a["preparation_current_A"]):
        present(baseline["preparation_changes_review"], "baseline.preparation_changes_review")
    verified = fresh(baseline["fresh_verified_utc"], baseline["max_age_s"], "baseline.fresh_verified_utc")
    snap_time = time_value(baseline["snapshot_utc"], "baseline.snapshot_utc")
    image_time = time_value(baseline["image_completed_utc"], "baseline.image_completed_utc")
    through = time_value(baseline["native_reviewed_through_utc"], "baseline.native_reviewed_through_utc")
    for key in ("snapshot", "image", "interval_native_review"):
        artifact(baseline[key], "baseline." + key)
    if all((verified, snap_time, image_time, through, history_time)):
        need(image_time <= through <= verified and snap_time <= verified and history_time >= through,
             "baseline: image-to-action interval/history review incomplete or inconsistent")
        if baseline["max_age_s"] is not None:
            need(0 <= (admission - through).total_seconds() <= baseline["max_age_s"], "baseline: native interval review stale")
            need(0 <= (admission - snap_time).total_seconds() <= baseline["max_age_s"], "baseline: snapshot stale")
    if hist["last_manual_intervention_utc"] is not None:
        last = time_value(hist["last_manual_intervention_utc"], "history.last_manual_intervention_utc")
        need(bool(image_time and snap_time and last < image_time and last < snap_time), "baseline predates last manual intervention")
    need(baseline["full_configuration_verified"] is True, "baseline: full configuration not verified")
    need(state["feedback_status"] == "On2" and state["scan_idle"] is True and state["other_actions_idle"] is True,
         "baseline: feedback/idle state not admitted")
    need(state["bias_V"] == float32(a["resting_bias_V"]) and state["setpoint_A"] == float32(a["preparation_current_A"]),
         "baseline: bias/setpoint mismatch (exact binary32 expectation from nominal command)")
    need(state["xy_m"] == a["xy_m"], "baseline: action XY differs from readback")
    present(state["z_m"], "baseline.readback.z_m")
    zlo, zhi = baseline["z_limits_m"]
    margin = baseline["z_margin_m"]
    if all(present(x, "baseline.Z limits/margin") for x in (zlo, zhi, margin)) and state["z_m"] is not None:
        need(zlo + margin <= state["z_m"] <= zhi - margin, "baseline: insufficient Z endpoint margin")
    present(state["safetip_state"], "baseline.readback.safetip_state")
    need(bool(state["safetip_properties"]) and bool(state["gain_readback"]), "baseline: missing SafeTip properties/gain readback")
    low, high = baseline["signed_current_band_A"]
    if all(present(x, "baseline.signed_current_band_A") for x in (low, high)) and present(state["current_A"], "baseline.current_A"):
        need(low <= state["current_A"] <= high and low < high, "baseline: signed current outside admission band")
    if present(baseline["stable_observation_s"], "baseline.stable_observation_s") and present(baseline["required_stable_s"], "baseline.required_stable_s"):
        need(baseline["stable_observation_s"] >= baseline["required_stable_s"], "baseline: insufficient sampled stability")
    need(clip["status"] != "unknown", "prior clipping: not reviewed")
    artifact(clip["review"], "prior_clipping.review")
    if clip["status"] == "detected":
        need(clip["handled"] is True and bool(clip["resolution"]), "prior clipping: unresolved")
        last = time_value(clip["last_detected_utc"], "prior_clipping.last_detected_utc")
        need(bool(last and image_time and snap_time and last < image_time and last < snap_time), "prior clipping: no new post-event baseline")
    if present(native["sample_rate_hz"], "recording.sample_rate_hz"):
        need(native["sample_rate_hz"] >= 1000, "recording: less than 1 kHz")
        if native["sample_rate_hz"] != 2000:
            warnings.append("Local 20–100 ms evidence used 2 kHz; this different rate needs its own timing/bandwidth review.")
    need(native["sample_rate_basis"] in ("native_readback", "verified_native_header"), "recording: sample rate unverified")
    present(native["module"], "recording.module")
    for key in ("configuration", "configuration_readback"):
        artifact(native[key], "recording." + key)
    if native["bandwidth_status"] == "verified":
        present(native["bandwidth_Hz"], "recording.bandwidth_Hz")
    if native["range_status"] == "verified":
        rlo, rhi = native["current_range_A"]
        if all(present(x, "recording.current_range_A") for x in (rlo, rhi)):
            need(rlo < rhi, "recording: current range reversed")
    if "unknown" in (native["bandwidth_status"], native["range_status"]):
        present(native["unknown_chain_limitations"], "recording.unknown_chain_limitations")
    need(set(("Current", "Bias", "Z")) <= set(native["channels"]), "recording: require Current/Bias/Z")
    fresh(native["logger_verified_utc"], native["logger_max_age_s"], "recording.logger_verified_utc")
    if present(native["estimated_remaining_s"], "recording.estimated_remaining_s") and present(native["required_coverage_s"], "recording.required_coverage_s") and estimate is not None:
        need(native["estimated_remaining_s"] >= native["required_coverage_s"] >= estimate,
             "recording: insufficient estimated wall-clock coverage")
    for key in ("max_wait_s", "required_stable_s", "expected_bias_V", "expected_setpoint_A",
                "max_abs_z_trend_m_per_s", "max_z_span_m", "z_trend_window_s"):
        present(recovery[key], "recovery." + key)
    if recovery["max_wait_s"] is not None:
        if estimate is not None and a["width_s"] is not None:
            need(estimate >= recovery["max_wait_s"] + a["width_s"], "recovery: estimated action time cannot cover recovery deadline")
        for key in ("required_stable_s", "z_trend_window_s"):
            if recovery[key] is not None:
                need(recovery[key] <= recovery["max_wait_s"], "recovery: stability window exceeds deadline")
    need(recovery["expected_bias_V"] == baseline["imaging_bias_V"]
         and recovery["expected_setpoint_A"] == baseline["imaging_setpoint_A"], "recovery: reference imaging conditions not restored by plan")
    rlow, rhigh = recovery["signed_current_band_A"]
    if all(present(x, "recovery.signed_current_band_A") for x in (rlow, rhigh)):
        need(rlow < rhigh, "recovery: reversed signed current band")
    if phase == "ready":
        need(ex["attempted"] is False and ex["ack_status"] == "not_attempted" and ex["claim_utc"] is None,
             "execution: this event already attempted/claimed; no replay")
        need(budget["actions_attempted_after"] is None and budget["stage_actions_attempted_after"] is None and budget["consecutive_failures_after"] is None,
             "budget: result counters already populated; do not replay this event")
    if phase == "completed":
        # Completed audit is anchored to the preparation time, not the current clock.
        need(ex["attempted"] is True and ex["ack_status"] == "zero_error_waiting_ack" and ex["native_end_known"] is True,
             "execution: known native completion not established")
        need(budget["actions_attempted_after"] == budget["actions_attempted_before"] + 1,
             "budget: every dispatched/claimed attempt consumes one action, including unknown ACK")
        present(budget["consecutive_failures_after"], "budget.consecutive_failures_after")
        times = [time_value(ex[k], "execution." + k) for k in ("claim_utc", "ack_utc", "observation_ended_utc")]
        if all(times):
            need(times[0] <= times[1] <= times[2], "execution: timing order invalid")
            elapsed_from_stamps = (times[2] - times[0]).total_seconds()
            post_ack_from_stamps = (times[2] - times[1]).total_seconds()
            if ex["elapsed_s"] is not None:
                need(abs(ex["elapsed_s"] - elapsed_from_stamps) <= .001,
                     "execution: elapsed_s inconsistent with same-host claim/observation timestamps")
            if ex["recovery_elapsed_s"] is not None:
                need(abs(ex["recovery_elapsed_s"] - post_ack_from_stamps) <= .001,
                     "execution: recovery_elapsed_s inconsistent with ACK/observation timestamps")
            if budget["max_action_elapsed_s"] is not None:
                need(elapsed_from_stamps <= budget["max_action_elapsed_s"], "execution: timestamp-derived action budget exceeded")
            if started and budget["max_session_elapsed_s"] is not None:
                need((times[2] - started).total_seconds() <= budget["max_session_elapsed_s"], "execution: timestamp-derived session budget exceeded")
        native_end = None
        if ex["native_end_basis"] == "observed_native_end":
            native_end = time_value(ex["native_end_utc"], "execution.native_end_utc")
            if all(times) and native_end:
                need(times[0] <= native_end <= times[1], "execution: measured native end must be between claim and waiting ACK")
        elif ex["native_end_basis"] == "waiting_ack_upper_bound":
            need(ex["native_end_utc"] is None, "execution: ACK upper bound is not an exact native end timestamp")
        else:
            need(False, "execution: native end timing basis unknown")
        restored = time_value(ex["feedback_restored_utc"], "execution.feedback_restored_utc")
        returned = time_value(ex["reference_returned_utc"], "execution.reference_returned_utc")
        if all(times) and restored and returned:
            need(times[1] <= restored <= returned <= times[2], "execution: restoration/return/observation ordering invalid")
            # These are host readback observation times, not the physical instant
            # of feedback switching. Stability cannot predate observed feedback.
            observed_on_span = (times[2] - restored).total_seconds()
            for key in ("effective_stable_window_s", "recovery_z_observation_s"):
                if ex[key] is not None:
                    need(ex[key] <= observed_on_span, "execution: " + key + " exceeds observed feedback-on span")
            if recovery["max_wait_s"] is not None:
                recovery_start = native_end if native_end else times[1]
                need((times[2] - recovery_start).total_seconds() <= recovery["max_wait_s"],
                     "execution: timestamp-derived recovery wait exceeded")
        if ex["scan_started_utc"] is not None:
            scan_start = time_value(ex["scan_started_utc"], "execution.scan_started_utc")
            need(bool(returned and returned <= scan_start and times[2] and times[2] <= scan_start), "execution: scan before recovery completed")
        present(ex["elapsed_s"], "execution.elapsed_s")
        if ex["elapsed_s"] is not None and budget["max_action_elapsed_s"] is not None:
            need(ex["elapsed_s"] <= budget["max_action_elapsed_s"], "execution: elapsed budget exceeded")
        need(ex["bias_restored"] is True and ex["feedback_restored"] is True, "execution: recovery not independently read back")
        for key in ("recovery_elapsed_s", "recovery_z_trend_m_per_s", "recovery_z_span_m", "recovery_z_observation_s"):
            present(ex[key], "execution." + key)
        if ex["recovery_elapsed_s"] is not None:
            if ex["elapsed_s"] is not None:
                need(ex["recovery_elapsed_s"] <= ex["elapsed_s"], "execution: recovery longer than whole action")
            for key in ("effective_stable_window_s", "recovery_z_observation_s"):
                if ex[key] is not None:
                    need(ex[key] <= ex["recovery_elapsed_s"], "execution: " + key + " exceeds recovery elapsed")
        for field, limit in (("recovery_elapsed_s", "max_wait_s"), ("recovery_z_span_m", "max_z_span_m")):
            if ex[field] is not None and recovery[limit] is not None:
                need(ex[field] <= recovery[limit], "execution: " + field + " exceeds recovery criterion")
        if ex["recovery_z_trend_m_per_s"] is not None and recovery["max_abs_z_trend_m_per_s"] is not None:
            need(abs(ex["recovery_z_trend_m_per_s"]) <= recovery["max_abs_z_trend_m_per_s"], "execution: recovery Z trend exceeds criterion")
        if ex["recovery_z_observation_s"] is not None and recovery["z_trend_window_s"] is not None:
            need(ex["recovery_z_observation_s"] >= recovery["z_trend_window_s"], "execution: insufficient Z observation window")
        if present(ex["effective_stable_window_s"], "execution.effective_stable_window_s") and present(ex["required_final_stable_s"], "execution.required_final_stable_s"):
            need(ex["effective_stable_window_s"] >= ex["required_final_stable_s"], "execution: insufficient final sampled stable window")
            need(ex["required_final_stable_s"] == recovery["required_stable_s"], "execution: stable-window requirement changed after action")
        for key in ("claim", "ack", "immediate_readback", "final_readback", "reference_return_evidence"):
            artifact(ex[key], "execution." + key)
        final = ex["final_state"]
        if local is not None:
            need(final["safetip_state"] == "off", "local-au111: final SafeTip must remain Off")
        for key in ("xy_m", "safetip_state", "safetip_properties", "gain_readback"):
            need(final[key] == state[key], "execution: final " + key + " not preserved/restored")
        need(final["bias_V"] == float32(recovery["expected_bias_V"]) and final["setpoint_A"] == float32(recovery["expected_setpoint_A"]),
             "execution: reference bias/setpoint not restored")
        if all(x is not None for x in (zlo, zhi, margin, final["z_m"])):
            need(zlo + margin <= final["z_m"] <= zhi - margin, "execution: final Z endpoint margin insufficient")
        else:
            need(False, "execution: missing final Z position/limits/margin")
        need(final["feedback_status"] == "On2" and final["scan_idle"] is True and final["other_actions_idle"] is True,
             "execution: final state not idle On2")
        if rlow is not None and rhigh is not None:
            need(final["current_A"] is not None and rlow <= final["current_A"] <= rhigh,
                 "execution: final current outside signed admission band")
        need(native["complete"] is True and not native["gaps"], "recording: missing native coverage")
        nonempty_evidence(native["files"], "recording.files")
    for key, label in labels.items():
        if label["status"] == "supported":
            nonempty_evidence(label["evidence"], "labels." + key)
    if labels["L0"]["status"] == "supported":
        need(ex["native_end_known"] is True and ex["attempted"] is True, "L0: command execution not confirmed")
    if labels["L4"]["status"] == "supported":
        need(record["decision"]["independent_chemical_evidence"] is True, "L4 requires independent chemical evidence, not L0–L3 inference")
    if labels["L3"]["status"] == "supported":
        artifact(record["decision"]["recheck_evidence"], "decision.recheck_evidence")
        rechecked = time_value(record["decision"]["recheck_completed_utc"], "decision.recheck_completed_utc")
        need(ex["scan_started_utc"] is not None and rechecked is not None
             and stamp(ex["scan_started_utc"]) <= rechecked, "L3: no ordered post-recovery imaging/recheck")
    if record["decision"]["assessment_for_budget"] == "successful":
        artifact(record["decision"]["success_evidence"], "decision.success_evidence")
    if record["decision"]["verified_repair_cycle"]:
        d = record["decision"]
        artifact(d["causal_evidence"], "decision.causal_evidence")
        need(record["intent"] == "repair" and d["before_bad_established"] and d["matched_imaging_conditions"]
             and labels["L2"]["status"] == labels["L3"]["status"] == "supported" and ex["native_end_known"] is True
             and hist["manual_intervention_since_baseline"] is False,
             "repair cycle requires established bad→one known intervention→matched task-usable evidence without untracked intervention")
    return errors, warnings


def write_new(path, value):
    # Exclusive creation: no overwrite of a prior claim, report, or receipt.
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create an unconfigured local JSON record; never executes")
    init.add_argument("output", type=Path)
    init.add_argument("--event-id", required=True)
    init.add_argument("--session-id", required=True)
    init.add_argument("--profile", choices=("generic", "local-au111"), default="generic")
    for name in ("validate", "prepare"):
        cmd = sub.add_parser(name)
        cmd.add_argument("record", type=Path)
        cmd.add_argument("--require-profile", choices=("generic", "local-au111"), help="Enforce the project policy rather than trusting a record's profile selection")
        if name == "validate":
            cmd.add_argument("--phase", choices=("draft", "ready", "completed"), default="draft")
            cmd.add_argument("--at", help="Historical audit clock (ISO8601); not a live-state check")
        else:
            cmd.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            value = load_json(TEMPLATE)
            apply_profile(value, args.profile)
            value.update(event_id=args.event_id, session_id=args.session_id, created_utc=utc_now().isoformat())
            write_new(args.output, value)
            print(json.dumps({"created": str(args.output), "configured": False, "hardware_commands_performed": 0}))
            return 0
        record = load_json(args.record)
        clock = stamp(args.at) if args.command == "validate" and args.at else utc_now()
        phase = "ready" if args.command == "prepare" else args.phase
        errors, warnings = validate(record, phase, base_dir=args.record.parent, now=clock, required_profile=args.require_profile)
        result = {"schema_version": "1.0", "phase": phase, "valid": not errors,
                  "evaluated_utc": clock.isoformat(), "errors": errors, "warnings": warnings,
                  "record_sha256": digest(args.record), "hardware_commands_performed": 0,
                  "execution_permitted": False, "requires_external_live_admission": True}
        if args.command == "prepare" and not errors:
            result["record"] = str(args.record.resolve())
            result["command_for_review_only"] = ["Bias.Pulse", [1, record["action"]["width_s"], record["action"]["voltage_V"], 1, 2]]
            result["encoded_float32_for_review_only"] = {key: float32(record["action"][key])
                for key in ("voltage_V", "width_s", "preparation_current_A", "resting_bias_V")}
            result["attempt_budget_reservation"] = {
                "id": record["budget"]["reservation_id"],
                "before": record["budget"]["actions_attempted_before"],
                "consumed_count_if_claimed": record["budget"]["actions_attempted_before"] + 1,
                "stage_id": record["budget"]["stage_id"],
                "stage_consumed_count_if_claimed": record["budget"]["stage_actions_attempted_before"] + 1,
                "consumes_even_if_ack_unknown": True, "global_ledger_atomically_reserved": False}
            if record.get("profile") == "local-au111":
                result["local_au111_policy"] = {"max_pulses_per_session": 6, "review_after_no_improvement": 2,
                    "required_safetip": "off", "pulse_count_if_claimed": record["local_au111"]["pulse_attempts_before"] + 1,
                    "strategy_review_executes_no_action": True, "tipshaper_executor_provided": False}
            write_new(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 1 if errors else 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({"valid": False, "error": str(exc), "hardware_commands_performed": 0}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
