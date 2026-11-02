# Implementation contract v0.2

Two backends share an API. Synthetic data must always be labelled `synthetic`; actual TCP acquisition is `nanonis_demo`. Never claim synthetic results are instrument measurements. All SI units unless stated.

Backend methods:

- `reset(seed: int, scenario: str) -> dict`: snapshot; synthetic reset deterministic, Demo reset bounded preparation with saved initial state.
- `snapshot() -> dict`: feedback_on, setpoint_A, p_gain_m, time_constant_s, line_time_s, z_range_m, frame (cx_m, cy_m, width_m, height_m, angle_deg), backend.
- `approach() -> dict`: approach evidence, including completed bool and method; bounded timeout, no mere ACK considered completion.
- `configure(params: dict) -> dict`: allowed keys p_gain_m, time_constant_s, line_time_s, setpoint_A; verified snapshot returned.
- `sample(count=32) -> dict`: current_A and z_m lists, dt_s, feedback_on, setpoint_A, z_range_m, unique window_id, monotonic started_s/ended_s. Each call is a fresh nonoverlapping window.
- `scan(kind: str) -> dict`: id, backend, kind, z_forward, z_backward, current_forward, current_backward (2D numpy arrays, same orientation), frame, setpoint_A, z_range_m, fresh bool, lifecycle list of integer scan states (must include 1 then 0), elapsed_s. Optional raw_paths and acquisition metadata. All frame arrays raw and unmodified.
- `move_roi(roi: dict) -> dict`: ROI x,y in [0,1] and size in [0.15,0.5], referenced to latest survey frame, including rotation transform. Returns verified snapshot. Coordinates use x increasing column, y increasing row; frame arrays mapped consistently; physical convention documented by backend.
- `retract() -> dict`: stop owned operations and retract/disable feedback in verified simulator only.
- `close() -> dict`: restore captured settings, save cleanup evidence; failures surfaced, no silent PASS.

Metrics module: `stability(window, profile="strict-v1") -> dict` with `stable`, metrics; `image_quality(frame, profile="strict-v1") -> dict` with `acceptable`, `label` (good/noisy/flat/saturated/incomplete), metrics; `choose_roi(frame, profile="strict-v1") -> dict` x,y,size; `repeatability(a,b, profile="strict-v1") -> dict` with `confirmed` and correlation. Registered thresholds are immutable in `profiles.PROFILES`; the selected name and exact thresholds are frozen in each run's protocol. `metrics.THRESHOLDS` remains a compatibility reference to strict-v1. Relaxed-v1 changes only five numerical quality tolerances; protection, evidence freshness and required sample/frame counts stay fixed.

Environment: `STMEnv(backend=None, max_steps=48, profile="strict-v1")`; `reset(seed=0, options=None) -> (obs,info)` scenario from options; `step(action:dict) -> (obs,reward,terminated,truncated,info)`; `close()`. Actions: approach, observe, configure (params dict), survey, select_roi (roi dict), scan, judge (label string, optional diagnosis), accept, retract. Obs includes stage, action_mask (list names), profile, snapshot, latest stability/image metrics, latest frame (arrays permitted), budgets and last_error. The profile stays fixed for the environment lifetime; reference policies should use the same profile. Two consecutive fresh stable windows required before survey; survey quality gate before ROI; two same-context fresh detail scans plus agent judge=good then accept required for successful episode. Configuration/move invalidates old stability and image confirmations. Stable windows cannot be reused. Stages & score evidence explicit. No hidden scenario/ground truth in agent observation. Failures/budget stop in bounded time. JSONL logs owned by runner. Env exposes summary() dict with success, profile, stages and score parts.

Synthetic scenarios: nominal, noisy, drift, double_tip, no_tunnel, current_spike, scan_timeout, flat, stale_frame. Scenario choices explicit in benchmark manifest, not agent obs. Offline world is a software task generator, not calibrated STM physics. Raw truth only for evaluator, no scientifically meaningful accuracy claims.
