import json

import obs
from state import merge_dict


def test_merge_dict_merges_and_resets():
    assert merge_dict({"technology": "SUCCESS"}, {"market": "FAILED"}) == {"technology": "SUCCESS", "market": "FAILED"}
    assert merge_dict({"technology": "SUCCESS"}, {"technology": "FAILED"}) == {"technology": "FAILED"}
    assert merge_dict({"technology": "SUCCESS"}, None) == {}


def test_log_decision_and_summarize(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path)
    state = {"trace_id": "t1", "current_company": {"company_id": "C03"}}
    obs.log_decision(state, "supervisor", ["technology", "market"], "미수행")
    for node in ("technology", "market", "technology"):
        obs.log_decision(state, node, "SUCCESS", "attempt")
    obs.log_decision(state, "evaluator", "fail", "x")
    rec = json.loads((tmp_path / "t1.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["trace_id"] == "t1" and rec["company_id"] == "C03"
    assert rec["node"] == "supervisor" and rec["decision"] == ["technology", "market"]
    assert rec["reason"] == "미수행" and "ts" in rec
    assert obs.summarize("t1") == {"supervisor_routes": 1, "agent_runs": {"technology": 2, "market": 1},
                                   "reworks": 1, "evaluations": ["fail"]}


def test_loader_applies_company_filter(monkeypatch):
    from agents import loader
    monkeypatch.setattr(loader, "load_companies", lambda *a, **k: [{"company_id": c} for c in ("C01", "C03", "C11")])
    out = loader.run({"company_filter": ["C03", "C11"]})
    assert [c["company_id"] for c in out["candidate_companies"]] == ["C03", "C11"]
    assert len(loader.run({})["candidate_companies"]) == 3
