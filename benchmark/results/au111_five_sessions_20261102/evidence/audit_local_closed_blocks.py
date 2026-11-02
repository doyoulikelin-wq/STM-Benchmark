#!/usr/bin/env python3
"""Local-only closed DAT audit; no instrument, share, network or control imports."""
import argparse, hashlib, json, math, re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHANNELS=['Current (A)','Bias (V)','Z (m)','Z Control signal (A)','Z Error signal (A)','Z SafeTip signal (A)']
def sha(data):return hashlib.sha256(data).hexdigest()
def inside(path):
    p=Path(path).resolve()
    if not p.is_relative_to(ROOT) or 'win_users' in p.parts:raise ValueError('Local new-run path only')
    return p
def audit(receipt, output, through):
    receipt=inside(receipt);output=inside(output)
    if type(through) is not int or through<1:raise ValueError('Positive finite through-index required')
    raw=receipt.read_bytes();r=json.loads(raw);selected=[]
    for name,f in r['files'].items():
        match=re.search(r'(\d{5})\.dat$',name)
        if match and int(match[1])<=through:selected.append((int(match[1]),name,f))
    selected.sort()
    if [x[0] for x in selected]!=list(range(1,through+1)):raise ValueError('Missing/duplicate requested closed block index')
    output.mkdir(parents=True,exist_ok=False)
    (output/'receipt_at_review.json').write_bytes(raw)
    reports=[];total=0;sum_i=0.;sumsq_i=0.;counts={str(v):0 for v in [400,1000,9990]};rail_total=0;overall_min=(math.inf,None);overall_max=(-math.inf,None)
    for index,name,entry in selected:
        if entry.get('terminal_copy_requires_independent_Stop_review') or entry.get('last_path_index_at_copy',0)<=index:
            raise ValueError('This initial closed-block tool requires later path identity; terminal block review is separate')
        p=inside(entry['local_path'])
        if p.name!=name:raise ValueError('Filename mismatch')
        blob=p.read_bytes()
        if sha(blob)!=entry['sha256'] or len(blob)!=entry['bytes']:raise ValueError('SHA/size mismatch '+name)
        lines=blob.decode().splitlines();mark=lines.index('[DATA]');header=lines[:mark]
        if lines[mark+1].split('\t')!=CHANNELS:raise ValueError('Unexpected channels')
        dt=float(next(x for x in header if x.startswith('Sample Period (ms)')).split('\t')[1])*1e-3
        if dt!=.0005:raise ValueError('Unexpected native dt')
        rowcount=0;mini=(math.inf,None);maxi=(-math.inf,None);minz=math.inf;maxz=-math.inf;maxdz=(0.,None);prev=None;localcounts={str(v):0 for v in [400,1000,9990]};rail=0;bias_min=math.inf;bias_max=-math.inf;si=0.;ssi=0.;rail_runs=[];run_start=None
        for line in lines[mark+2:]:
            if not line.strip():continue
            values=[float(v) for v in line.split('\t')]
            if len(values)!=6 or not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite/malformed native row')
            i,b,z=values[:3];pos=rowcount;rowcount+=1;si+=i;ssi+=i*i
            mini=min(mini,(i,pos));maxi=max(maxi,(i,pos));minz=min(minz,z);maxz=max(maxz,z);bias_min=min(bias_min,b);bias_max=max(bias_max,b)
            if prev is not None and abs(z-prev)>maxdz[0]:maxdz=(abs(z-prev),pos)
            prev=z
            for t in localcounts:
                if abs(i)>=int(t)*1e-12:localcounts[t]+=1
            at_rail=abs(i-(-9.9994768e-9))<=1e-18
            if at_rail:
                rail+=1
                if run_start is None:run_start=pos
            elif run_start is not None:rail_runs.append([run_start,pos-1]);run_start=None
        if run_start is not None:rail_runs.append([run_start,rowcount-1])
        if rowcount!=entry['rows'] or rowcount!=25000:raise ValueError('Expected complete25000row block')
        avg=si/rowcount;sd=math.sqrt(max(0,ssi/rowcount-avg*avg))
        report={'index':index,'path':str(p),'sha256':sha(blob),'bytes':len(blob),'rows':rowcount,'dt_s':dt,'header_duration_s':rowcount*dt,'saved_date_header':next(x for x in header if x.startswith('Saved Date')).split('\t')[1],'all6columns_finite':True,'current_min_A':mini[0],'current_min_zero_index':mini[1],'current_max_A':maxi[0],'current_max_zero_index':maxi[1],'current_mean_A':avg,'current_RMS_about_mean_A':sd,'abs_current_ge_pA_counts':localcounts,'historical_negative_rail_matching_count':rail,'rail_runs_inclusive_zero_index':rail_runs,'bias_min_max_V':[bias_min,bias_max],'Z_min_max_m':[minz,maxz],'max_within_block_adjacent_abs_Z_m':maxdz[0],'max_Z_jump_later_zero_index':maxdz[1]}
        reports.append(report);total+=rowcount;sum_i+=si;sumsq_i+=ssi;rail_total+=rail
        for t in counts:counts[t]+=localcounts[t]
        if mini[0]<overall_min[0]:overall_min=(mini[0],{'block':index,'zero_index':mini[1]})
        if maxi[0]>overall_max[0]:overall_max=(maxi[0],{'block':index,'zero_index':maxi[1]})
    avg=sum_i/total
    result={'scope':'Requested prefix of root-copied closed local DAT only; not entire running logger or completed session','source_receipt':str(receipt),'source_receipt_sha256':sha(raw),'audit_script_sha256':sha(Path(__file__).read_bytes()),'native_start_identity':r['native_start_identity'],'through_index':through,'rows_per_channel':total,'finite_scalars':6*total,'dt_s':.0005,'header_duration_sum_s':total*.0005,'current_min_A':overall_min[0],'current_min_location':overall_min[1],'current_max_A':overall_max[0],'current_max_location':overall_max[1],'current_mean_A':avg,'current_RMS_about_mean_A':math.sqrt(max(0,sumsq_i/total-avg*avg)),'abs_current_ge_pA_counts':counts,'historical_negative_rail_matching_count':rail_total,'all_bias_minus1':all(x['bias_min_max_V']==[-1.,-1.] for x in reports),'blocks':reports,'limits':['No SMB/source_path access; only local_path opened','Header sample sum and adjacent block indices do not prove physical gap-free acquisition','Saved Date and DataLog elapsed/counter are asynchronous; no hard pixel or event clock alignment','All-prefix current RMS mixes phases; not stationary noise or tip quality','No physiological/physical current bound: sampled extrema and no matching rail do not prove analog chain unsaturated','Terminal block, full7200 duration and before/action/after coverage require later independent audit']}
    (output/'review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--receipt',required=True);a.add_argument('--output',required=True);a.add_argument('--through-index',type=int,required=True);args=a.parse_args();r=audit(args.receipt,args.output,args.through_index);print(json.dumps({k:r[k] for k in ['through_index','rows_per_channel','finite_scalars','header_duration_sum_s','current_min_A','current_min_location','abs_current_ge_pA_counts','historical_negative_rail_matching_count','all_bias_minus1']},indent=2))
