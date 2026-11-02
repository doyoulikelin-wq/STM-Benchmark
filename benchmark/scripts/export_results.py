"""Export a portable, explicitly partial evidence bundle without editing runs.

Run after both experiment series have completed and produced manifest.json:
    python scripts/export_results.py --benchmark-root D:\\STM\\stm_agent_benchmark
Existing output directories are always refused. Raw device/wire logs stay local.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
from stm_bench.artifacts import render_report


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def portable_json(value):
    """Redact local absolute path strings, preserving evidence hashes and values."""
    if isinstance(value, dict):
        return {key: portable_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_json(item) for item in value]
    if isinstance(value, str):
        win, posix = PureWindowsPath(value), PurePosixPath(value)
        if win.is_absolute() or posix.is_absolute():
            name = win.name if win.is_absolute() else posix.name
            return "[local path omitted]/" + name
        # Error messages may contain an absolute Windows path inside prose.
        return re.sub(r"(?<!\w)(?:[A-Za-z]:[\\/]|\\\\)[^\s\"'<>]+",
                      "[local path omitted]", value)
    return value


def seal_export(root):
    root = Path(root)
    files = {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*"))
             if p.is_file() and p != root / "manifest.json"}
    write_json(root / "manifest.json", {"algorithm": "sha256", "files": files})


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Source reference escapes its series: {relative!r}")
    return path


class EvidenceSubset:
    """Preserve the original manifest separately from the curated export seal."""
    def __init__(self, source, output, redact=True):
        self.source, self.output, self.redact = Path(source), Path(output), redact
        self.original = read_json(self.source / "manifest.json")
        if self.original.get("algorithm") != "sha256" or not isinstance(self.original.get("files"), dict):
            raise ValueError(f"Unsupported source manifest: {self.source.name}")
        self.output.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(self.source / "manifest.json", self.output / "source_manifest.json")
        self.selected, self.transformed = set(), set()
        self.relocated = {}

    def copy(self, relative, *, transform=None, raw=False):
        relative = Path(relative).as_posix()
        source, target = within(self.source, relative), within(self.output, relative)
        expected = self.original["files"].get(relative)
        if expected is None or digest(source) != expected:
            raise ValueError(f"Selected evidence is absent or changed from source manifest: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not raw and source.suffix == ".json":
            value = read_json(source)
            if transform:
                value = transform(value)
            write_json(target, portable_json(value) if self.redact else value)
        elif not raw and source.suffix == ".jsonl":
            with source.open(encoding="utf-8") as src, target.open("w", encoding="utf-8") as dst:
                for line in src:
                    value = json.loads(line)
                    dst.write(json.dumps(portable_json(value) if self.redact else value,
                                         ensure_ascii=False, allow_nan=False) + "\n")
        else:
            shutil.copyfile(source, target)
        self.selected.add(relative)
        if digest(target) != expected:
            self.transformed.add(relative)

    def snapshot(self):
        for relative in sorted(self.original["files"]):
            if relative.startswith("source_snapshot/"):
                self.copy(relative, raw=True)

    def include_child(self, name, child):
        """Account for nested exports in the parent original-manifest inventory."""
        selected = set(child.selected) | {"manifest.json"}
        for relative in selected:
            source_relative = f"{name}/{relative}"
            if self.original["files"].get(source_relative) != digest(within(child.source, relative)):
                raise ValueError(f"Nested evidence differs from parent source manifest: {source_relative}")
            self.selected.add(source_relative)
        self.transformed.update(f"{name}/{relative}" for relative in child.transformed)
        self.relocated[f"{name}/manifest.json"] = f"{name}/source_manifest.json"
        self.relocated.update({f"{name}/{key}": f"{name}/{value}" for key, value in child.relocated.items()})

    def finish(self, *, shared_source_snapshot=None):
        write_json(self.output / "export_notes.json", {
            "kind": "curated_partial_evidence_export",
            "source_manifest_file": "source_manifest.json",
            "source_manifest_sha256": digest(self.source / "manifest.json"),
            "source_original_file_count": len(self.original["files"]),
            "source_files_verified_before_export": sorted(self.selected),
            "transformed_original_files": sorted(self.transformed),
            "relocated_original_files": self.relocated,
            "omitted_original_files": sorted(set(self.original["files"]) - self.selected),
            "absolute_json_paths_redacted": self.redact,
            "shared_source_snapshot": shared_source_snapshot,
            "integrity_scope": "manifest.json verifies this exported tree only. source_manifest.json is an unchanged record of the original full run; auditing that original manifest against this partial export is expected to fail.",
            "omissions": "Raw device/wire logs and duplicate source snapshots remain local. Synthetic episode events and arrays are omitted; all synthetic episode outcomes remain in profile summaries. Demo NPZ files retain the full unmodified measurement arrays. Redacted raw_paths refer to omitted local acquisition files, not files in this bundle.",
        })
        seal_export(self.output)


def report_with_links(root, summary, previews=(), links=()):
    render_report(root, summary, previews)
    path = Path(root) / "report.html"
    nav = "<nav>" + " · ".join(f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
                              for label, url in links) + "</nav>"
    page = path.read_text(encoding="utf-8")
    path.write_text(page.replace("<h1>STM Agent Benchmark</h1>", "<h1>STM Agent Benchmark</h1>" + nav), encoding="utf-8")


def frame_previews(root):
    previews = []
    for path in sorted((Path(root) / "frames").glob("*.npz")):
        metadata = read_json(path.with_suffix(".json"))
        with np.load(path, allow_pickle=False) as arrays:
            z = np.asarray(arrays["z_forward"], dtype=float)
            step = max(1, z.shape[0] // 96)
            previews.append({"id": metadata["id"], "kind": metadata.get("kind"), "data": z[::step, ::step]})
    return previews


def completed_source(path):
    for name in ("plan.json", "summary.json", "protocol.json", "manifest.json"):
        if not (path / name).is_file():
            raise ValueError(f"Source series is incomplete: {path.name}/{name} is missing")


def export_results(benchmark_root, output="results/v0.2.0", comparison="runs/profile_comparison_v020",
                   demo_series="runs/relaxed_demo_series_v020", redact=True):
    benchmark_root = Path(benchmark_root).resolve()
    source_comparison = (benchmark_root / comparison).resolve()
    source_demo = (benchmark_root / demo_series).resolve()
    output = (benchmark_root / output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists; choose a new directory: {output}")
    if any(output.is_relative_to(source) or source.is_relative_to(output)
           for source in (source_comparison, source_demo)):
        raise ValueError("Export output must not overlap either source series")
    completed_source(source_comparison)
    completed_source(source_demo)
    comparison_summary, demo_summary = read_json(source_comparison / "summary.json"), read_json(source_demo / "summary.json")
    profiles = read_json(source_comparison / "plan.json")["profiles"]
    trial_names = [row["evidence_directory"] for row in demo_summary["episodes"]]
    if len(trial_names) != len(set(trial_names)):
        raise ValueError("Duplicate Demo trial directories")
    # Validate all required files and shared source identities before creating output.
    for source, children, required in ((source_comparison, profiles, ("summary.json", "cases.json", "protocol.json", "manifest.json")),
                                       (source_demo, trial_names, ("summary.json", "protocol.json", "events.jsonl", "manifest.json"))):
        shared_hashes = read_json(source / "protocol.json")["source_hashes"]
        for child in children:
            directory = within(source, child)
            for name in required:
                if not (directory / name).is_file():
                    raise ValueError(f"Incomplete source evidence: {child}/{name}")
            if read_json(directory / "protocol.json")["source_hashes"] != shared_hashes:
                raise ValueError(f"Cannot deduplicate changed source snapshot: {child}")
    output.mkdir(parents=True, exist_ok=False)
    marker = output / "EXPORT_INCOMPLETE.txt"
    marker.write_text("Export has not completed. Do not publish this directory.\n", encoding="utf-8")
    compact = {key: value for key, value in comparison_summary.items() if key != "episodes"}
    paired = EvidenceSubset(source_comparison, output / "profile_comparison", redact)
    for name in ("plan.json", "protocol.json"):
        paired.copy(name)
    paired.copy("summary.json", transform=lambda _: compact)
    paired.snapshot()
    for profile in profiles:
        subset = EvidenceSubset(within(source_comparison, profile), within(paired.output, profile), redact)
        for name in ("summary.json", "cases.json", "protocol.json"):
            subset.copy(name)
        report_with_links(subset.output, read_json(subset.output / "summary.json"), links=[("Comparison", "../report.html")])
        subset.finish(shared_source_snapshot="../source_snapshot")
        paired.include_child(profile, subset)
    report_with_links(paired.output, read_json(paired.output / "summary.json"),
                      links=[(profile, f"{profile}/report.html") for profile in profiles])
    paired.finish()
    demo = EvidenceSubset(source_demo, output / "demo_series", redact)
    for name in ("plan.json", "summary.json", "protocol.json"):
        demo.copy(name)
    demo.snapshot()
    final_previews = []
    for trial in trial_names:
        subset = EvidenceSubset(within(source_demo, trial), within(demo.output, trial), redact)
        for name in ("summary.json", "protocol.json", "events.jsonl"):
            subset.copy(name)
        for relative in sorted(subset.original["files"]):
            path = PurePosixPath(relative)
            if path.parent.as_posix() == "frames" and path.suffix in (".json", ".npz"):
                subset.copy(relative)
        previews = frame_previews(subset.output)
        final_previews.extend(previews[-1:])
        report_with_links(subset.output, read_json(subset.output / "summary.json"), previews,
                          links=[("Demo series", "../report.html")])
        subset.finish(shared_source_snapshot="../source_snapshot")
        demo.include_child(trial, subset)
    report_with_links(demo.output, read_json(demo.output / "summary.json"), final_previews,
                      links=[(trial, f"{trial}/report.html") for trial in trial_names])
    demo.finish()
    exported = {
        "kind": "portable_curated_stm_benchmark_results", "version": "0.2.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "absolute_json_paths_redacted": redact,
        "aggregate": {"synthetic_episodes": comparison_summary["aggregate"]["episodes"],
                      "paired_cases": comparison_summary["aggregate"]["paired_cases"],
                      "demo_completed": demo_summary["aggregate"]["completed"],
                      "demo_successes": demo_summary["aggregate"]["successes"]},
        "profile_comparison": "profile_comparison/summary.json", "demo_series": "demo_series/summary.json",
        "integrity": "Each manifest.json seals the exported files in its directory tree. Original full-run manifests are separately preserved as source_manifest.json; omitted or transformed files prevent full-source audit equivalence.",
        "scope": "Synthetic tasks and same-session Nanonis Demo measurements; not real instrument scientific validation.",
    }
    write_json(output / "export.json", exported)
    report_with_links(output, exported, final_previews,
                      [("Profile comparison", "profile_comparison/report.html"), ("Demo series", "demo_series/report.html")])
    (output / "README.md").write_text(
        "# Portable benchmark evidence\n\nOpen [report.html](report.html) for the overview. "
        "[Synthetic comparison](profile_comparison/report.html) retains paired outcomes and every episode summary; "
        "[Demo series](demo_series/report.html) includes each trial's events, metadata and complete NPZ measurement arrays.\n\n"
        "`manifest.json` verifies this exported tree. `source_manifest.json` files preserve original full-run manifests unchanged. "
        "They cannot validate this partial export: raw device/wire logs, synthetic arrays/events and duplicate snapshots were omitted. "
        "See each `export_notes.json` for exact omitted/transformed file lists and the original manifest hash. "
        "Absolute local paths in exported JSON are redacted by default. Redacted `raw_paths` describe omitted acquisition files; "
        "portable arrays are under each Demo trial's `frames/` directory. Source runs were not modified.\n\n"
        "These results concern generated software tasks and a Nanonis Demo session, not real hardware scientific image certification.\n",
        encoding="utf-8")
    marker.unlink()
    seal_export(output)
    return exported


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--output", default="results/v0.2.0", help="New output path, relative to benchmark root or absolute")
    parser.add_argument("--comparison", default="runs/profile_comparison_v020")
    parser.add_argument("--demo-series", default="runs/relaxed_demo_series_v020")
    parser.add_argument("--keep-local-paths", action="store_true", help="Keep absolute paths in JSON instead of redacting them")
    args = parser.parse_args(argv)
    result = export_results(args.benchmark_root, args.output, args.comparison, args.demo_series,
                            redact=not args.keep_local_paths)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
