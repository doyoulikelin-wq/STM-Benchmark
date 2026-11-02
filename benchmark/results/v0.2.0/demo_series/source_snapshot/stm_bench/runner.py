from __future__ import annotations
import json
import math
import platform
import time
import shutil
from pathlib import Path
import numpy as np
from .artifacts import Recorder, now, write_json, sha, seal, render_report
from .metrics import image_quality, stability
from .profiles import thresholds_snapshot, resolve_profile
from .policies import POLICIES

SCENARIOS = ("nominal", "noisy", "drift", "double_tip", "no_tunnel", "current_spike", "scan_timeout", "flat", "stale_frame")
EXPECTED = {s: ("success" if s in ("nominal", "noisy") else "reject") for s in SCENARIOS}


def scenario_pass(summary, evidence):
    """Fault credit requires the corresponding measured failure, not abstention."""
    if summary.get("error") or not summary.get("cleanup_ok"): return False
    scenario = summary["scenario"]
    if EXPECTED.get(scenario) == "success": return bool(summary["success"])
    if summary["success"] or summary.get("truncated"): return False
    reason = summary.get("termination_reason") or ""
    judgments = summary.get("judgments", [])
    correct = {j["label"] for j in judgments if j.get("agrees_with_metrics")}
    diagnoses = {j.get("diagnosis") for j in judgments}
    if scenario == "no_tunnel":
        return evidence.get("failed_approach", False) and reason == "approach_not_established"
    if scenario == "current_spike":
        return evidence.get("overcurrent", False) and "protection" in reason.lower()
    if scenario == "scan_timeout":
        return (evidence.get("scan_timeout", False) and reason.startswith("TimeoutError:")
                and summary.get("stages",{}).get("stability",False))
    if scenario == "stale_frame":
        return evidence.get("scan_attempt",False) and any(s in reason.lower() for s in ("stale", "repeated raw scan", "cached"))
    if scenario in ("flat","double_tip","drift") and reason != "agent_retracted": return False
    if scenario == "flat": return "flat" in correct and "flat" in evidence.get("image_labels",[])
    if scenario == "double_tip":
        return ("double_tip" in diagnoses and evidence.get("scan_attempt",False)) or (
            "noisy" in correct and "noisy" in evidence.get("image_labels",[]))
    if scenario == "drift":
        return ("drift" in diagnoses and evidence.get("scan_attempt",False)) or evidence.get("excess_z_drift",False) or evidence.get("unconfirmed_repeat",False) or (
            "noisy" in correct and "noisy" in evidence.get("image_labels",[]))
    return False


def protocol(profile="strict-v1"):
    package = Path(__file__).resolve().parent
    return {"version": "0.2.0", "created": now(), "profile": profile, "thresholds": thresholds_snapshot(profile),
            "scope": "numerical_workflow_not_scientific_image_certification",
            "source_hashes": {p.name: sha(p) for p in sorted(package.iterdir()) if p.suffix in (".py",".json")},
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "required_stable_windows": 2, "required_detail_scans": 2,
            "scientific_ground_truth": "unavailable", "training": "none; frozen rule and random policies"}


def freeze_protocol(root, profile="strict-v1"):
    package=Path(__file__).resolve().parent
    target=Path(root)/"source_snapshot"/"stm_bench"
    target.mkdir(parents=True)
    for p in package.iterdir():
        if p.suffix in (".py",".json"): shutil.copyfile(p,target/p.name)
    write_json(Path(root)/"protocol.json",protocol(profile))


