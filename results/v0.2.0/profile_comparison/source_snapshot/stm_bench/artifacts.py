"""Append-only episode evidence, content hashes and a local HTML result viewer."""
from __future__ import annotations
import hashlib
import html
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import numpy as np

ARRAY_KEYS = ("z_forward", "z_backward", "current_forward", "current_backward")


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds")


def plain(obj):
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, np.generic): return plain(obj.item())
    if isinstance(obj, float) and not np.isfinite(obj): return None
    if isinstance(obj, dict): return {str(k): plain(v) for k,v in obj.items()}
    if isinstance(obj, (list, tuple)): return [plain(v) for v in obj]
    if isinstance(obj, Path): return str(obj)
    return obj


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(plain(obj), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal(root):
    root = Path(root)
    files = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file() and p != root/"manifest.json"}
    write_json(root/"manifest.json", {"algorithm": "sha256", "files": files})


def audit(root):
    root = Path(root)
    manifest = json.loads((root/"manifest.json").read_text(encoding="utf-8"))["files"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p != root/"manifest.json"}
    missing = sorted(set(manifest)-actual)
    extra = sorted(actual-set(manifest))
    changed = [n for n in set(manifest)&actual if sha(root/n) != manifest[n]]
    return {"valid": not (missing or extra or changed), "files": len(manifest), "missing": missing, "extra": extra, "changed": sorted(changed)}


class Recorder:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.frames = {}
        self.previews = []

    def observation(self, obs):
        result = dict(obs)
        frame = result.get("latest_frame")
        if frame:
            identity = frame["id"]
            if identity not in self.frames:
                relative = f"frames/frame_{len(self.frames):03d}.npz"
                path = self.root/relative
                path.parent.mkdir(exist_ok=True)
                np.savez_compressed(path, **{k: frame[k] for k in ARRAY_KEYS})
                metadata = {k:v for k,v in frame.items() if k not in ARRAY_KEYS}
                write_json(path.with_suffix(".json"), metadata)
                self.frames[identity] = relative
                z = np.asarray(frame["z_forward"],float)
                step = max(1, z.shape[0]//96)
                self.previews.append({"id": identity, "kind": frame.get("kind"), "data": plain(z[::step,::step])})
            result["latest_frame"] = {k:v for k,v in frame.items() if k not in ARRAY_KEYS}
            result["latest_frame"]["arrays_path"] = self.frames[identity]
        return result

    def event(self, kind, **data):
        if "observation" in data: data["observation"] = self.observation(data["observation"])
        if isinstance(data.get("info"),dict) and "acquired_frame" in data["info"]:
            data["info"] = dict(data["info"])
            data["info"]["acquired_frame"] = self.observation({"latest_frame": data["info"]["acquired_frame"]})["latest_frame"]
        with (self.root/"events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(plain({"at": now(), "event": kind, **data}), ensure_ascii=False, allow_nan=False)+"\n")


def render_report(root, report, previews=()):
    root = Path(root)
    data = json.dumps(plain(report), ensure_ascii=False).replace("<", "\\u003c")
    imgs = json.dumps(plain(previews), ensure_ascii=False).replace("<", "\\u003c")
    title = "STM Agent Benchmark · 实验结果"
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>STM Agent Benchmark</title><style>body{font:15px/1.65 system-ui;margin:40px auto;max-width:1180px;background:#0f1724;color:#e5edf6;padding:0 24px}h1{font-size:30px}small,.muted{color:#96abc3}.cards{display:flex;gap:18px;flex-wrap:wrap}.card,figure{background:#182638;border:1px solid #314760;border-radius:12px;padding:20px;margin:10px 0}.big{font-size:28px;color:#76e5c2}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #314760;text-align:left}canvas{width:260px;height:260px;image-rendering:pixelated}pre{white-space:pre-wrap;word-break:break-word}details{margin:20px 0}a{color:#80c8ff}.grid{display:flex;gap:16px;flex-wrap:wrap}</style>
<h1>STM Agent Benchmark</h1><p>进针 → 连续稳定性确认 → 概览扫描 → ROI 定位 → 独立复扫 → 判图</p>
<p class="muted">数值工作流评测。Synthetic 是软件任务生成器；Nanonis Demo 是实际模拟器采集。两类结果分开记录，均不代表真机科学成像认证。</p><div class="cards" id="cards"></div><div id="result"></div><h2>原始 Z 图预览</h2><p class="muted">每张单独按有限像素 1–99% 映射颜色，仅改变显示；NPZ 保存未处理的完整 Current/Z 正反扫数组。</p><div class="grid" id="images"></div><details><summary>完整结果 JSON</summary><pre id="json"></pre></details>
<script>const report=REPORT, images=IMAGES;document.querySelector('#json').textContent=JSON.stringify(report,null,2);
const cards=document.querySelector('#cards');for(const [k,v] of Object.entries(report.aggregate||{backend:report.backend,success:report.success,score:report.score})){if(typeof v==='object')continue;const d=document.createElement('div');d.className='card';const label=document.createElement('div');label.textContent=k;const val=document.createElement('div');val.className='big';val.textContent=String(v);d.append(label,val);cards.append(d)}
if(report.episodes){const t=document.createElement('table');for(const [index,row] of [['case','policy','success','task_pass','score','termination_reason'],...report.episodes.map(e=>[e.case_id,e.policy,e.success,e.task_pass,e.score,e.termination_reason])].entries()){const tr=document.createElement('tr');for(const v of row){const td=document.createElement(index?'td':'th');td.textContent=String(v);tr.append(td)}t.append(tr)}document.querySelector('#result').append(t)}
for(const im of images){const f=document.createElement('figure'), c=document.createElement('canvas'), cap=document.createElement('figcaption');const a=im.data,h=a.length,w=a[0].length;c.width=w;c.height=h;const finite=a.flat().filter(x=>x!==null&&Number.isFinite(x)).sort((a,b)=>a-b),lo=finite[Math.floor(finite.length*.01)]||0,hi=finite[Math.floor(finite.length*.99)]||1;const ctx=c.getContext('2d'), pix=ctx.createImageData(w,h);for(let y=0;y<h;y++)for(let x=0;x<w;x++){const v=a[y][x],q=v===null?0:Math.min(1,Math.max(0,(v-lo)/Math.max(hi-lo,1e-18))),i=(y*w+x)*4;pix.data[i]=Math.round(255*q);pix.data[i+1]=Math.round(210*Math.sqrt(q));pix.data[i+2]=Math.round(120*(1-q));pix.data[i+3]=255}ctx.putImageData(pix,0,0);cap.textContent=im.kind+' · '+im.id;f.append(c,cap);document.querySelector('#images').append(f)}
</script></html>'''.replace('REPORT',data).replace('IMAGES',imgs)
    (root/"report.html").write_text(page,encoding="utf-8")
