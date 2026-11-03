"""R06 local immutable-DAT and scan-outcome audit. No hardware connections."""
import argparse
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import re
import sys

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parents[1]
S = C.parent/'session_02'
L = S/'logger_06'
RUN = S/'baseline_segment06_full'
PREFIX = 'dl_goal30_FIVE1102_SESSION_02_R06'
LOGGER_SHA = '527e5b5f3a7d542415c9efda6506818f64a8a910848766c34d37508fbed53184'
SCAN_SHA = 'f55c58f30a29d9f5ebf908c49298e81d857878e4c1954b1e3a895a4f4803558d'
LOGGER_IDENTITY_PINS = {'READY.json': '463890eb80aae4f6889e35d1c5c8db72c96f5a74fba28b01180b56f956cc7b10', 'start.claim': '8bf28a7714098f399911fc67ee20f7fca7c8b4b0da13ffb033b186fea8412e0f', 'manifest.json': 'b76ff6805ed590ca123d24b864848065ba14e26ea5fed18ade1f2f8afb581c7f'}
helper_path = C/'R04_expert_continuation/review_fixed_native.py'
if hashlib.sha256(helper_path.read_bytes()).hexdigest()!='70d4fc7778537337a0b6ead0bee865bf1bb5d424031d92c08208722633445361':
    raise ValueError('Local parser/statistics helper changed')
spec = importlib.util.spec_from_file_location('fixed_native_parser',helper_path)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
np, require, DT, BLOCK = h.np, h.require, h.DT, h.FULL_ROWS


def events(path, kinds):
    raw = h.local(path).read_bytes()
    lines = raw.splitlines(keepends=True)
    if lines and not lines[-1].endswith(b'\n'):
        lines.pop()
    records = []
    for line in lines:
        row = json.loads(line)
        if row.get('kind') in kinds:
            records.append(row)
    return records, {'path':str(path),'complete_prefix_bytes':sum(map(len,lines)),
                     'complete_prefix_sha256':h.sha(b''.join(lines))}


def log_anchors(rows, native_id):
    anchors = []
    pattern = re.compile(re.escape(PREFIX)+r'(\d{5})\.dat$')
    for e in rows:
        v = e['raw_values']
        if len(v)!=10 or v[1]!=native_id or v[6]:
            continue
        match = pattern.fullmatch(re.split(r'[\\/]',v[8])[-1])
        if not match:
            continue
        block, counter = int(match[1]),v[9]
        require(block>=1 and type(counter) is int and 0<=counter<=BLOCK,'Malformed R06 native file index/counter')
        sample = (block-1)*BLOCK+counter
        # During a file rotation, the published basename can lag the reset counter or vice versa.
        # Keep only clock-consistent status observations, so a stale name cannot shift a boundary by 12.5s.
        nominal_half = (v[2]*3600+v[3]*60+v[4])/2
        if abs(sample*DT-nominal_half)>2.:
            continue
        if anchors and sample<anchors[-1]['sample']:
            continue
        anchors.append({'monotonic_ns':e['monotonic_ns'],'utc':e['utc'],'block':block,
                        'points_counter':counter,'sample':sample,'native_s':sample*DT,
                        'elapsed_nominal_half_s':nominal_half})
    return anchors


def bracket(anchors, lo, hi):
    before = [a for a in anchors if a['monotonic_ns']<=lo]
    after = [a for a in anchors if a['monotonic_ns']>=hi]
    if not before or not after:
        return None
    left, right = before[-1], after[0]
    if lo-left['monotonic_ns']>5e9 or right['monotonic_ns']-hi>5e9:
        return None
    return {'before':left,'after':right,'host_before_ns':lo,'host_after_ns':hi}