def run_episode(output, *, seed=0, scenario="nominal", policy="rule", backend=None, max_steps=48, case_id=None, profile="strict-v1"):
    from .env import STMEnv
    thresholds = resolve_profile(profile)
    rec = Recorder(output)
    freeze_protocol(rec.root, profile)
    # Keep third-party policy factories implementing the original seed-only API usable.
    if policy in ("rule", "random"):
        agent = POLICIES[policy](seed, profile=profile)
    else:
        agent = POLICIES[policy](seed)
    env = None
    started = time.monotonic()
    error = None
    cleanup = None
    total_reward = 0.
    evidence = {"image_labels": []}
    try:
        if callable(backend): backend = backend(rec.root/"device")
        env = STMEnv(backend=backend, max_steps=max_steps, profile=profile)
        obs, info = env.reset(seed=seed, options={"scenario": scenario})
        rec.event("reset", seed=seed, scenario=scenario, observation=obs, info=info)
        for _ in range(max_steps):
            action = agent.act(obs)
            rec.event("decision", action=action, policy=policy)
            obs, reward, terminated, truncated, info = env.step(action)
            approach = info.get("approach")
            if approach and approach.get("completed") is False: evidence["failed_approach"] = True
            if "window" in info:
                measurement = stability(info["window"], profile=profile)
                evidence["overcurrent"] = evidence.get("overcurrent",False) or measurement.get("protection_triggered",False)
                evidence["excess_z_drift"] = evidence.get("excess_z_drift",False) or measurement.get("z_drift_m_s",0)>thresholds["z_drift_m_s"]
            if action.get("type",action.get("action")) in ("survey","scan"):
                evidence["scan_attempt"] = True
                if info.get("error_type")=="TimeoutError": evidence["scan_timeout"] = True
            if obs.get("latest_frame"):
                label = image_quality(obs["latest_frame"], profile=profile)["label"]
                if label not in evidence["image_labels"]: evidence["image_labels"].append(label)
            repeat = obs.get("repeatability") or {}
            if repeat.get("distinct_acquisitions") and repeat.get("same_context") and repeat.get("correlation") is not None:
                evidence["unconfirmed_repeat"] = evidence.get("unconfirmed_repeat",False) or repeat["correlation"]<thresholds["repeat_corr"]
            total_reward += reward
            rec.event("transition", action=action, observation=obs, reward=reward,
                      terminated=terminated, truncated=truncated, info=info)
            if terminated or truncated:
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        rec.event("exception", error=error)
    finally:
        try:
            cleanup = env.close() if env else {"completed": True, "detail": "backend initialization failed before environment creation"}
            if cleanup is None:
                cleanup = {"completed": True, "detail": "environment close returned no value"}
            rec.event("cleanup", result=cleanup)
        except Exception as exc:
            cleanup = {"completed": False, "error": f"{type(exc).__name__}: {exc}"}
            rec.event("cleanup", result=cleanup)
    summary = env.summary() if env else {"success":False,"score":0,"steps":0,"stages":{}}
    cleanup_ok = bool(cleanup.get("completed", cleanup.get("restored", cleanup.get("success", False))))
    summary.update(backend=getattr(env.backend, "backend", "unknown") if env else "unavailable",
                   seed=seed, scenario=scenario, policy=policy, case_id=case_id or f"{scenario}-{seed}",
                   runtime_s=time.monotonic()-started, total_reward=total_reward, error=error,
                   cleanup=cleanup, cleanup_ok=cleanup_ok, frames=len(rec.frames))
    summary["fault_evidence"] = evidence
    summary["profile"] = profile
    if error or not cleanup_ok:
        summary["success"] = False
        summary["termination_reason"] = "execution_error" if error else "cleanup_failed"
    # Rejection is a scenario test outcome, never substituted for workflow success.
    expected = EXPECTED.get(scenario)
    summary["expected_outcome"] = expected
    summary["task_pass"] = bool(scenario_pass(summary,evidence))
    if summary["backend"] != "synthetic":
        summary["expected_outcome"] = None
        summary["task_pass"] = bool(summary["success"] and cleanup_ok and not error)
    write_json(rec.root/"summary.json", summary)
    render_report(rec.root, summary, rec.previews)
    seal(rec.root)
    return summary, rec.previews


