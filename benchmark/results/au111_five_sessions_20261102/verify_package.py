"""Local SHA/membership verification only; no controllers or network APIs."""
from pathlib import Path
import hashlib
root=Path(__file__).resolve().parent
fail=[];expected=set()
for line in (root/'package_files.sha256').read_text().splitlines():
    digest,name=line.split('  ',1)
    expected.add(name)
    p=(root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
        fail.append(name)
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='package_files.sha256'}
fail.extend('unlisted: '+name for name in sorted(actual-expected))
print({'files_checked':len(expected),'failures':fail})
raise SystemExit(bool(fail))
