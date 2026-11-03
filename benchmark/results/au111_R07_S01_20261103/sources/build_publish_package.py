"""Build a local immutable R07-through-S01 snapshot. No device, network or Git operations."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

C = Path(__file__).resolve().parents[1]
N = C.parent
S = N / 'session_02'
D = C / 'R07_diagnostic'
P = Path(__file__).resolve().parent
cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument('--build-local', action='store_true')
cli.add_argument('--output', type=Path)
cli.add_argument('--report', type=Path)
args = cli.parse_args()
if not args.build_local:
    print('Plan only. Local staging only. Actual completed214/215 and frozen377 receipt required.')
    raise SystemExit(0)
assert args.output and args.report
DEST = args.output.resolve()
assert DEST.is_relative_to(P) and DEST != P and not DEST.exists()

def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(path.read_bytes())
receipt_path = D / 'S01_restored215_post_through377_native_receipt.json'
assert sha(receipt_path.read_bytes()) == 'd0fefe6cf0f47d629a139fdd3405f359f579d0cde98aa6cd4afb50df7e416f6b'
receipt = read(receipt_path)
assert receipt['complete_through_index'] == 377 and receipt['recording_segment_id'] == 'R07'
image_path = C / 'R07_S01_recovered_image_review/post_manual_review.json'
assert sha(image_path.read_bytes()) == '5c474d571e49a2d93df3e8cf719a5ebf804c6329b9dc835ecc509917ab4f5dd7'
assert read(image_path)['full_task_usable'] and read(image_path)['cycle_increment'] == 0
DEST.mkdir(parents=True)
records = []

def save(relative, raw):
    path = DEST / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), relative
    path.write_bytes(raw)
    assert path.read_bytes() == raw
    return path

def copy(source, relative, compress=False):
    source = source.resolve()
    assert source.is_file() and source.is_relative_to(N), source
    raw = source.read_bytes()
    content = gzip.compress(raw, compresslevel=9, mtime=0) if compress else raw
    save(relative, content)
    records.append({'source_path':str(source), 'source_sha256':sha(raw), 'source_bytes':len(raw),
                    'package_path':relative, 'package_sha256':sha(content), 'package_bytes':len(content),
                    'encoding':'gzip' if compress else 'identity'})

def copy_tree_files(folder, relative, suffixes=None):
    for path in sorted(folder.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and (suffixes is None or path.suffix in suffixes):
            copy(path, relative + '/' + str(path.relative_to(folder)))

writer_commands = {'Scan.Action','ZCtrl.Withdraw','ZCtrl.OnOffSet','FolMe.XYPosSet',
                   'ZCtrl.SetpntSet','ZCtrl.GainSet','Scan.SpeedSet'}
def stage(folder, relative):
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix in ('.json','.claim'):
            copy(path, relative+'/'+path.name)
    log = folder/'events.jsonl'
    copy(log, relative+'/events.jsonl.gz', True)
    copied=set()
    for event in map(json.loads,log.read_text().splitlines()):
        if event.get('kind') == 'tcp_exchange' and event.get('command') in writer_commands:
            for key in ('request_header','request_body','response_header','response_body'):
                ref=event[key]
                path=folder/ref['path']
                assert sha(path.read_bytes())==ref['sha256']
                if ref['path'] not in copied:
                    copy(path,relative+'/'+ref['path']);copied.add(ref['path'])

roles=['baseline_segment07_full','baseline_segment07_full02','prepare_R07_S01',
       'configure_R07_S01_gain','configure_R07_S01_speed','induction_R07_S01_full',
       'recovery_R07_S01_H01_gain','recovery_R07_S01_H01_speed','recovery_R07_S01_H01_current',
       'after_R07_S01_recovered_full']
for role in roles:stage(S/role,'evidence/stages/'+role)
for role in ['engage_R07_01','move_R07_home01','engage_R07_02','move_R07_after_S01_home02','engage_R07_03']:
    stage(C/role,'evidence/stages/'+role)
for role,number in [('baseline_segment07_full02','214'),('after_R07_S01_recovered_full','215')]:
    folder=S/role
    assert read(folder/'outcome.json')['status']=='completed'
    quality=read(folder/'analysis/quality_report.json')['integrity']
    assert quality['native_TCP_wire_bitmatch'] and quality['matched_float32_values']==345600
    copy(folder/'native'/f'BM261029_00{number}.sxm',f'raw/BM261029_00{number}.sxm')
    copy_tree_files(folder/'frames',f'evidence/scan{number}/frames')
    copy_tree_files(folder/'analysis',f'evidence/scan{number}/analysis',{'.json','.txt','.npz'})

for name,display in [('partial_buffer_before_fine01','offline_display_v3'),('partial_buffer_after_S01_gain_before_speed','offline_display')]:
    folder=P/name
    stage(folder,'evidence/partial/'+name)
    copy_tree_files(folder/'frames','raw/partial/'+name)
    copy_tree_files(folder/display,'figures/'+name,{'.png'})
    copy(folder/display/'display_record.json','evidence/partial/'+name+'/display_record.json')

for folder_name,images,alias in [('R07_baseline02_image_review','baseline_vs_213','baseline214'),
                                 ('R07_S01_recovered_image_review','recovered_vs_214','recovered215')]:
    folder=C/folder_name
    for path in sorted(folder.glob('*.json')):
        if '.DRAFT.' not in path.name:copy(path,'evidence/image_review/'+alias+'/'+path.name)
    for path in sorted((folder/images).iterdir()):
        if path.suffix=='.png':copy(path,'figures/'+alias+'/'+path.name)
        elif path.suffix=='.json':copy(path,'evidence/image_review/'+alias+'/'+path.name)
    for path in sorted(folder.glob('*.py')):copy(path,'sources/image/'+alias+'/'+path.name)

for path in sorted(D.glob('*.json')):
    if not path.name.startswith('S02') and 'before_wire_resolution' not in path.name and path.name != 'S01_native_auditors_offline_preparation.json':
        copy(path,'evidence/native_audits/'+path.name)
for name in ['interrupted_baseline_native_waveform_v2.png','S01_interrupted_native_waveform_v2.png']:
    copy(D/name,'figures/'+name)
for path in sorted(D.glob('*.py')):
    if 'S02' not in path.name:copy(path,'sources/native/'+path.name)
for folder in [P,C/'R07_fine_recovery']:
    for path in sorted(folder.glob('*.json')):
        if not path.name.startswith('publication_') and not any(x in path.name for x in ['INACTIVE','template','candidate','source_pins','single_stage_entrypoints','logger07_offline_audit.json','logger07_independent_peer_review.json']):
            copy(path,'evidence/root_and_bindings/'+folder.name+'/'+path.name)
for name in ['R07_logger_launch.json','segment07_observe_root_admission.json']:
    path=C/name
    if path.exists():copy(path,'evidence/recorder/'+name)

logger=S/'logger_07'
for name in ['manifest.json','READY.json','start.claim','before.json',
             'recording_segment_reservation.json','config_1.claim','config_1_readback.json','config_2.claim','config_2_readback.json']:
    copy(logger/name,'evidence/recorder/'+name)
# The recorder remains active. Freeze exactly the complete prefix used by the357 full audit.
audit=read(D/'S01_restored215_native_review.json')
logref=audit['inputs']['logger_events']
prefix=(logger/'events.jsonl').read_bytes()[:logref['complete_prefix_bytes']]
assert sha(prefix)==logref['complete_prefix_sha256'] and prefix.endswith(b'\n')
rows=list(map(json.loads,prefix.splitlines()))
filtered=b''.join((json.dumps(e,separators=(',',':'))+'\n').encode() for e in rows if e.get('kind')=='datalog_status')
blob=gzip.compress(filtered,compresslevel=9,mtime=0)
save('evidence/recorder/datalog_status_events_prefix.jsonl.gz',blob)
records.append({'source_path':str(logger/'events.jsonl'),'source_prefix_bytes':len(prefix),
                'source_prefix_sha256':sha(prefix),'package_path':'evidence/recorder/datalog_status_events_prefix.jsonl.gz',
                'package_sha256':sha(blob),'package_bytes':len(blob),'selected_raw_sha256':sha(filtered),
                'selected_rows':len(filtered.splitlines()),'encoding':'gzip_filtered_jsonl_kind_datalog_status'})
start_events=[e for e in rows if e.get('kind')=='tcp_exchange' and e.get('command')=='DataLog.Start']
assert len(start_events)==1
save('evidence/recorder/start_tcp_event.json',(json.dumps(start_events[0],indent=2)+'\n').encode())
for key in ('request_header','request_body','response_header','response_body'):
    r=start_events[0][key];src=logger/r['path'];assert sha(src.read_bytes())==r['sha256'];copy(src,'evidence/recorder/'+r['path'])

controls=['segment07_observe_binding.py','logger_fullcycle_segment07_observe_once.py','archive_closed_native_R07.py',
          'scan_full50nm_fast_R07_baseline_once.py','scan_full50nm_fast_R07_baseline02_once.py',
          'scan_full50nm_fast_R07_induction_S01_once.py','scan_full50nm_fast_R07_after_S01_recovered_5nA_once.py',
          'engage_finez_R07_100pA_once.py','engage_finez_R07_02_100pA_once.py','engage_finez_R07_03_100pA_once.py',
          'move_R07_home_corner_once.py','move_R07_after_S01_home02_once.py',
          'setpoint_R07_scan_induction_S01_once.py','configure_R07_scan_induction_S01_once.py','recover_R07_S01_OffHome_once.py']
for name in controls:copy(C/name,'sources/control/'+name)
for name in ['stage_binding.py','gain_codec_support.py','offhome_recovery_binding.py','post_S01_restoration_binding.py',
             'capture_partial_buffer_before_fine01.py','capture_partial_buffer_after_S01_gain_once.py',
             'render_partial_buffer_local_v3.py','render_S01_partial_buffer_local.py']:
    copy(P/name,'sources/control/'+name)

selected={1,116,126,135,151,152,318,337,346,353,356,357,375,376,377}
for low,high in [(25,29),(60,65),(87,88),(98,101),(186,192),(212,216),(220,224),(230,239),
                 (246,248),(259,261),(267,270),(282,284),(295,299),(310,311)]:
    selected.update(range(low,high+1))
selected=sorted(selected)
for index in selected:
    name=f'dl_goal30_FIVE1102_SESSION_02_R07{index:05d}.dat';meta=receipt['files'][name];source=S/'native_R07'/name
    assert meta['rows']==25000 and meta['local_path']==str(source) and meta['sha256']==sha(source.read_bytes())
    assert source.stat().st_size==meta['bytes'] and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal']
    copy(source,'raw/native/'+name+'.gz',True)
coverage={'scope':'R07 through completed215 and post215 closed block377. Recorder was ongoing at this historical cutoff. No terminal closure is claimed.',
          'frozen_receipt':{'path':str(receipt_path),'sha256':sha(receipt_path.read_bytes())},
          'local_closed_native_blocks':377,'local_closed_native_rows':377*25000,'local_closed_native_seconds':377*12.5,
          'native_dt_s':.0005,'channels':6,'native_stop_observed':False,'includes_terminal':False,
          'uploaded_native_block_indices':selected,'uploaded_native_block_count':len(selected),
          'uploaded_native_rows':len(selected)*25000,'all_native_blocks_uploaded':False,
          'whole_complete_214_and_215_SXM_uploaded':True,'four_scan_buffers_six_planes_each_uploaded':True,
          'selection':'Start block, both interrupted trigger/recovery windows, all three fine-On windows and Home move windows, S01 preparation/configuration/exposure/Home-restoration windows, complete214/215 endpoint and selected peak blocks, selected drift windows, and final375..377 postscan blocks. All other DAT blocks remain local and have hashes in frozen receipts. Raw upload gaps are explicit, not missing acquisition.',
          'recorder_log':'Verified complete prefix frozen by the full215 audit. Filtered DataLog status rows and the unique Start exchange are included. No Stop or terminal outcome is fabricated.',
          'native_index':[dict(index=i,name=name,rows=meta['rows'],bytes=meta['bytes'],sha256=meta['sha256'],uploaded=i in selected) for i,(name,meta) in enumerate(sorted(receipt['files'].items()),1)],
          'counter_state':{'repair_attempts':2,'requested_repair_attempts':5,'remaining_repair_attempts':3,'strict_induced_bad_repair_usable_cycles':0,'shared_pulses':5,'shared_pulse_limit':6,'new_S01_induction_attempts':1,'new_S01_completed_induction_frames':0,'new_S01_repair_attempts':0},
          'excluded_superseded_offline_preparation':['S01_native_auditors_offline_preparation.json references earlier unexecuted candidate analyzer bytes. The original remains local; the final v2 preparation and actual execution audits are published.'],
          'source_runnability':'Published control and analysis copies retain original pinned local dependencies. These are version-audit evidence, not standalone permission to control hardware.',
          'image_assessment_sha256':sha(image_path.read_bytes())}
save('coverage.json',(json.dumps(coverage,indent=2)+'\n').encode())
copy(args.report,'README.md')
copy(P/'publication_image_index.md','IMAGE_INDEX.md')
copy(Path(__file__),'sources/build_publish_package.py')
copy(P/'verify_package.py','verify_package.py')
save('source_index.json',(json.dumps({'records':records},indent=2)+'\n').encode())
files=[{'path':str(p.relative_to(DEST)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(DEST.rglob('*')) if p.is_file()]
save('manifest.json',(json.dumps({'scope':'All payload files, including every nested manifest. Outer manifest excludes only itself.','files':files},indent=2)+'\n').encode())
print(json.dumps({'package':str(DEST),'payload_files':len(files),'source_copies':len(records),'native_gzip_blocks':len(selected),'manifest_sha256':sha((DEST/'manifest.json').read_bytes())}))