def phase_plan(outcome, rows, start, start_ack, anchors, count):
    status = outcome['status']
    unknown = [('complete_archive_without_attribution',0,count)]
    if start is None and status=='rejected_before_start' and outcome.get('start_attempted') is False:
        return [('no_scanner_Start_full_archive',0,count)],{},'rejected_before_start'
    if not start or not start_ack or start_ack.get('values')!=[] or start_ack.get('warning'):
        return unknown,{},'scanner Start/ACK missing or ambiguous'
    require(start.get('command')=='Scan.Action' and start.get('args')==[0,0] and start['source_sha256']==SCAN_SHA,
            'Wrong scan Start identity')
    active = [r for r in rows if r['kind'] in ('running_observed','scan_guard') and r['values'].get('Scan.StatusGet')==[1]]
    if not active:
        return unknown,{},'Start ACK without positive running observation'
    entry = bracket(anchors,start['monotonic_ns'],active[0]['monotonic_ns'])
    if not entry:
        return unknown,{},'insufficient matching logger counter bracket for start'
    if status=='completed' and outcome['completed_frame_confirmed']:
        stop_time = outcome['end_event']['monotonic_ns']
        end_scope = 'known_completed_native_WaitEnd'
    else:
        post = next((r for r in rows if r['kind']=='post_stop' and r['values']['Scan.StatusGet']==[0]),None)
        wait_end = next((r for r in rows if r['kind']=='wait_end' and r['values'][0]==0 and r['values'][2]),None)
        if wait_end and outcome.get('end_event_confirmed'):
            stop_time = wait_end['monotonic_ns']
            end_scope = 'native_end_but_frame_not_fully_validated'
        elif post and outcome.get('stop_acknowledged'):
            stop_time = post['monotonic_ns']
            end_scope = 'owned_Stop_and_nonrunning_readback_incomplete_scan'
        else:
            return unknown,{'start':entry},'no independently bounded known-end; full raw support only'
    observed = [r for r in active if r['monotonic_ns']<=stop_time]
    require(bool(observed),'No sampled native running state preceding end')
    last = observed[-1]
    end = bracket(anchors,last['monotonic_ns']-math.ceil(last['duration_s']*1e9),stop_time)
    if not end:
        return unknown,{'start':entry},'missing native counter bracket for end'
    a,b,c,d = entry['before']['sample'],entry['after']['sample'],end['before']['sample'],end['after']['sample']
    if not 0<=a<=b<=c<=d<=count:
        return unknown,{'start':entry,'end':end},'closed archive not yet sufficient or brackets overlap'
    return [('pre_Start_nominal_fixed',0,a),('Start_boundary_and_positioning',a,b),
            ('scan_core_between_observations',b,c),('end_boundary',c,d),('post_event_context_unclassified',d,count)],{'start':entry,'end':end},end_scope


