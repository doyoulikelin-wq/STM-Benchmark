from stm_bench.env import STMEnv
from stm_bench.policies import RulePolicy
from stm_bench.runner import scenario_pass


def test_scientific_hypothesis_is_not_numerical_acceptance():
    env=STMEnv()
    obs,_=env.reset(seed=0)
    policy=RulePolicy()
    while not (obs.get("repeatability") or {}).get("confirmed"):
        obs,_,done,truncated,_=env.step(policy.act(obs))
        assert not done and not truncated
    obs,_,_,_,_=env.step({"type":"judge","label":"good","diagnosis":"double_tip"})
    assert "accept" not in obs["action_mask"]
    assert env.summary()["judgments"][-1]["diagnosis_status"]=="unverified_agent_hypothesis"
    env.close()


def test_synthetic_oracle_scores_explicit_diagnosis_separately():
    summary={"error":None,"cleanup_ok":True,"success":False,"truncated":False,
             "scenario":"double_tip","termination_reason":"agent_retracted",
             "judgments":[{"label":"good","agrees_with_metrics":True,"diagnosis":"double_tip"}]}
    assert scenario_pass(summary,{"scan_attempt":True,"image_labels":["good"]})
    summary["scenario"]="nominal"
    assert not scenario_pass(summary,{"scan_attempt":True,"image_labels":["good"]})
