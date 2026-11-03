"""Same local 2 kHz scan audit as 207, pinned to the post-P02 independent-recovery scan."""
import hashlib, importlib.util, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE/'review_native_phases.py'
require_sha = lambda p,s:hashlib.sha256(p.read_bytes()).hexdigest()==s
if not require_sha(BASE,'7543764d9f1d8410169ba10e4e0210d25b50d579e19a196516c7e3bd7b9fe111'):
    raise RuntimeError('R06 phase helper changed')
spec=importlib.util.spec_from_file_location('R06_full_after_P02_recovery_local',BASE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.RUN=m.S/'after_R06_P02_recovery_full'
m.SCAN_SHA='c30f251302f30d0bf8b5e204bf5ccaac066a08acf677ccd98d48bfbc89ee94f6'
if not require_sha(m.C/'scan_full50nm_fast_R06_after_P02_recovery_once.py',m.SCAN_SHA):
    raise RuntimeError('After-P02-independent-recovery scan source changed')
original_phase_plan=m.phase_plan
def plan(*args):
    phases,brackets,why=original_phase_plan(*args)
    phases=[('pre_after_P02_recovery_mixed_prior_experiment' if label=='pre_Start_nominal_fixed' else label,l,r)
            for label,l,r in phases]
    return phases,brackets,why

if __name__=='__main__':
    m.__file__=str(Path(__file__).resolve())
    m.phase_plan=plan
    m.main()
