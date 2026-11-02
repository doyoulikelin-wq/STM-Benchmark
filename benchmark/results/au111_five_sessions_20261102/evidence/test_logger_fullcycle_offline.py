#!/usr/bin/env python3
"""Offline tests only: block every socket/DNS entry before importing logger."""
import ast, contextlib, copy, hashlib, importlib.util, io, json, socket, struct, sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
TARGET=HERE/'logger_fullcycle_once.py'
checks=[]; network=[]
def blocked(*args,**kw):
    network.append(repr(args)); raise AssertionError('network forbidden')
def reject(label, fn):
    try: fn()
    except (RuntimeError,ValueError): checks.append(label)
    else: raise AssertionError('accepted '+label)
def ast_function(tree,name):
    found=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    assert len(found)==1,name
    return ast.dump(found[0],include_attributes=False)
def main():
    tree=ast.parse(TARGET.read_text())
    with patch.object(socket,'socket',blocked),patch.object(socket,'create_connection',blocked),patch.object(socket,'getaddrinfo',blocked):
        spec=importlib.util.spec_from_file_location('offline_fullcycle_logger',TARGET)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        output=HERE/'session_05/logger'; existed=output.exists(); stream=io.StringIO()
        with patch.object(sys,'argv',[str(TARGET),'--session','session_05','--mode','stable']),contextlib.redirect_stdout(stream):
            assert m.main()==0
        plan=json.loads(stream.getvalue())
        assert output.exists()==existed and plan['socket_opened'] is False
        assert plan['session_id']=='session_05' and plan['source_sha256']==hashlib.sha256(TARGET.read_bytes()).hexdigest()
        assert plan['duration_nominal_units']==7200 and plan['prior_factor_wall_estimate_s_not_guarantee']==3600
        assert plan['overall_deadline_s']==7280 and plan['native_completion_wait_s']==7215
        assert plan['expected_full_blocks_at_prior_factor_not_guaranteed']==288
        checks.append('actual import/default plan uses no network/no output; source/session/7200/3600/finite7280/7215 metadata')
        assert m.duration_fields(7200)==[2,0,0.]
        for x in [1200,240,0,7199,7201,7200.,True]: reject('reject duration '+repr(x),lambda x=x:m.duration_fields(x))
        for x in ['session_00','session_06','../session_01','session_1',None]:reject('reject session '+repr(x),lambda x=x:m.session_binding(x))
        for i in range(1,6):
            sid=f'session_{i:02d}'; v=m.session_binding(sid)
            assert v=={'session_id':sid,'source_sha256':m.SOURCE_SHA256,'role':'fullcycle_native_logger'}
        checks.append('five exact session bindings')
        with patch.object(Path,'exists',return_value=False):assert m.output_guard(HERE/'session_01/logger','session_01')==HERE/'session_01/logger'
        with patch.object(Path,'exists',return_value=True):reject('existing logger never reused',lambda:m.output_guard(HERE/'session_01/logger','session_01'))
        for x in [HERE/'logger',HERE/'session_01/another',HERE/'session_02/logger']:
            reject('wrong output '+str(x),lambda x=x:m.output_guard(x,'session_01'))
        with patch.object(Path,'resolve',lambda self:self):reject('share refused without walking share',lambda:m.output_guard(HERE/'win_users/logger','session_01'))
        settings=m.settings('dl_goal30_OFFLINE_FULLCYCLE',7200); props=settings[1][1]
        assert props[:5]==[2,2,0,0.,1] and props[-1]==[]
        body=m.p.encode(m.p.COMMANDS['DataLog.PropsSet']['inputs'],props)
        assert struct.unpack('>Hiifi',body[:18])==(2,2,0,0.,1)
        good={'DataLog.ChsGet':[6,m.b.CHANNELS],'DataLog.PropsGet':[1,2,0,0.,1,len(props[5]),props[5],len(m.COMMENT),m.COMMENT]}
        m.profile(good,props[5],7200); checks.append('canonical2hour setter/getter and big-endian codec exact')
        for idx,val in [(0,2),(1,0),(2,120),(3,1.),(4,2)]:
            bad=copy.deepcopy(good);bad['DataLog.PropsGet'][idx]=val
            reject('profile mismatch '+str((idx,val)),lambda bad=bad:m.profile(bad,props[5],7200))
        before=json.loads((HERE/'read_001_initial/snapshot.json').read_text())['values']
        m.state_guard(before,'stable');m.timing_guard(before);checks.append('recorded initial100pA/SafeOff state accepted offline')
        for key,val in [('Bias.Get',[-.1]),('Current.Get',[-121e-12]),('ZCtrl.SetpntGet',[1e-9]),('ZCtrl.StatusGet',[1]),('Scan.StatusGet',[1]),('SafeTip.OnOffGet',[1]),('ZCtrl.ZPosGet',[float('nan')])]:
            bad=copy.deepcopy(before);bad[key]=val;reject('preflight rejects '+key,lambda bad=bad:m.state_guard(bad,'stable'))
        c=m.Client(SimpleNamespace(audit=lambda _:None),props[5],7200)
        assert c.allowed_writes==settings+[('DataLog.Start',[]),('DataLog.Stop',[])]
        for name,args in [('Bias.Pulse',[1,.02,-4.,1,2]),('ZCtrl.SetpntSet',[1e-9]),('Scan.Action',[0,0]),('SafeTip.OnOffSet',[0]),('Util.RTOversamplSet',[10])]:
            c.permit=(name,args);reject('Client rejects junction/sampling '+name,lambda name=name,args=args:c.call(name,args))
        c.permit=None;reject('Client rejects unclaimed Start',lambda:c.call('DataLog.Start',[]));c.close()
        original=ast.parse(m.ORIGINAL.read_text())
        for name in ['mode_description','state_guard','disk_guard','timing_guard','settings','profile','q','snapshot','get_status','get_profile','poll','cleanup']:
            assert ast_function(tree,name)==ast_function(original,name),name
        checks.append('AST equal: state/profile/timing/disk guards, settings, q/snapshot/poll and ownedStop cleanup unchanged')
        starts=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='q' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='DataLog.Start']
        assert len(starts)==1;checks.append('one Start callsite; no scheduling or repeat loop added')
        claimnode=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='claim')
        assert 'session_binding(args.session)' in ast.unparse(claimnode)
        runsrc=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run'))
        assert runsrc.count('**session_binding(args.session)')==4
        checks.append('manifest,READY,claims,result all bind same session/source/role')
        assert not network
    report={'source':str(TARGET),'sha256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),'checks_count':len(checks),'checks':checks,'network_attempts':len(network),'run_function_called':False,'hardware_execution_performed':False,'plan':plan,'limitations':['run/cleanup behavior inherited and AST audited, not hardware tested','7200nominal actual duration unverified','no gap-free fullcycle claim','independent native disk space/root stage budgets required']}
    (HERE/'logger_fullcycle_offline_review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'checks_passed':len(checks),'network_attempts':len(network),'source_sha256':report['sha256']},indent=2))
if __name__=='__main__':main()