def wilson(success, n):
    if not n: return None
    z = 1.959963984540054
    p = success/n
    d = 1+z*z/n
    center = (p+z*z/(2*n))/d
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0.,center-half), min(1.,center+half)]


def make_cases(split="test", seeds_per_scenario=3, seed_offset=0):
    if type(seed_offset) is not int or seed_offset < 0 or seed_offset+seeds_per_scenario>1000:
        raise ValueError("seed offset plus count must remain in the scenario's 1000-seed block")
    bases = {"train": 100, "dev": 10000, "test": 1000000}
    base = bases[split]
    return [{"id": f"{split}-{s}-{j+seed_offset}", "scenario": s,
             "seed": base+i*1000+j+seed_offset, "split": split, "expected": EXPECTED[s]}
            for i,s in enumerate(SCENARIOS) for j in range(seeds_per_scenario)]


def evaluate(output, *, split="test", seeds_per_scenario=3, policies=("rule", "random"), max_steps=48, profile="strict-v1", seed_offset=0):
    root = Path(output)
    root.mkdir(parents=True,exist_ok=False)
    cases = make_cases(split, seeds_per_scenario, seed_offset)
    freeze_protocol(root, profile)
    write_json(root/"cases.json", cases)
    results, previews = [], []
    for policy in policies:
        for case in cases:
            summary, images = run_episode(root/policy/case["id"], seed=case["seed"], scenario=case["scenario"],
                                          policy=policy, max_steps=max_steps, case_id=case["id"], profile=profile)
            results.append(summary)
            if policy == "rule" and case["scenario"] == "nominal" and len(previews)<3:
                previews.extend(images[:3])
    by_policy = {}
    for policy in policies:
        rows = [r for r in results if r["policy"]==policy]
        passes = sum(r["task_pass"] for r in rows)
        successes = sum(r["success"] for r in rows)
        by_policy[policy] = {
            "episodes": len(rows), "workflow_success": successes, "scenario_tests_passed": passes,
            "scenario_pass_rate": passes/len(rows), "scenario_pass_wilson95": wilson(passes,len(rows)),
            "workflow_success_rate": successes/len(rows),
            "workflow_success_wilson95": wilson(successes,len(rows)),
            "false_accepts_on_faults": sum(r["success"] and r["expected_outcome"]=="reject" for r in rows),
            "mean_score": float(np.mean([r.get("score",0) for r in rows])),
            "mean_steps": float(np.mean([r.get("steps",0) for r in rows])),
            "cleanup_failures": sum(not r["cleanup_ok"] for r in rows),
            "errors": sum(r["error"] is not None for r in rows),
            "completion_tasks": sum(r["expected_outcome"]=="success" for r in rows),
            "correct_completions": sum(r["success"] and r["expected_outcome"]=="success" for r in rows),
            "fault_tasks": sum(r["expected_outcome"]=="reject" for r in rows),
            "correct_fault_rejections": sum(r["task_pass"] and r["expected_outcome"]=="reject" for r in rows),
            "by_scenario": {s:{"count":sum(r["scenario"]==s for r in rows),
                                "passed":sum(r["task_pass"] and r["scenario"]==s for r in rows),
                                "accepted":sum(r["success"] and r["scenario"]==s for r in rows)} for s in SCENARIOS},
        }
    result = {"backend": "synthetic", "split": split, "profile": profile, "seed_offset": seed_offset, "policies": by_policy,
              "aggregate": {"episodes": len(results), "policies": len(policies), "scenarios": len(SCENARIOS)},
              "episodes": results, "limitations": [
                  "Procedural software task generator; not calibrated STM physics.",
                  "Rule baseline implements the published numerical criteria; no learned image understanding is tested.",
                  "Seed separation is not sample, material, session or instrument generalization.",
                  "Confidence intervals describe these constructed cases, not real-world instrument reliability."]}
    write_json(root/"summary.json",result)
    render_report(root,result,previews)
    seal(root)
    return result
