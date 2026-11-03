"""Pure local JSON helper for the root operator. No instrument import or command.

This constructs inputs for the existing frozen validator. It never selects image
quality or native recovery automatically, never creates a hardware claim, and never
runs a stage. Each stage review must precede its newly acquired full snapshot.
"""
import argparse,copy,hashlib,importlib.util,json,os,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
BINDING=HERE/'full02_binding.py'
BINDING_SHA='8a67b3fce04b8e52b88a001b0433c4fa76b79a7f5efdc5fa9bf0fbd68b454aee'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(BINDING)!=BINDING_SHA:raise RuntimeError('Frozen stage binding changed')
_spec=importlib.util.spec_from_file_location('S02_root_input_validator',BINDING)
b=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(b)
TEMPLATE=HERE/'S02_full02_admission.INACTIVE.template.json'
TEMPLATE_SHA='808db2395220b8a4a262d6a62caf8709c7dce0cd6cea3f3bf0a4b4028c73f409'
STAGE_TEMPLATE=HERE/'S02_full02_stage_review.INACTIVE.template.json'
STAGE_TEMPLATE_SHA='7410b2a147dcd32d0d994b716e563350162d0e6d3b499d01fc5e21898ea7f257'

def template(path,digest):
    b.require(sha(path)==digest,'Input template changed');return b.load(path)
def reference(path,digest):
    r={'path':str(b.local(path)),'sha256':digest};b.artifact(r);return r

def build_admission(manual_path,manual_sha,*,root_selected,sole_writer,reason):
    b.require(root_selected is True and sole_writer is True and isinstance(reason,str) and reason.strip(),
              'Root must explicitly select this finite candidate and confirm sole writer')
    d=template(TEMPLATE,TEMPLATE_SHA)
    manual_ref=reference(manual_path,manual_sha);manual=b.artifact(manual_ref)
    baseline=b.completed_baseline(b.LOGGER_SHA)
    quality=b.ref(b.BASE_DIR/'analysis/quality_report.json')
    b.require(manual.get('full_task_usable') is True and manual.get('baseline_outcome')==baseline['outcome.json']
              and manual.get('baseline_quality')==quality,'Actual completed215 usable review must bind exact outcome/quality')
    after=b.load(b.BASE_DIR/'after_frames.json')['values']
    xy=after['FolMe.XYPosGet'];b.require(len(xy)==2 and all(abs(x+25e-9)<=2e-12 for x in xy),'Actual completed frame did not end at original corner')
    d.update(INACTIVE=False,allow_one_finite_induction_frame=True,baseline_task_usable=True,exclusive_root_writer=True,
             baseline=baseline,baseline_quality=quality,baseline_manual_review=manual_ref,fixed_xy_m=list(xy),
             prior_claim_inventory=[b.ref(p) for folder in ('claims','globalclaims')
                 for p in sorted((b.N/folder).glob('*.claim'))],reason=reason,created_monotonic_ns=time.monotonic_ns())
    d.pop('note',None)
    for stage in b.ORDER:b.stage_source(d,stage)
    # Also rejects an already attempted S02 without declaring it a new experiment.
    b.claim_inventory(d,'induction')
    return d

def build_review(admission_path,admission_sha,stage,native_path,native_sha,*,root_selected,native_passed,no_unresolved_writer,reason):
    b.require(root_selected is True and native_passed is True and no_unresolved_writer is True
              and isinstance(reason,str) and reason.strip(),'Root must explicitly select this stage after independent native review')
    path=b.local(admission_path);d=b.admission(path,admission_sha)
    b.ADMISSION_PATH,b.ADMISSION_SHA=path,admission_sha
    b.require(stage in b.ORDER[3:],'Only future continuation stages permitted');b.stage_source(d,stage);b.claim_inventory(d,stage)
    # A stage review is prospective. Re-running or replacing an already reserved stage is forbidden.
    b.require(not b.stage_claim(stage).exists() and not (b.S/b.EVENTS[stage]).exists(),'This stage already has an output or reservation; no replay')
    prior={previous:b.completed_stage(d,previous) for previous in b.ORDER[:b.ORDER.index(stage)]}
    native_ref=reference(native_path,native_sha)
    r=template(STAGE_TEMPLATE,STAGE_TEMPLATE_SHA)
    r.update(INACTIVE=False,stage=stage,allow_stage=True,no_unresolved_writer=True,
             induction_admission={'path':str(path),'sha256':admission_sha},native_review=native_ref,
             native_review_passed=True,monotonic_ns=time.monotonic_ns(),
             predecessor_outcomes={k:v['refs']['outcome.json'] for k,v in prior.items()},reason=reason)
    for k in ('note','stage_choices'):r.pop(k,None)
    return r

def serialize(doc):return (json.dumps(doc,ensure_ascii=False,indent=2)+'\n').encode()
def validate_prospective(doc,kind,admission_path=None,admission_sha=None):
    # Temporary local JSON only, removed immediately. Never an instrument or action reservation.
    with tempfile.TemporaryDirectory(prefix='_S02_full02_input_check_',dir=HERE) as temp:
        p=Path(temp)/'input.json';p.write_bytes(serialize(doc));digest=sha(p)
        if kind=='admission':b.admission(p,digest)
        else:b.validate_stage(admission_path,admission_sha,doc['stage'],p,digest)

def write_new(path,doc):
    p=b.local(path)
    b.require(p.suffix=='.json' and p.parent in (HERE,b.S),'Output must be one new root input JSON at S root or R07_scan_induction_S02')
    raw=serialize(doc);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'path':str(p),'sha256':sha(p)}

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='kind',required=True)
    a=sub.add_parser('admission');r=sub.add_parser('review')
    for p in (a,r):
        p.add_argument('--output',type=Path,required=True);p.add_argument('--root-selected',action='store_true')
        p.add_argument('--reason',required=True)
    a.add_argument('--manual-review',type=Path,required=True);a.add_argument('--manual-review-sha256',required=True);a.add_argument('--sole-writer',action='store_true')
    r.add_argument('--admission',type=Path,required=True);r.add_argument('--admission-sha256',required=True)
    r.add_argument('--stage',choices=b.ORDER[3:],required=True);r.add_argument('--native-review',type=Path,required=True);r.add_argument('--native-review-sha256',required=True)
    r.add_argument('--native-passed',action='store_true');r.add_argument('--no-unresolved-writer',action='store_true')
    x=ap.parse_args()
    if x.kind=='admission':
        doc=build_admission(x.manual_review,x.manual_review_sha256,root_selected=x.root_selected,sole_writer=x.sole_writer,reason=x.reason)
        validate_prospective(doc,'admission')
    else:
        doc=build_review(x.admission,x.admission_sha256,x.stage,x.native_review,x.native_review_sha256,
                         root_selected=x.root_selected,native_passed=x.native_passed,no_unresolved_writer=x.no_unresolved_writer,reason=x.reason)
        validate_prospective(doc,'review',x.admission,x.admission_sha256)
    result=write_new(x.output,doc)
    if x.kind=='admission':b.admission(result['path'],result['sha256'])
    else:b.validate_stage(x.admission,x.admission_sha256,x.stage,result['path'],result['sha256'])
    print(json.dumps({**result,'frozen_validator_passed':True,'instrument_called':False,'hardware_claim_created':False,
                     'next':'Root acquires a new complete snapshot after the stage review, then independently executes only that stage.'},indent=2))
if __name__=='__main__':main()
