"""Portable evidence retains provenance without pretending to be a full run."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.export_results import digest, export_results, portable_json, seal_export, write_json
from stm_bench.artifacts import audit


def snapshot(root):
    path = root / "source_snapshot" / "stm_bench" / "stub.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Frozen experiment source\n", encoding="utf-8")
    write_json(root / "protocol.json", {"source_hashes": {"stub.py": digest(path)}, "profile": "strict-v1"})


def source_fixture(root):
    comparison, demo = root / "runs/profile_comparison_v020", root / "runs/relaxed_demo_series_v020"
    rows = [{"case_id": "test-nominal-100", "policy": "rule", "success": True,
             "task_pass": True, "score": 98.9, "termination_reason": "verified_task_success"}]
    snapshot(comparison)
    write_json(comparison / "plan.json", {"profiles": ["strict-v1", "relaxed-v1"]})
    for profile in ("strict-v1", "relaxed-v1"):
        child = comparison / profile
        snapshot(child)
        write_json(child / "summary.json", {"episodes": rows, "aggregate": {"episodes": 1}})
        write_json(child / "cases.json", [{"id": "test-nominal-100"}])
        write_json(child / "omitted_episode/events.json", {"raw": "local-only"})
        seal_export(child)
    write_json(comparison / "summary.json", {"episodes": rows * 2, "aggregate": {"episodes": 2, "paired_cases": 1},
                                            "paired_outcomes": [{"strict_pass": True, "relaxed_pass": True}]})
    seal_export(comparison)
    snapshot(demo)
    trial = demo / "trial_01_reference_64"
    snapshot(trial)
    row = {**rows[0], "evidence_directory": trial.name}
    write_json(trial / "summary.json", row)
    frame = {"id": "frame-a", "kind": "detail", "raw_paths": {
        "z_forward": {"path": "C:\\Users\\private name\\local\\z.npy", "sha256": "original-channel-hash"}}}
    write_json(trial / "frames/frame_000.json", frame)
    array = np.arange(256, dtype=float).reshape(16, 16) * 1e-12
    np.savez_compressed(trial / "frames/frame_000.npz", **{key: array for key in
                        ("z_forward", "z_backward", "current_forward", "current_backward")})
    (trial / "events.jsonl").write_text(json.dumps({"event": "transition", "info": {"acquired_frame": {
        **frame, "arrays_path": "frames/frame_000.npz"}}}) + "\n", encoding="utf-8")
    write_json(trial / "device/wire.json", {"local_log": True})
    seal_export(trial)
    write_json(demo / "plan.json", {"recipes": [{"name": "reference_64"}]})
    write_json(demo / "summary.json", {"episodes": [row], "aggregate": {"completed": 1, "successes": 1}})
    seal_export(demo)
    return comparison, demo, trial


def test_export_is_portable_partial_and_does_not_modify_sources(tmp_path):
    comparison, demo, trial = source_fixture(tmp_path)
    before = {p.relative_to(tmp_path).as_posix(): digest(p) for p in (tmp_path / "runs").rglob("*") if p.is_file()}
    result = export_results(tmp_path)
    output = tmp_path / "results/v0.2.0"
    assert result["aggregate"]["synthetic_episodes"] == 2
    assert audit(output)["valid"]
    for manifest in output.rglob("manifest.json"):
        assert audit(manifest.parent)["valid"]
    after = {p.relative_to(tmp_path).as_posix(): digest(p) for p in (tmp_path / "runs").rglob("*") if p.is_file()}
    assert after == before
    compact = json.loads((output / "profile_comparison/summary.json").read_text())
    assert "episodes" not in compact and len(compact["paired_outcomes"]) == 1
    assert len(json.loads((output / "profile_comparison/strict-v1/summary.json").read_text())["episodes"]) == 1
    exported_trial = output / "demo_series" / trial.name
    assert digest(exported_trial / "frames/frame_000.npz") == digest(trial / "frames/frame_000.npz")
    assert digest(exported_trial / "source_manifest.json") == digest(trial / "manifest.json")
    notes = json.loads((exported_trial / "export_notes.json").read_text())
    assert notes["source_manifest_sha256"] == digest(trial / "manifest.json")
    assert "device/wire.json" in notes["omitted_original_files"]
    assert "frames/frame_000.json" in notes["transformed_original_files"]
    assert notes["shared_source_snapshot"] == "../source_snapshot"
    parent_notes = json.loads((output / "demo_series/export_notes.json").read_text())
    assert trial.name + "/frames/frame_000.npz" not in parent_notes["omitted_original_files"]
    assert parent_notes["relocated_original_files"][trial.name + "/manifest.json"] == trial.name + "/source_manifest.json"
    assert not (exported_trial / "device").exists() and not (exported_trial / "source_snapshot").exists()
    assert (output / "demo_series/source_snapshot/stm_bench/stub.py").exists()
    events = (exported_trial / "events.jsonl").read_text(encoding="utf-8")
    assert "private name" not in events and "[local path omitted]/z.npy" in events
    assert "original-channel-hash" in events and "frames/frame_000.npz" in events
    page = (output / "report.html").read_text(encoding="utf-8")
    assert 'href="demo_series/report.html"' in page and "frame-a" in page
    assert not (output / "EXPORT_INCOMPLETE.txt").exists()
    with pytest.raises(FileExistsError): export_results(tmp_path)


def test_export_refuses_unfinished_series_and_changed_selected_evidence(tmp_path):
    with pytest.raises(ValueError, match="incomplete"):
        export_results(tmp_path)
    assert not (tmp_path / "results").exists()
    comparison, _, _ = source_fixture(tmp_path)
    write_json(comparison / "strict-v1/cases.json", [{"changed_after_sealing": True}])
    with pytest.raises(ValueError, match="changed from source manifest"):
        export_results(tmp_path)
    assert (tmp_path / "results/v0.2.0/EXPORT_INCOMPLETE.txt").exists()


def test_portable_json_only_transforms_path_strings():
    value = {"windows": "D:\\data folder\\frame.npy", "unix": "/home/someone/frame.npy",
             "unc": "\\\\host\\share\\frame.npy", "relative": "frames/frame.npy", "number": 1e-9,
             "nested": [{"error": "Unable to open D:\\local\\foo.npy"}]}
    original = deepcopy(value)
    converted = portable_json(value)
    assert converted["windows"] == converted["unix"] == converted["unc"] == "[local path omitted]/frame.npy"
    assert converted["relative"] == value["relative"] and converted["number"] == value["number"]
    assert "D:" not in converted["nested"][0]["error"]
    assert value == original


def test_export_can_preserve_paths_explicitly(tmp_path):
    _, _, trial = source_fixture(tmp_path)
    export_results(tmp_path, redact=False)
    exported = tmp_path / "results/v0.2.0/demo_series" / trial.name / "frames/frame_000.json"
    assert "private name" in exported.read_text(encoding="utf-8")
