"""Local scientific visualization of existing immutable215/216/217 arrays. No image processing changes."""
from pathlib import Path
import sys,json,hashlib,datetime
sys.dont_write_bytecode=True
sys.path.insert(0,'/Users/maxlin/Desktop/Nanonis/work/ag110_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager
from matplotlib.patches import Rectangle
D=Path(__file__).resolve().parent;C=D.parent;S=C.parent/'session_02';O=D/'three_stage_comparison_v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
roles=[('215','after_R07_S01_recovered_full','原参数基线','100 pA · 0.912 s/方向 · 原增益'),('216','induction_R07_S02_full02','诱导参数曝光','200 pA · 0.456 s/方向 · T加倍'),('217','after_R07_S02_restored_full','恢复原参数','100 pA · 0.912 s/方向 · 原增益')]
expected={'215':'c596a3d1b63d096d4bd035ab9c2df618969ba2313dc764c4dd4195741114a2a6','216':'529032028f5182e0685a24fc3e6d24e4ac22f5942940cd890a4adc448c56a774','217':'e8e207f44c1704b5983672eadf41c6767386048e2fa955328a91893498f15895'}
assert not O.exists();arrays={};sources={}
plan=json.loads((C/'R07_S02_image_review/prospective_S02_plan.json').read_text());bounds=(-.2886687155978507,.40538459700201085)
for label,event,*_ in roles:
 root=S/event;q=json.loads((root/'analysis/quality_report.json').read_text());out=json.loads((root/'outcome.json').read_text());assert out['status']=='completed' and out['completed_frame_confirmed'];assert q['source']['sha256']==expected[label] and sha(q['source']['path'])==expected[label];assert q['integrity']['native_TCP_wire_bitmatch'] and q['integrity']['matched_float32_values']==345600
 npz=root/'analysis/analysis_planes.npz';assert any(r['path']==str(npz) and r['sha256']==sha(npz) for r in q['artifacts']);arrays[label]=np.load(npz);sources[label]={'quality':ref(root/'analysis/quality_report.json'),'outcome':ref(root/'outcome.json'),'raw_SXM':ref(Path(q['source']['path'])),'arrays':ref(npz)}
font=Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
if font.exists():font_manager.fontManager.addfont(font);plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(2,3,figsize=(15.5,10.7),layout='constrained');cmap=plt.get_cmap('afmhot').copy();cmap.set_under('#00b9f2');cmap.set_over('#f000ec');clip={};pitch=50/240
for col,(label,event,role,params) in enumerate(roles):
 for row,direction in enumerate(('F','B')):
  ax=axes[row,col];z=arrays[label]['z'+direction+'_nm'];z=z-np.median(z)
  im=ax.imshow(z,origin='upper',extent=[-25,25,-25,25],interpolation='nearest',cmap=cmap,vmin=bounds[0],vmax=bounds[1]);ax.set_xlabel('名义 X (nm)' if row == 1 else '',fontsize=10)
  ax.set_ylabel(('正扫 F' if row==0 else '反扫 B')+'\n名义 Y (nm)' if col==0 else '名义 Y (nm)',fontsize=11)
  ax.set_title(f'{label}  {role}\n{params}' if row == 0 else '',fontsize=12)
  for key in ('C1','C3','S1'):
   r0,r1,c0,c1=plan['frozen_ROIs'][key];x=-25+c0*pitch;y=25-r1*pitch
   ax.add_patch(Rectangle((x,y),(c1-c0)*pitch,(r1-r0)*pitch,fill=False,linewidth=.65,edgecolor='#61d7ff',alpha=.9));ax.text(x+.15,y+.25,key,color='#61d7ff',fontsize=8)
  clip[label+direction]={'below_display':int((z<bounds[0]).sum()),'above_display':int((z>bounds[1]).sum()),'pixels':z.size,'raw_relative_min_nm':float(z.min()),'raw_relative_max_nm':float(z.max())}
fig.colorbar(im,ax=axes.ravel().tolist(),label='原始 Z 减各帧中位数 (nm)',extend='both',shrink=.79,pad=.02)
fig.suptitle('S02 扫描参数实验  |  基线 → 诱导参数曝光 → 恢复原参数\n六幅图共用已冻结的台阶显示范围，原坐标像素保持',fontsize=16)
fig.supxlabel('青色低于显示下限，品红色高于显示上限。完整原始范围和SXM见配套索引。\nC1/C3/S1框为原固定参照。各图仅减一个中位数，无配准、平滑或逐行校正。',fontsize=11)
O.mkdir();png=O/'215_216_217_FB_frozen_contrast.png';fig.savefig(png,dpi=155);plt.close(fig)
full_links=[D/'exposure216_vs215/full_raw_range.png',D/'restored_vs_215/full_raw_range.png']
record={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Three-column publication display of original baseline215, changed-parameter exposure216 and restored-original217. Not labelled repair before/after.','sources':sources,'frozen_scale_nm':list(bounds),'frozen_scale_origin':ref(C/'R07_S02_image_review/prospective_S02_plan.json'),'original_ROIs':{k:plan['frozen_ROIs'][k] for k in ('C1','C3','S1')},'clipping':clip,'raw_arrays_unchanged':True,'scalar_offset':'one full-frame median per direction','registration':False,'smoothing':False,'row_correction':False,'full_range_companion_figures':[ref(p) for p in full_links],'figure':ref(png),'source':ref(__file__),'scientific_judgement':ref(D/'post_manual_review.json'),'limitations':['216 parameters differ, so persistent function is assessed by matched original215 and217.','C3 local change remains documented in the formal review.','Colors outside display limits explicitly show clipping, not capped or replaced raw data.']}
(O/'display_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
lines=['三列依次是215原参数基线、216诱导参数曝光、217恢复原参数。上排正扫F，下排反扫B。六幅共用冻结范围，青色和品红色分别标记低于下限与高于上限的值。原始像素保持，未配准或逐行校正。\n',f'![三阶段正反扫]({png})\n','216条纹与恢复后的217应结合不同采集参数理解。217支持本轮纳米成像任务可用，C3近边突起的局部变化继续保留，严格诱导修复闭环增量为0。\n']
for p,label in zip(full_links,['215与216完整原始高度范围','215与217完整原始高度范围']):lines.append(f'[{label}]({p})\n')
for label in ('215','216','217'):lines.append(f'[{label}完整原生SXM]({sources[label]["raw_SXM"]["path"]})\n')
lines.append(f'[正式判读与限制]({D/"post_manual_review.json"})\n')
(O/'source_links_zh.md').write_text('\n'.join(lines))
print(json.dumps({'image':str(png),'sha256':sha(png),'record_sha256':sha(O/'display_record.json'),'index':str(O/'source_links_zh.md')},ensure_ascii=False))
