import obs
from agents import supervisor
from agents.supervisor import RouteResponse, decide_next, sufficient

OK_TECH = {"근거충분": True, "근거ID": ["TEC-1", "TEC-2"]}
OK_MKT = {"근거충분": True, "근거ID": ["MKT-1", "MKT-2"]}
OK_CMP = {"경쟁제품": [{"제품": "x"}], "근거ID": ["CMP-1", "CMP-2"]}
BAD_TECH = {"근거충분": False, "근거ID": ["TEC-1"], "미확인정보": ["성능지표"]}
ONCE = {"technology": 1, "market": 1, "competitor": 1}


def test_first_round_runs_technology_and_market_in_parallel():
    nxt, rework, _ = decide_next({})
    assert nxt == ["technology", "market"] and set(rework) == {"technology", "market"}


def test_competitor_runs_after_views_even_if_insufficient():
    state = {"technology_analysis": BAD_TECH, "market_analysis": OK_MKT, "agent_attempts": {"technology": 1, "market": 1}}
    assert decide_next(state)[0] == ["competitor"]


def test_rework_candidates_with_reason():
    state = {"technology_analysis": BAD_TECH, "market_analysis": OK_MKT, "competitor_analysis": OK_CMP,
             "agent_attempts": ONCE}
    nxt, rework, _ = decide_next(state)
    assert nxt == ["technology"] and "성능지표" in rework["technology"]


def test_rework_cap_moves_to_investment():
    state = {"technology_analysis": BAD_TECH, "market_analysis": OK_MKT, "competitor_analysis": OK_CMP,
             "agent_attempts": {**ONCE, "technology": 2}}
    assert decide_next(state)[0] == ["investment"]


def test_all_sufficient_goes_to_investment():
    state = {"technology_analysis": OK_TECH, "market_analysis": OK_MKT, "competitor_analysis": OK_CMP,
             "agent_attempts": ONCE}
    assert decide_next(state)[0] == ["investment"]


def test_step_cap_forces_investment():
    assert decide_next({"step_count": 6})[0] == ["investment"]
    assert decide_next({"step_count": 2, "max_steps": 2})[0] == ["investment"]


def test_failed_worker_retried_once_then_fallback():
    once = {"node_status": {"technology": "FAILED", "market": "SUCCESS"}, "market_analysis": OK_MKT,
            "agent_attempts": {"technology": 1, "market": 1}}
    assert decide_next(once)[0] == ["technology"]
    assert decide_next({**once, "agent_attempts": {"technology": 2, "market": 1}})[0] == ["handle_error"]
    mkt_failed = {"technology_analysis": OK_TECH, "node_status": {"technology": "SUCCESS", "market": "FAILED"},
                  "agent_attempts": {"technology": 1, "market": 2}}
    assert decide_next(mkt_failed)[0] == ["competitor"]  # 시장 실패는 미확인으로 계속


def test_sufficient_requires_min_evidence():
    assert sufficient("technology", {"technology_analysis": {"근거충분": True, "근거ID": ["TEC-1"]}})[0] is False
    assert sufficient("technology", {"technology_analysis": OK_TECH})[0] is True


REWORK_STATE = {"trace_id": "t", "technology_analysis": BAD_TECH, "market_analysis": OK_MKT,
                "competitor_analysis": {"경쟁제품": [], "근거ID": []}, "agent_attempts": ONCE}


def test_llm_decides_between_rework_and_investment(monkeypatch):
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: RouteResponse(next=["investment"], reason="공개자료 부족"))
    out = supervisor.run(REWORK_STATE)
    assert out["next"] == ["investment"] and "LLM" in out["route_reason"]
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: RouteResponse(next=["technology"], reason="재검색"))
    out = supervisor.run(REWORK_STATE)
    assert out["next"] == ["technology"] and set(out["rework_reason"]) == {"technology"}


def test_invalid_llm_choice_falls_back_to_policy(monkeypatch):
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: RouteResponse(next=["market"], reason="x"))
    assert supervisor.run(REWORK_STATE)["next"] == ["technology", "competitor"]


def test_llm_not_asked_for_mandatory_steps(monkeypatch):
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: (_ for _ in ()).throw(AssertionError("호출 금지")))
    assert supervisor.run({"trace_id": "t"})["next"] == ["technology", "market"]


def test_run_increments_step_logs_and_routes():
    out = supervisor.run({"trace_id": "t", "step_count": 2,
                          "current_company": {"company_id": "C1"},
                          "errors": [{"company_id": "C1", "stage": "market", "error": "x"}]})
    assert out["step_count"] == 3 and out["next"] == ["technology", "market"]
    assert out["last_error"]["stage"] == "market"
    assert supervisor.route({"next": ["market"]}) == ["market"]
    assert (obs.LOG_DIR / "t.jsonl").exists()
