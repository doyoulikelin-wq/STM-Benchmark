#!/usr/bin/env python3
"""Offline by default: finite DataLog-only record with SafeTip already Off.

Independent derivative of event240/event600 and the static recorder base.
Modes: withdraw=Off/status1/absolute Home/|I|<10pA; stable=On2/-100pA+/-20%.
Both modes require -1V/100pA/all idle and retained SafeTip properties.
Only7200 nominal units (2hours0minutes); prior1200→600wall timing suggests
about3600wall seconds. This longer setting is unvalidated until measured.
Exact local session_01..05/logger outputs; independent one-shot invocation.
After Start the junction is observed only. This recorder is not protection,
does not disable SafeTip, and sends no junction or sampling-setting command.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import re
import shutil
import signal
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE_DIR = HERE.parent / "stm_tip_benchmark_goal_20261030/datalog_review"
ORIGINAL = BASE_DIR / "datalog_safetipoff_20261031.py"
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ROLE = "fullcycle_native_logger"
PINS = {
    '/Users/maxlin/Desktop/Nanonis/work/stm_tip_benchmark_goal_20261030/datalog_review/datalog_safetipoff_20261031.py': '88f6a49daa54c042536764377b1a8217a511c9bbd1bc943b8d83e594faf6f0d5',
    '/Users/maxlin/Desktop/Nanonis/work/stm_tip_benchmark_goal_20261030/datalog_review/datalog_static_once.py': '74b4ee781cf55c9c46bd8e7510f5048efaba781edaa6a707d3d7400d59677438',
    '/Users/maxlin/Desktop/Nanonis/work/stm_tip_benchmark_20261029/scan_acquire.py': '1398797da9b7d2a7e93490e272afb4fef702035d867f67cb08abbbefa5a19958',
    '/Users/maxlin/Desktop/Nanonis/work/stm_tip_control_test_20261028/protocol.py': 'cb89eba6d0417b37b86ed593b9d85d96650ae5978d7d1e919b6a291e9ab2b742',
    '/Users/maxlin/Desktop/Nanonis/work/stm_tip_control_test_20261028/catalog.json': 'f7637754438751ca52253f0884632d499202111140e945efaeaedbbb38a184ac',
    '/Users/maxlin/Desktop/Nanonis/outputs/nanonis-tcp-20261010/Nanonis_TCP_全部接口.json': '0cebeb38d416df2371d7d77e677f8181eda0fcdbc2bf3573211a2a3c23e3ac3e',
}
for _path, _sha in PINS.items():
    if hashlib.sha256(Path(_path).read_bytes()).hexdigest() != _sha:
        raise RuntimeError("Frozen local dependency changed: " + _path)
spec = importlib.util.spec_from_file_location("datalog_event_base", BASE_DIR / "datalog_static_once.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
a, p, require = b.a, b.p, b.require
COMMENT = "SafeTipOff event record; DataLog commands only; junction action audited separately."
ALLOWED_DURATIONS = (7200,)
MIN_LOCAL_FREE_BYTES = 1024 ** 3
TIMING_READS = ("Util.RTFreqGet", "Util.RTOversamplGet", "Util.AcqPeriodGet")
EXPECTED_TIMING = {"Util.RTFreqGet": [20000.0], "Util.RTOversamplGet": [10],
                   "Util.AcqPeriodGet": [0.019999999552965164]}


HOME_READS = ("ZCtrl.HomePropsGet", "ZCtrl.LimitsGet", "ZCtrl.LimitsEnabledGet")


def mode_description(mode):
    require(mode in ("withdraw", "stable"), "Mode must be withdraw or stable")
    junction = ("feedbackOff/status1/absolutephysicalHome/absCurrent<10pA" if mode == "withdraw"
                else "feedbackOn/status2/signedCurrent-120..-80pA")
    return "Five-second sampled static -1V/100pA/allidle/SafeTipOff; retained500pA/recoveryOff/pauseOn; " + junction


def state_guard(v, mode):
    mode_description(mode)
    require(a.close_float(v["Bias.Get"][0], -1.0), "Bias must remain -1V")
    require(a.close_float(v["ZCtrl.SetpntGet"][0], 100e-12), "Setpoint must remain100pA")
    current, z = v["Current.Get"][0], v["ZCtrl.ZPosGet"][0]
    require(a.finite(current) and a.finite(z), "Nonfinite current or Z")
    for name in ("Scan.StatusGet", "BiasSpectr.StatusGet", "ZSpectr.StatusGet", "AutoApproach.OnOffGet"):
        require(v[name] == [0], name + " must be idle/Off")
    require(v["SafeTip.OnOffGet"] == [0], "SafeTip must already be Off; recorder never changes it")
    props = v["SafeTip.PropsGet"]
    require(len(props) == 3 and props[:2] == [0, 1] and a.close_float(props[2], 500e-12),
            "Retain configured recoveryOff/pauseOn/500pA (inactive while SafeTipOff)")
    if mode == "stable":
        require(v["ZCtrl.OnOffGet"] == [1] and v["ZCtrl.StatusGet"] == [2], "Need On/status2")
        require(-120e-12 <= current <= -80e-12, "Sampled current outside -100pA +/-20%")
    else:
        require(v["ZCtrl.OnOffGet"] == [0] and v["ZCtrl.StatusGet"] == [1], "Need Off/status1")
        require(abs(current) < 10e-12, "Withdrawn sampled absCurrent must be <10pA")
        home, limits = v["ZCtrl.HomePropsGet"], v["ZCtrl.LimitsGet"]
        require(v["ZCtrl.LimitsEnabledGet"] == [0], "Need physical piezo limits, not enabled software limits")
        require(len(home) == 2 and home[0] == 0 and len(limits) == 2
                and all(a.finite(x) for x in [home[1], *limits]) and limits[1] < limits[0],
                "Need finite absolute Home and ordered physical limits")
        require(a.close_float(home[1], limits[0]) and a.close_float(z, home[1]),
                "Need withdrawn Z at absolute Home/physical upper limit")


def disk_guard(path):
    # Only the local audit filesystem is checked. Native Windows free space is
    # not queried by this recorder, and must not be claimed from this value.
    probe = Path(path).resolve()
    while not probe.exists():
        require(probe.parent != probe, "No existing local filesystem ancestor")
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    require(free >= MIN_LOCAL_FREE_BYTES, "Local audit filesystem below1GiB free; no new regular command")
    return {"existing_path_checked": str(probe), "free_bytes": free,
            "minimum_free_bytes": MIN_LOCAL_FREE_BYTES, "native_Windows_free_space_verified": False}


def timing_guard(values):
    for name in TIMING_READS:
        require(values[name] == EXPECTED_TIMING[name], "Reviewed sampling/TCP acquisition setting changed: " + name)


def session_binding(session):
    require(type(session) is str and re.fullmatch(r"session_0[1-5]", session) is not None,
            "Explicit session_01..05 required")
    return {"session_id": session, "source_sha256": SOURCE_SHA256, "role": ROLE}


def output_guard(path, session):
    session_binding(session)
    root = Path(path).resolve()
    require(root == HERE / session / "logger", "Output must be exact local NEW/session_0x/logger; no aliases/shares")
    require(not root.exists(), "New output directory required; no reuse")
    return root


def duration_fields(duration):
    require(type(duration) is int and duration == 7200, "Only7200 nominal setting units reviewed")
    return [2, 0, 0.0]


def settings(basename, duration):
    return [("DataLog.ChsSet", [6, b.CHANNELS]),
            ("DataLog.PropsSet", [2, *duration_fields(duration), 1, basename, COMMENT, []])]


def profile(v, basename, duration):
    require(v["DataLog.ChsGet"] == [6, b.CHANNELS], "DataLog channel readback differs")
    props = v["DataLog.PropsGet"]
    hours, minutes, seconds = duration_fields(duration)
    require(len(props) == 9 and props[:3] == [1, hours, minutes] and a.close_float(props[3], seconds)
            and props[4] == 1 and props[5:] == [len(basename), basename, len(COMMENT), COMMENT],
            "DataLog finiteTimed/avg1/basename/comment readback differs")


class Client(b.Client):
    def __init__(self, store, basename, duration):
        super().__init__(store, basename)
        self.allowed_writes = settings(basename, duration) + [("DataLog.Start", []), ("DataLog.Stop", [])]


def run(args):
    duration_fields(args.duration)
    mode_description(args.mode)
    output = output_guard(args.output, args.session)
    initial_disk = disk_guard(output)
    store = a.Store(output)
    c = Client(store, args.basename, args.duration)
    global_deadline = time.monotonic() + args.duration + 80
    started = False; terminated = False; stop_attempted = False; abort = False
    owns_start = True; new_start = None; paths = set(); ready = False
    result = {"status": "not_started", "start_attempted": False, "ready_written": False,
              "junction_writes": 0, "automatic_retry": False, "automatic_reconnect": False,
              "native_files_archived": False, "file_content_validated": False,
              "hard_realtime_alignment_proven": False, "stop_attempted": False, "preflight_mode": args.mode, **session_binding(args.session)}

    def interrupted(number, _frame):
        nonlocal abort
        abort = True
        store.event("termination_requested", signal=number)

    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}

    def q(name, values=None):
        require(not abort, "Recorder termination requested")
        disk_guard(store.root)
        remaining = global_deadline - time.monotonic()
        require(remaining > 0, "Recorder overall deadline reached")
        return c.call(name, values, timeout=min(3, remaining))

    def snapshot(label):
        values, errors = {}, {}
        begin = a.stamp(); complete = False
        try:
            for name, values_args in b.CORE + b.EXTRA:
                try:
                    values[name] = q(name, values_args)
                except p.InstrumentError as exc:
                    errors[name] = str(exc)
                    if (name, values_args) in b.CORE:
                        raise
            complete = True
        finally:
            store.save(label + ".json", {"start": begin, "end": a.stamp(), "values": values,
                "unavailable": errors, "enumeration_completed": complete, "coherent_snapshot": False})
        return values

    def claim(command, values, label):
        ref = store.save(label + ".claim", {**a.stamp(), **session_binding(args.session), "command": command, "args": values, "at_most_once": True})
        c.permit = (command, values)
        return ref

    def get_status(label):
        raw = q("DataLog.StatusGet")
        s = b.status_values(raw)
        if s["last_saved_path"]:
            paths.add(s["last_saved_path"])
        store.event("datalog_status", label=label, raw_values=raw, parsed=s)
        return s

    def get_profile(label):
        v = {name: q(name) for name in ("DataLog.ChsGet", "DataLog.PropsGet") + TIMING_READS}
        store.event("datalog_profile", label=label, values=v)
        profile(v, args.basename, args.duration)
        timing_guard(v)
        return v

    def poll(label, static):
        values, errors = {}, {}
        for name in b.POLL + (list(HOME_READS) if static and args.mode == "withdraw" else []):
            try:
                values[name] = q(name)
            except p.InstrumentError as exc:
                errors[name] = str(exc)
                if static:
                    raise
        store.event(label, values=values, unavailable=errors, coherent_snapshot=False,
                    interpretation="static_preflight" if static else "observed_only_no_junction_failure_diagnosis")
        if static:
            state_guard(values, args.mode)
        return values

    def cleanup(reason):
        nonlocal stop_attempted
        # Low free-space failures deliberately bypass q's reserve guard for
        # this already-claimed single logger Stop/status cleanup only. It still
        # audits/fsyncs, never reconnects, and cannot send a junction command.
        if started and not terminated and not stop_attempted and not c._closed and owns_start:
            stop_attempted = True; result["stop_attempted"] = True
            claim("DataLog.Stop", [], "cleanup_stop")
            store.event("cleanup_stop_reason", reason=reason)
            c.call("DataLog.Stop", [], timeout=3)
            value = c.call("DataLog.StatusGet", [], timeout=3)
            store.save("after_cleanup_stop.json", {**a.stamp(), "values": value,
                                                  "ack_alone_proves_stop": False})

    try:
        require(re.fullmatch(r"dl_goal30_[A-Za-z0-9_]{4,48}", args.basename) is not None, "Unique ASCII dl_goal30_ basename required")
        b.valid_directory(args.expected_session_path); b.valid_directory(args.expected_native_directory)
        ui = args.ui_evidence.read_bytes()
        age = time.time() - args.ui_evidence.stat().st_mtime
        require(ui and 0 <= age < 900, "Context screenshot must be recent (<15min); logger idleness is checked by TCP")
        store.save_bytes("context_screenshot" + args.ui_evidence.suffix, ui)
        sources = [Path(__file__), ORIGINAL, BASE_DIR / "datalog_event600_once.py", BASE_DIR / "datalog_event240_once.py", BASE_DIR / "datalog_static_once.py", b.OLD / "scan_acquire.py",
                   a.PACKAGE / "protocol.py", a.PACKAGE / "catalog.json", b.DOC]
        store.save("manifest.json", {**a.stamp(), **session_binding(args.session), "purpose": "finite_fullcycle_SafeTipOff_observation_only",
            "preflight_mode": args.mode,
            "ui_evidence_scope": "Recent screenshot provides desktop context only; DataLog UI was not visible/reviewed. Idle evidence is unchanged stopped DataLog.StatusGet across two TCP reads at least1s apart, plus another prestart comparison. No active-logger takeover.",
            "host": a.HOST, "port": 6504, "source_ip": a.SOURCE_IP, "interface": "en0",
            "settings": settings(args.basename, args.duration), "native_duration_s": args.duration,
            "overall_deadline_s": args.duration + 80, "native_completion_wait_s": args.duration + 15,
            "bounded_cleanup_network_budget_s": 6,
            "local_disk_reserve": initial_disk,
            "disk_guard_policy": "At least1GiB free before output creation and every regular query/write. On exhaustion, only the existing at-most-once loggerStop/status cleanup may bypass the reserve. fsync failure closes the client; no reconnect.",
            "native_disk_space": "Not verified by local disk guard. Parent reviews native Windows destination capacity separately; no SMB/network capacity probe is implemented.",
            "fixed_sampling_readbacks": EXPECTED_TIMING,
            "sampling_check": "Exact readback before configuration, prestart, aboutevery2s and after. No RT/oversampling/acquisition-period setters are allowed. Native header0.5ms still requires post-audit.",
            "native_block_samples_documented": 25000,
            "native_block_size_setter_sent": False,
            "capacity_planning_only": {"expected_wall_s_from_prior_half_factor": args.duration / 2,
                "expected_points_at_header_0_5ms": args.duration * 1000,
                "expected_full25000point_blocks": (args.duration * 1000) // 25000,
                "expected_partial_block_points": (args.duration * 1000) % 25000,
                "possible_partial_or_empty_stop_flush_unverified": True,
                "native_ASCII_size_estimate_MiB_at_prior_factor": args.duration / 12,
                "basis": "Prior1200nominal repeatedly yielded600wall/1200000rows.7200nominal is a new extrapolation, not guaranteed3600wall or fullcycle coverage. Check file headers, continuity and every stage overlap."},
            "expected_session_path": args.expected_session_path, "expected_native_directory": args.expected_native_directory,
            "before_start": mode_description(args.mode),
            "after_start": "Junction states are observational data. No feedback/bias/scan/position/spectroscopy/protection command exists in this recorder.",
            "ready_contract": "Only after StartACK, fresh native start, elapsed/counter progress, and finite profile readback. Root must check READY plus fresh continuing status/no outcome before a separately audited action.",
            "disconnect_policy": "Readback-verified native Timed duration is the finite fallback. Timeout is not cancellation. No reconnect/repeatedStart; root verifies native UI if stop is unconfirmed.",
            "file_policy": "Native time-series files must be copied and validated separately; status only exposes last path, not every block or its sample array.",
            "timing_limits": "Native start/stop strings are opaque. READY/ACK are client observations, not hardware trigger timestamps. Actual on-time/action overlap and all file content require post-audit.",
            "known_timing_discrepancy": "Prior1200nominal yielded600wall.7200nominal may yield3600wall but actual duration, block continuity and all stage overlap require measurement. No hard trigger alignment or gap-free fullcycle coverage is claimed.",
            "action_coverage_budget": "Use min((7200-nativeElapsed)/2,3600-hostAgeSinceStartClaim); each writer needs its own full finite coverage. This recorder does not authorize or schedule a junction action.",
            "safe_tip_scope": "SafeTip is required Off before Start. The500pA property is recorded but inactive; this passive recorder is not a substitute protection mechanism and cannot stop/retract the junction.",
            "sources": [{"path": str(f), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for f in sources]})
        before = snapshot("before")
        state_guard(before, args.mode)
        timing_guard(before)
        require(before["Util.VersionGet"][2:] == [15331, 15331], "Unreviewed release")
        require([before["Signals.NamesGet"][2][i] for i in b.CHANNELS] == b.NAMES, "Signal map differs")
        require(b.native_path(before["Util.SessionPathGet"][1]) == b.native_path(args.expected_session_path), "Session path differs")
        initial = b.status_values(before["DataLog.StatusGet"])
        require(not initial["start"] or initial["stop"], "Existing start without stop; no takeover")
        time.sleep(1)
        require(get_status("idle_confirmation") == initial, "Existing logger state changes; no takeover")
        for i, (command, values) in enumerate(settings(args.basename, args.duration)):
            claim(command, values, f"config_{i+1}")
            q(command, values)
            name = command[:-3] + "Get"; v = q(name)
            store.save(f"config_{i+1}_readback.json", {**a.stamp(), "command": name, "values": v})
            if i == 0:
                require(v == [6, b.CHANNELS], "DataLog channels differ")
            else:
                profile({"DataLog.ChsGet": q("DataLog.ChsGet"), "DataLog.PropsGet": v}, args.basename, args.duration)
        stable_begin = time.monotonic()
        while True:
            poll("prestart_static_poll", True)
            if time.monotonic() - stable_begin >= 5:
                break
            time.sleep(.5)
        get_profile("prestart")
        require(get_status("prestart") == initial, "DataLog changed before Start")
        start_ref = claim("DataLog.Start", [], "start")
        started = True; result["start_attempted"] = True
        start_mono = time.monotonic()
        q("DataLog.Start")
        result["start_acknowledged"] = True
        store.event("start_acknowledged", start_claim=start_ref)
        pending_stop = None; last_profile_mono = -1e9
        while time.monotonic() - start_mono < args.duration + 15:
            s = get_status("acquiring")
            fresh = bool(s["start"] and s["start"] != initial["start"])
            if fresh and new_start is None:
                new_start = s["start"]
            if new_start is not None and s["start"] != new_start:
                owns_start = False
                raise RuntimeError("Native start identity changed; do not Stop an unidentified acquisition")
            poll("dynamic_state_poll", False)
            if time.monotonic() - last_profile_mono >= 2:
                verified_profile = get_profile("acquiring")
                last_profile_mono = time.monotonic()
            fresh_stop = fresh and bool(s["stop"] and s["stop"] != initial["stop"])
            if not ready:
                require(not fresh_stop, "Native acquisition ended before READY; no action should begin")
                if fresh and (s["elapsed_s"] >= .25 or s["points_counter"] > 0) and s["elapsed_s"] < args.duration - 5:
                    # Recheck immediately before publishing ready. Root owns the action.
                    verified_profile = get_profile("ready")
                    ready_data = {**a.stamp(), **session_binding(args.session), "ready": True, "basename": args.basename,
                        "output_directory": str(store.root), "native_start_identity": new_start,
                        "native_status": s, "profile": verified_profile, "start_claim": start_ref,
                        "native_duration_s": args.duration,
                        "nominal_remaining_setting_units": max(0, args.duration - s["elapsed_s"]),
                        "actual_remaining_seconds": None,
                        "duration_warning": "1200nominal previously covered600wall.7200nominal extrapolates to3600wall; native header/timing and all-stage overlap require audit. Nominal remaining units are not guaranteed wall coverage.",
                        "freshness_required": "Root checks this record and latest datalog_status <=2s old, no outcome.json, and process alive immediately before its own action. READY alone is not ongoing proof.",
                        "no_hardware_trigger_or_atomic_alignment": True,
                        "junction_actions_permitted_by_recorder": False}
                    store.save("READY.json", ready_data)
                    ready = True; result["ready_written"] = True
                    store.event("ready_published", native_status=s)
                    print(json.dumps({"READY": str(store.root / "READY.json"), "basename": args.basename}), flush=True)
                require(ready or time.monotonic() - start_mono < 8, "No start/progress within8s; READY withheld")
            if fresh_stop:
                require(s["elapsed_s"] >= args.duration - .5,
                        "Native stopped before nominal setting elapsed; preserve partial record")
                if pending_stop == s:
                    terminated = True
                    result["final_native_status"] = s
                    result["client_seconds_since_Start_attempt_at_stop_confirmation"] = time.monotonic() - start_mono
                    result["actual_record_coverage_seconds"] = None
                    result["actual_on_time_requires_native_file_audit"] = True
                    break
                pending_stop = s
            else:
                pending_stop = None
            time.sleep(.5)
        require(terminated, "No stable fresh native stop before finite completion deadline")
        require(s["last_saved_path"], "Native stop observed but saved path empty")
        for path in paths:
            if PureWindowsPath(path).name.casefold().startswith(args.basename.casefold()):
                require(b.native_path(str(PureWindowsPath(path).parent)) == b.native_path(args.expected_native_directory), "Native file directory differs")
        require(PureWindowsPath(s["last_saved_path"]).name.casefold().startswith(args.basename.casefold()), "Final basename differs")
        after = snapshot("after")
        # Deliberately no junction/static guard here: the recorder does not diagnose actions.
        profile(after, args.basename, args.duration)
        timing_guard(after)
        result["status"] = "native_timed_record_stopped_files_and_action_overlap_pending_audit"
    except Exception as exc:
        result.update(status="recorder_failed_no_retry", error=f"{type(exc).__name__}: {exc}",
                      junction_failure_diagnosis="not_made")
        try:
            cleanup(result["error"])
        except Exception as cleanup_error:
            result["cleanup_error"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
        if started and not c._closed and not abort and global_deadline - time.monotonic() > 3:
            try:
                snapshot("after_failure")
            except Exception as followup:
                result["after_failure_snapshot_error"] = f"{type(followup).__name__}: {followup}"
        elif started:
            store.save("after_failure.json", {**a.stamp(), "enumeration_completed": False,
                "unavailable": "Connection closed, termination requested or deadline exhausted; no reconnect."})
    finally:
        c.close()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        result.update(native_stop_confirmed=terminated, observed_last_paths=sorted(paths),
                      all_file_paths_known=False, must_check_native_ui_if_unconfirmed=started and not terminated)
        store.save("outcome.json", {**a.stamp(), **result})
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return int(result["status"] == "recorder_failed_no_retry")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--duration", type=int, choices=ALLOWED_DURATIONS, default=7200, help="7200nominal only; historical ratio suggests3600wall, unverified for this duration")
    ap.add_argument("--session", choices=[f"session_{i:02d}" for i in range(1, 6)], required=True)
    ap.add_argument("--mode", choices=("withdraw", "stable"), required=True)
    ap.add_argument("--basename")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--expected-session-path")
    ap.add_argument("--expected-native-directory")
    ap.add_argument("--ui-evidence", type=Path)
    args = ap.parse_args()
    args.output = args.output or HERE / args.session / "logger"
    args.basename = args.basename or "dl_goal30_FIVE1102_" + args.session.upper()
    session_binding(args.session)
    duration_fields(args.duration)
    if not args.execute:
        print(json.dumps({"socket_opened": False, **session_binding(args.session), "output": str(args.output), "settings": settings(args.basename, args.duration),
            "start_at_most_once": True, "ready": "Fresh native start + elapsed/points progress after ACK and profile verification",
            "before_start": mode_description(args.mode),
            "context_screenshot_only": True, "logger_idle_evidence": "unchanged stopped DataLog.StatusGet across >=1s and rechecked prestart",
            "after_start": "observe junction state only", "junction_writes": 0,
            "duration_nominal_units": args.duration, "prior_factor_wall_estimate_s_not_guarantee": args.duration / 2,
            "overall_deadline_s": args.duration + 80, "native_completion_wait_s": args.duration + 15, "bounded_cleanup_network_budget_s": 6,
            "local_disk_reserve_bytes": MIN_LOCAL_FREE_BYTES, "native_disk_free_verified": False,
            "fixed_sampling_readbacks": EXPECTED_TIMING, "native_block_samples_documented": 25000,
            "expected_full_blocks_at_prior_factor_not_guaranteed": args.duration * 1000 // 25000,
            "expected_partial_points_at_prior_factor_not_guaranteed": args.duration * 1000 % 25000,
            "parent_full_review_before_execution": True}, indent=2))
        return 0
    if any(v is None for v in (args.output, args.expected_session_path, args.expected_native_directory, args.ui_evidence)):
        ap.error("--output, both --expected-... paths and --ui-evidence required")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
