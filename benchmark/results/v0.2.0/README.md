# Portable benchmark evidence

Open [report.html](report.html) for the overview. [Synthetic comparison](profile_comparison/report.html) retains paired outcomes and every episode summary; [Demo series](demo_series/report.html) includes each trial's events, metadata and complete NPZ measurement arrays.

`manifest.json` verifies this exported tree. `source_manifest.json` files preserve original full-run manifests unchanged. They cannot validate this partial export: raw device/wire logs, synthetic arrays/events and duplicate snapshots were omitted. See each `export_notes.json` for exact omitted/transformed file lists and the original manifest hash. Absolute local paths in exported JSON are redacted by default. Redacted `raw_paths` describe omitted acquisition files; portable arrays are under each Demo trial's `frames/` directory. Source runs were not modified.

These results concern generated software tasks and a Nanonis Demo session, not real hardware scientific image certification.
