#!/usr/bin/env python3
"""Offline byte/link audit of this publication; no device/network dependencies."""
from pathlib import Path
import hashlib,json,re,urllib.parse,sys
P=Path(__file__).resolve().parent
REPO=P.parents[2]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check():
 failures=[];checks=[]
 manifest=P/'package_files.sha256'
 if not manifest.is_file():raise SystemExit('package_files.sha256 missing')
 listed={}
 for line in manifest.read_text().splitlines():
  h,rel=line.split('  ',1);q=(P/rel).resolve()
  if not q.is_relative_to(P) or not q.is_file():failures.append('missing/unsafe '+rel);continue
  listed[rel]=h
  if digest(q)!=h:failures.append('hash mismatch '+rel)
 checks.append({'name':'package_sha256','files':len(listed),'passed':not failures})
 actual={str(q.relative_to(P)) for q in P.rglob('*') if q.is_file() and q.name not in {'package_files.sha256','offline_pack_verification.json'} and '__pycache__' not in q.parts}
 if actual!=set(listed):failures.append('inventory differs: '+repr(sorted(actual^set(listed))))
 idx=json.loads((P/'source_hash_index.json').read_text());trans=json.loads((P/'transformation_index.json').read_text())
 for f in idx['files']:
  q=P/f['export_path']
  if not q.is_file() or q.stat().st_size!=f['export_bytes'] or digest(q)!=f['export_sha256']:failures.append('source/export record mismatch '+f['export_path'])
  if f['byte_identical'] and f['source_sha256']!=f['export_sha256']:failures.append('invalid byte-identical claim '+f['export_path'])
 checks.append({'name':'source_export_records','files':len(idx['files'])})
 omission=json.loads((P/'omitted-evidence.json').read_text());oids={x['id'] for x in omission['omissions']}
 relcount=0
 for t in trans['transformations']:
  for c in t['changes']:
   if c.get('kind')=='included_or_previous_package_relative_path':
    q=(P/t['export_path']).parent/c['exported'];relcount+=1
    if not q.is_file():failures.append('JSON rewritten path missing '+str(q))
   if c.get('kind')=='local_archive_reference_not_download':
    if c['exported'].split(':',1)[-1] not in oids:failures.append('unknown omitted ID')
 checks.append({'name':'portable_JSON_paths','rewritten_paths':relcount})
 links=0
 docs=[q for q in P.rglob('*') if q.is_file() and q.suffix in {'.md','.html'}]
 docs += [REPO/'README.md',REPO/'skill/stm-au111-tip-conditioning/references/local-au111-protocol.md']
 for q in docs:
  text=q.read_text();vals=re.findall(r'\]\(([^)]+)\)',text) if q.suffix=='.md' else re.findall(r'(?:href|src)=["\']([^"\']+)["\']',text)
  for val in vals:
   if re.match(r'^[a-z]+:',val) or val.startswith('#'):continue
   pathpart=urllib.parse.unquote(val.split('#',1)[0]);target=(q.parent/pathpart).resolve();links+=1
   if not target.is_relative_to(REPO) or not target.is_file():failures.append('bad document link '+str(q)+' -> '+val)
 checks.append({'name':'document_links','files':len(docs),'links':links})
 expected={201:'c7df6426519e54fbdcc5586ce1c321b207fb62741294b1e3f7424d86a401f5cf',202:'c723c9fb50e500cfb85563d424fc235e393a44b4deae7995c5e25a7ed6beb8c4',203:'975d29bb4d842297b641aaf94f3cca1a9d61d72a57ec9ed9d8bdc6c7ff7dae92',204:'e89e3d10c60cc3dd230d5eda8dacd09030e38797fa6f168dee0883087af2d5b9',205:'b0056330eed4b7ce1f642d094c9cde90ab0d8c2500958783ac45b04408a66364'}
 for number,h in expected.items():
  qs=list(P.rglob(f'BM261029_{number:05d}.sxm'))
  if len(qs)!=1 or digest(qs[0])!=h:failures.append('full SXM altered/missing '+str(number))
 checks.append({'name':'original_complete_SXM','count':5,'TCP_reverification':'not performed; raw TCP streams omitted, original bitmatch audit retained'})
 actions=json.loads((P/'actual_actions.json').read_text());wanted={'completed_full_attempts':1,'requested':5,'remaining':4,'strict_successful_cycles':0,'episode_pulses_consumed':3,'new_pulses_in_R02_R03':0,'new_TipShaper_Start':0,'successful_inductions_in_this_increment':0}
 if actions['counts']!=wanted:failures.append('counts changed')
 for e in actions['events']:
  for w in e['actual_writer_claims']:
   if w['command'] in ['Bias.Pulse','TipShaper.Start']:failures.append('unexpected new conditioning writer')
 checks.append({'name':'counts_and_actual_writer_summary','events':len(actions['events'])})
 raw=json.loads((P/'raw_archives_not_uploaded.json').read_text());counts={x:sum(r['segment']==x for r in raw['files']) for x in ['R02','R03']}
 if counts!={'R02':93,'R03':732}:failures.append('initial frozen raw manifest count differs')
 checks.append({'name':'initial_frozen_DataLog_manifest','blocks':counts,'raw_bytes_included':False,'hash_basis':'root frozen receipt; this portable check cannot hash omitted DataLog'})
 forbidden={'.exe','.dll','.dmg','.chm','.pdf','.dat','.bin','.jsonl','.whl','.so','.dylib','.pyc'}
 for q in P.rglob('*'):
  if q.is_file() and q.suffix.lower() in forbidden:failures.append('forbidden bundled type '+str(q))
 checks.append({'name':'excluded_vendor_runtime_rawdump_types','passed':not any('forbidden bundled' in x for x in failures)})
 result={'all_checks_passed':not failures,'checks':checks,'failures':failures,'payload_files':len(listed),'payload_bytes':sum((P/r).stat().st_size for r in listed),'limits':['Verifies exported bytes and paths, not instrument correctness or missing raw TCP bitmatches.','Source hashes are original provenance; exported JSON/document hashes differ by declared path transformations.','No online or hardware calls.']}
 print(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':sys.exit(0 if check()['all_checks_passed'] else 1)
