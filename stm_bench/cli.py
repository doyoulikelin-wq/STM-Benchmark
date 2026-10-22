from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from .artifacts import plain, audit


def default_output(prefix):
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S_%f")
    return str(Path.cwd()/"runs"/f"{prefix}_{stamp}")


def stdio(profile="strict-v1"):
    """One persistent synthetic episode, JSONL request/response external-agent API."""
    from .env import STMEnv
    env = STMEnv(profile=profile)
    initialized = False
    try:
        for line in sys.stdin:
            req = {}
            try:
                req = json.loads(line)
                tool = req["tool"]
                args = req.get("arguments", {})
                if tool == "reset":
                    obs, info = env.reset(seed=args.get("seed",0),options={"scenario":args.get("scenario","nominal")})
                    initialized = True
                    result = {"observation":obs,"info":info}
                elif tool == "step" and initialized:
                    obs,r,t,tr,info = env.step(args["action"])
                    result = {"observation":obs,"reward":r,"terminated":t,"truncated":tr,"info":info}
                elif tool == "summary" and initialized: result = env.summary()
                elif tool == "close": result = env.close(); initialized=False
                else: raise ValueError("Expected reset before step/summary; tools: reset,step,summary,close")
                response = {"request_id":req.get("request_id"),"result":plain(result)}
            except Exception as exc:
                response = {"request_id":req.get("request_id") if isinstance(req,dict) else None,
                            "error":f"{type(exc).__name__}: {exc}"}
            print(json.dumps(response,ensure_ascii=False,allow_nan=False),flush=True)
    finally:
        env.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="STM agent numerical workflow benchmark")
    sub = parser.add_subparsers(dest="command",required=True)
    run = sub.add_parser("run",help="one reproducible synthetic episode")
    run.add_argument("--scenario",default="nominal")
    run.add_argument("--seed",type=int,default=0)
    run.add_argument("--policy",choices=["rule","random"],default="rule")
    run.add_argument("--out")
    ev = sub.add_parser("evaluate",help="frozen synthetic scenario suite")
    ev.add_argument("--split",choices=["train","dev","test"],default="test")
    ev.add_argument("--seeds",type=int,default=3)
    ev.add_argument("--policies",nargs="+",choices=["rule","random"],default=["rule","random"])
    ev.add_argument("--out")
    au = sub.add_parser("audit",help="verify sealed artifacts without modifying them")
    au.add_argument("path")
    std = sub.add_parser("stdio",help="synthetic external agent JSONL API")
    demo = sub.add_parser("demo",help="bounded write-capable experiment on verified local Nanonis SIM")
    demo.add_argument("--out")
    demo.add_argument("--port",type=int,choices=[6501,6502,6503],default=6501)
    demo.add_argument("--pixels",type=int,choices=[64,128],default=64)
    ev.add_argument("--seed-offset",type=int,default=0)
    for command in (run,ev,demo,std):
        command.add_argument("--profile",choices=["strict-v1","relaxed-v1"],default="strict-v1")
    compare=sub.add_parser("compare",help="paired strict/relaxed profile benchmark")
    compare.add_argument("--seeds",type=int,default=20)
    compare.add_argument("--seed-offset",type=int,default=100)
    compare.add_argument("--out")
    series=sub.add_parser("demo-series",help="five bounded, predeclared Nanonis Demo recipes")
    series.add_argument("--repeats",type=int,choices=range(1,6),default=5)
    series.add_argument("--profile",choices=["strict-v1","relaxed-v1"],default="relaxed-v1")
    series.add_argument("--port",type=int,choices=[6501,6502,6503],default=6501)
    series.add_argument("--out")
    args=parser.parse_args(argv)
    if args.command=="stdio": return stdio(args.profile)
    if args.command=="audit":
        result=audit(args.path); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result["valid"] else 1
    from .runner import run_episode,evaluate
    out=Path(args.out or default_output(args.command))
    if args.command=="compare":
        if not 1<=args.seeds<=50 or not 0<=args.seed_offset<=950: parser.error("Invalid seed count/offset")
        from .experiments import compare_profiles
        result=compare_profiles(out,seeds=args.seeds,seed_offset=args.seed_offset)
        print(json.dumps({"output":str(out),"aggregate":result["aggregate"],"by_profile":result["by_profile"]},ensure_ascii=False,indent=2))
        return 0 if all(p["errors"]==0 and p["cleanup_failures"]==0 for v in result["by_profile"].values() for p in v.values()) else 1
    if args.command=="demo-series":
        from .experiments import demo_series
        result=demo_series(out,profile=args.profile,repeats=args.repeats,port=args.port)
        print(json.dumps({"output":str(out),"aggregate":result["aggregate"]},ensure_ascii=False,indent=2))
        return 0 if result["aggregate"]["successes"]==args.repeats else 2
    if args.command=="evaluate":
        if not 1 <= args.seeds <= 50: parser.error("--seeds must be 1..50")
        result=evaluate(out,split=args.split,seeds_per_scenario=args.seeds,policies=tuple(args.policies),profile=args.profile,seed_offset=args.seed_offset)
        print(json.dumps({"output":str(out),"policies":result["policies"]},ensure_ascii=False,indent=2))
        return 0 if all(v["errors"]==0 and v["cleanup_failures"]==0 for v in result["policies"].values()) else 1
    if args.command=="demo":
        from .demo import DemoBackend
        # Adapter artifacts go inside the run but initialization must remain lazy.
        backend=lambda directory: DemoBackend(out_dir=directory,port=args.port,pixels=args.pixels)
        result,_=run_episode(out,backend=backend,scenario="nominal",max_steps=32,profile=args.profile)
    else:
        result,_=run_episode(out,seed=args.seed,scenario=args.scenario,policy=args.policy,profile=args.profile)
    print(json.dumps({"output":str(out),"result":plain(result)},ensure_ascii=False,indent=2))
    return 0 if result["task_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