def stats(a,lo,hi,sp,limits):
    if hi<=lo:
        return {'rows':0,'zero_based_sample_half_open':[lo,hi]}
    v = a[lo:hi]
    output = h.describe(v,lo,sp)
    current,z = v[:,0],v[:,2]
    result = {}
    for level in [400,1000,4000]:
        mask = abs(current)>=level
        edges = np.diff(np.r_[False,mask,False].astype(int))
        starts, ends = np.flatnonzero(edges==1),np.flatnonzero(edges==-1)
        j = int(np.argmax(ends-starts)) if len(starts) else None
        result[str(level)] = {'sample_count':int(mask.sum()),'groups':len(starts),
            'longest_samples':int(ends[j]-starts[j]) if j is not None else 0,
            'longest_native_seconds_half_open':[(lo+starts[j])*DT,(lo+ends[j])*DT] if j is not None else None}
    output['abs_I_sample_exceedances_pA'] = result
    output['matches_historical_negative_digitizer_value_samples'] = int(np.isclose(current,-9999.4768,atol=.00005,rtol=0).sum())
    first,last = np.median(z[:200]),np.median(z[-200:])
    dz = np.diff(z)
    j = int(np.argmax(abs(dz))) if len(dz) else None
    margin = np.minimum(limits[1]-z,z-limits[0])
    output['Z_changes'] = {'median_last_minus_first_upto100ms_pm':float((last-first)*1000),
        'maximum_single_adjacent_change_pm_signed':float(dz[j]*1000) if j is not None else None,
        'pair_first_native_s':(lo+j)*DT if j is not None else None,
        'endpoint_limits_nm_low_high':limits,'minimum_distance_to_either_limit_nm':float(margin.min()),
        'rows_within_2nm_of_endpoint':int((margin<2.).sum())}
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--last',type=int,required=True,help='Closed contiguous blocks 1 through this index')
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    path = h.local(args.output)
    require(not path.exists() and path.parent.is_dir(),'New output JSON path required')
    rr, receipt_ref = h.read_json(args.receipt)
    ready, ready_ref = h.read_json(L/'READY.json')
    logger_start, lsref = h.read_json(L/'start.claim')
    require(all(h.sha(h.local(L/name).read_bytes())==digest for name,digest in LOGGER_IDENTITY_PINS.items()),
            'Changed R06 recorder READY, claim or manifest')
    bound,bound_ref = h.read_json(RUN/'logger_ready_bound.json') if (RUN/'logger_ready_bound.json').is_file() else (None,None)
    manifest,mref = h.read_json(RUN/'manifest.json')
    out,oref = h.read_json(RUN/'outcome.json')
    require(all(j['session_id']=='session_02' and j['recording_segment_id']=='R06' for j in [rr,ready,manifest,logger_start])
            and (bound is None or bound==ready) and ready['source_sha256']==logger_start['source_sha256']==LOGGER_SHA
            and ready['start_claim']['sha256']==lsref['sha256'] and logger_start['command']=='DataLog.Start' and logger_start['args']==[]
            and manifest['source_sha256']==SCAN_SHA and manifest['event_id']==RUN.name
            and manifest['logger_source_sha256']==LOGGER_SHA and manifest['logger_directory']==str(L)
            and ready['profile']['DataLog.ChsGet']==[6,[0,24,30,98,99,100]]
            and rr['native_start_identity']==ready['native_start_identity']
            and ready['basename']==PREFIX and ready['ready'] is True,'Scan/recording/receipt provenance differs')
    require(1<=args.last<=rr['complete_through_index'],'Requested file not archived')
    data, files = [], []
    for block in range(1,args.last+1):
        name = f'{PREFIX}{block:05d}.dat'
        meta = rr['files'][name]
        pp = h.local(S/'native_R06'/name)
        require(str(pp)==meta['local_path'],'Wrong archive path')
        raw = pp.read_bytes()
        require(len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256'], 'Size or SHA mismatch')
        require((meta.get('source_double_read_sha_equal') and meta.get('local_reread_sha_equal')) or
                (meta.get('two_source_reads_same_sha') and meta.get('local_reread_matches')), 'Archival copy verification missing')
        rows = meta['rows']
        terminal = meta.get('terminal') and rr.get('all_blocks_including_last_archived') and block==rr['complete_through_index']
        require(rows==BLOCK or (terminal and 0<=rows<=BLOCK),'Malformed partial block')
        if rows:
            data.append(h.parse_block(raw,rows))
        else:
            require(raw.splitlines()[-1].decode('ascii').strip().split('\t')==h.CHANNELS
                    and b'Sample Period (ms)\t5.000E-1' in raw,'Empty terminal header differs')
        files.append({'path':str(pp),'rows':rows,'sha256':meta['sha256']})
    a = np.concatenate(data)
    del data
    before, pref = h.read_json(L/'before.json')
    v = before['values'];sp = v['ZCtrl.SetpntGet'][0]*1e12
    limits = sorted(f*1e9 for f in v['ZCtrl.LimitsGet'])
    start, sref = h.read_json(RUN/'scan_start.claim') if (RUN/'scan_start.claim').exists() else (None,None)
    require(start is None or bound==ready,'Started scan lacks same native READY binding')
    ack, aref = h.read_json(RUN/'scan_start_ack.json') if (RUN/'scan_start_ack.json').exists() else (None,None)
    ev,er = events(RUN/'events.jsonl',{'running_observed','scan_guard','post_stop','wait_end','post_roll_guard'})
    lev,lr = events(L/'events.jsonl',{'datalog_status'})
    anchors = log_anchors(lev,ready['native_start_identity'])
    phases,brackets,why = phase_plan(out,ev,start,ack,anchors,len(a))
    output = {'scope':'R06 continuous electrical record and host-bracketed diagnostic scan. Raw files retained byte-for-byte.',
        'source_sha256':h.sha(Path(__file__).read_bytes()),'native_start':rr['native_start_identity'],
        'scan_outcome':out['status'],'phase_interpretation':why,
        'complete_scan_interval_bracketed_in_closed_blocks':why=='known_completed_native_WaitEnd' and set(brackets)=={'start','end'},'is_complete_frame':out.get('completed_frame_confirmed',False),
        'native_archive_blocks_inclusive':[1,args.last], 'includes_terminal':bool(rr.get('all_blocks_including_last_archived') and args.last==rr['complete_through_index']),
        'rows':len(a),'dt_s':DT,'setpoint_reference_pA':sp,'native_columns':h.CHANNELS,
        'full':stats(a,0,len(a),sp,limits),'brackets':brackets,
        'phases':{k:stats(a,l,r,sp,limits) for k,l,r in phases},
        'ten_second_windows':[],
        'limits':['Whole record includes every requested closed native row. Phase windows partition it without overlap. Host readbacks and file counters are asynchronous; window edges are not hardware triggers, and the scan may natively reposition.',
                  'Consecutive 10s blocks are frozen from the start of each phase, with any short tail retained. No window selected by signal quality.',
                  'Raster Z includes topography, piezo motion and control response. No stationary noise/drift or physical gap interpretation during scanning; post_end may contain subsequent actions.',
                  'The native nominal elapsed counter runs about twice sample wall time. Explicit file/points anchors only; no mapping to exact scan lines or pixels.',
                  'Current thresholds and historical floor matching are sample descriptors, with neither calibrated analog peak nor image-quality attribution.'],
        'inputs':{'receipt':receipt_ref,'native_blocks':files,'scan_outcome':oref,'scan_manifest':mref,'scan_start_claim':sref,
                  'scan_start_ack':aref,'logger_ready':ready_ref,'logger_start':lsref,'bound_logger_ready':bound_ref,
                  'logger_before':pref,'logger_events':lr,'scan_events':er}}
    for k,l,r in phases:
        for start_index in range(l,r,h.WINDOW):
            stop_index = min(start_index+h.WINDOW,r)
            d = stats(a,start_index,stop_index,sp,limits)
            output['ten_second_windows'].append(dict(phase=k,partial_tail=stop_index-start_index<h.WINDOW,**d))
    require(sum(x['rows'] for x in output['phases'].values())==len(a)==sum(w['rows'] for w in output['ten_second_windows']),
            'Phase or window accounting failed')
    with path.open('x') as f:
        json.dump(output,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'path':str(path),'sha256':h.sha(path.read_bytes()),'phase_interpretation':why,'outcome':out['status'],
                      'rows':len(a),'phase_rows':{k:x['rows'] for k,x in output['phases'].items()}}))


if __name__=='__main__':
    main()
