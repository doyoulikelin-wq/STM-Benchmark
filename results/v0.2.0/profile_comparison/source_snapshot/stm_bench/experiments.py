"""Predeclared profile comparison and bounded multi-recipe Demo trials."""
from __future__ import annotations
import json
from pathlib import Path
from .artifacts import write_json, render_report, seal
from .runner import evaluate, run_episode, freeze_protocol
from .profiles import thresholds_snapshot

DEMO_RECIPES = (
    {"name":"reference_64", "pixels":64, "params":{"p_gain_m":35e-12,"time_constant_s":.001,"line_time_s":.256}},
    {"name":"lower_gain_64", "pixels":64, "params":{"p_gain_m":30e-12,"time_constant_s":.001,"line_time_s":.256}},
    {"name":"higher_gain_64", "pixels":64, "params":{"p_gain_m":40e-12,"time_constant_s":.001,"line_time_s":.256}},
    {"name":"faster_longer_integral_64", "pixels":64, "params":{"p_gain_m":35e-12,"time_constant_s":.002,"line_time_s":.2048}},
    {"name":"reference_128", "pixels":128, "params":{"p_gain_m":35e-12,"time_constant_s":.001,"line_time_s":.256}},
)


def compare_profiles(output, *, seeds=20, seed_offset=100, policies=("rule","random")):
    root=Path(output); root.mkdir(parents=True,exist_ok=False)
    plan={"profiles":["strict-v1","relaxed-v1"],"seeds_per_scenario":seeds,"seed_offset":seed_offset,
          "split":"test","policies":list(policies),"paired_initial_seeds":True,
          "thresholds":{p:thresholds_snapshot(p) for p in ("strict-v1","relaxed-v1")}}
    write_json(root/"plan.json",plan)
    freeze_protocol(root)
    reports={}
    for profile in plan["profiles"]:
        reports[profile]=evaluate(root/profile,split="test",seeds_per_scenario=seeds,
                                  seed_offset=seed_offset,policies=policies,profile=profile)
    pairs=[]
    strict={(r["case_id"],r["policy"]):r for r in reports["strict-v1"]["episodes"]}
    for r in reports["relaxed-v1"]["episodes"]:
        before=strict[(r["case_id"],r["policy"])]
        pairs.append({"case_id":r["case_id"],"policy":r["policy"],"scenario":r["scenario"],"seed":r["seed"],
                      "strict_pass":before["task_pass"],"relaxed_pass":r["task_pass"],
                      "strict_success":before["success"],"relaxed_success":r["success"]})
    rows=[{**r,"case_id":profile+"/"+r["case_id"]} for profile,report in reports.items() for r in report["episodes"]]
    result={"kind":"paired_profile_comparison","backend":"synthetic","plan":plan,
            "aggregate":{"episodes":len(rows),"paired_cases":len(pairs),"profiles":2},
            "by_profile":{k:v["policies"] for k,v in reports.items()},"paired_outcomes":pairs,"episodes":rows,
            "interpretation":"Relaxed numerical gates change qualification; this is not evidence of a more capable agent."}
    write_json(root/"summary.json",result); render_report(root,result); seal(root)
    return result


def demo_series(output, *, profile="relaxed-v1", repeats=5, port=6501):
    from .demo import DemoBackend
    if not 1 <= repeats <= len(DEMO_RECIPES): raise ValueError("Demo series supports 1..5 predeclared trials")
    root=Path(output); root.mkdir(parents=True,exist_ok=False)
    recipes=DEMO_RECIPES[:repeats]
    write_json(root/"plan.json",{"profile":profile,"recipes":recipes,"stop_on_cleanup_failure":True,
                                "thresholds":thresholds_snapshot(profile),"same_session":True})
    freeze_protocol(root,profile)
    results=[]; previews=[]

    class RecipeBackend(DemoBackend):
        def __init__(self,directory,recipe):
            self.trial_recipe=recipe
            super().__init__(directory,port=port,pixels=recipe["pixels"])
        def reset(self,seed=0,scenario="nominal"):
            super().reset(seed=seed,scenario=scenario)
            return self.configure(self.trial_recipe["params"])

    for i,recipe in enumerate(recipes,1):
        name=f"trial_{i:02d}_{recipe['name']}"
        print(json.dumps({"event":"trial_started","trial":name,"recipe":recipe},ensure_ascii=False),flush=True)
        result,imgs=run_episode(root/name,backend=lambda d:RecipeBackend(d,recipe),profile=profile,
                                scenario="nominal",max_steps=32,case_id=name)
        result={**result,"trial_recipe":recipe,"evidence_directory":name}
        results.append(result)
        previews.extend(imgs[-1:])
        write_json(root/"progress.json",{"completed":len(results),"planned":len(recipes),"episodes":results})
        print(json.dumps({"event":"trial_finished","trial":name,"success":result["success"],
                          "cleanup_ok":result["cleanup_ok"],"reason":result.get("termination_reason")},ensure_ascii=False),flush=True)
        if not result["cleanup_ok"] or result.get("error"):
            break
    summary={"backend":"nanonis_demo","profile":profile,"episodes":results,
             "aggregate":{"planned":len(recipes),"completed":len(results),"successes":sum(r["success"] for r in results),
                          "cleanup_failures":sum(not r["cleanup_ok"] for r in results),
                          "fresh_frames":sum(r["frames"] for r in results)},
             "scope":"Repeated same-session simulator workflow with predeclared recipes, not hardware/generalization validation."}
    write_json(root/"summary.json",summary); render_report(root,summary,previews); seal(root)
    return summary
