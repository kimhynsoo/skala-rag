"""LangGraph 흐름 — 외부 루프(45개사) + 기업별 Supervisor 서브루프.

eligibility(적격) → supervisor ⇄ {technology, market, competitor} → investment.
하위 에이전트는 guarded_worker로 감싸 실행 횟수·상태를 기록하고 항상 supervisor로 돌아온다.
흐름 제어 노드(select, exclude, hold, handle_error, save, next_index, rank)는 이 파일에 둔다.
루프는 후보 소진 시에만 종료하고, rank가 투자 적격 기업 중 1위를 selected_company_id로 고른다.
"""

import time

from langgraph.graph import END, START, StateGraph

from agents import competitor, eligibility, evaluator, investment, loader, market, report, supervisor, technology
from agents.investment import rank_key
from config import MAX_SUPERVISOR_STEPS
from obs import log_decision
from state import State

# 후보 전환 시 리셋하는 ③ 작업 산출물
_RESET = {
    "eligibility": None,
    "checklist": None,
    "technology_analysis": None,
    "market_analysis": None,
    "competitor_analysis": None,
    "current_evidence": None,  # merge_evidence 리듀서가 None을 리셋으로 처리
    "scorecard": None,
    "decision": None,
    "decision_details": None,
    "route_reason": "",
    "next": [],
    "step_count": 0,
    "max_steps": MAX_SUPERVISOR_STEPS,
    "rework_reason": {},
    "node_status": None,  # merge_dict 리듀서가 None을 리셋으로 처리
    "agent_attempts": None,
    "last_error": None,
}


def _company_id(state: State) -> str | None:
    return (state.get("current_company") or {}).get("company_id")


def guarded(stage: str, fn):
    def node(state: State) -> dict:
        try:
            return fn(state)
        except Exception as e:  # 한 기업의 실패가 전체 루프를 멈추지 않도록
            return {"errors": [{"company_id": _company_id(state), "stage": stage, "error": repr(e)}]}

    return node


def guarded_worker(stage: str, fn):
    """Supervisor 하위 에이전트용. 실행 횟수·상태를 여기서 일괄 기록 → worker는 자기 산출물만 반환한다."""

    def node(state: State) -> dict:
        n = (state.get("agent_attempts") or {}).get(stage, 0) + 1
        try:
            out, status = fn(state), "SUCCESS"
        except Exception as e:  # 실패해도 supervisor가 재시도/진행/보류를 정한다
            out = {"errors": [{"company_id": _company_id(state), "stage": stage, "type": type(e).__name__,
                               "error": repr(e), "ts": time.time()}]}
            status = "FAILED"
        log_decision(state, stage, status, f"attempt {n}" + (f": {out['errors'][0]['error'][:200]}" if status == "FAILED" else ""))
        return {**out, "agent_attempts": {stage: n}, "node_status": {stage: status}}

    return node


def _failed(state: State) -> bool:
    errors = state.get("errors") or []
    return bool(errors) and errors[-1]["company_id"] == _company_id(state)


# ---------- 흐름 제어 노드 ----------

def select(state: State) -> dict:
    company = state["candidate_companies"][state.get("current_index", 0)]
    return {"current_company": company, **_RESET}


def exclude(state: State) -> dict:
    reason = state["eligibility"].get("사유", "")
    return {"decision": "제외", "decision_details": {"판단사유": reason}, "route_reason": f"자격 요건 미충족: {reason}"}


def hold(state: State) -> dict:
    reason = state["eligibility"].get("사유", "")
    return {"decision": "보류", "decision_details": {"추가확인사항": reason}, "route_reason": f"자격 요건 확인 필요: {reason}"}


def handle_error(state: State) -> dict:
    stage = state["errors"][-1]["stage"]
    return {"decision": "보류", "decision_details": {"판단사유": f"{stage} 단계 오류"}, "route_reason": f"오류: {stage}"}


def save(state: State) -> dict:
    """기업별 결과를 누적. 투자 적격이어도 루프는 계속된다 (선정은 rank에서)."""
    keys = ("current_company", "eligibility", "checklist", "technology_analysis", "market_analysis",
            "competitor_analysis", "scorecard", "decision", "decision_details", "route_reason", "current_evidence")
    return {"evaluation_results": [{"company_id": _company_id(state), **{k: state.get(k) for k in keys}}]}


def next_index(state: State) -> dict:
    return {"current_index": state.get("current_index", 0) + 1}


def rank(state: State) -> dict:
    """최종 선정: 전체 후보 평가 후 투자 적격 기업 순위 산정, 1위를 보고서 대상으로."""
    passed = [r for r in state.get("evaluation_results", []) if r["decision"] == "투자 적격"]
    ids = [r["company_id"] for r in sorted(passed, key=rank_key)]
    return {"ranking": ids, "selected_company_id": ids[0] if ids else None}


# ---------- 라우터 ----------

def route_exists(state: State) -> str:
    return "select" if state.get("current_index", 0) < len(state["candidate_companies"]) else "rank"


def route_eligibility(state: State) -> str:
    if _failed(state):
        return "handle_error"
    return {"적격": "supervisor", "부적격": "exclude"}.get(state["eligibility"]["판정"], "hold")


def route_ok(next_node: str):
    return lambda state: "handle_error" if _failed(state) else next_node


def build_graph(checkpointer=None):
    g = StateGraph(State)
    g.add_node("load", loader.run)
    g.add_node("select", select)
    g.add_node("eligibility", guarded("eligibility", eligibility.run))
    g.add_node("supervisor", supervisor.run)
    g.add_node("technology", guarded_worker("technology", technology.run))
    g.add_node("market", guarded_worker("market", market.run))
    g.add_node("competitor", guarded_worker("competitor", competitor.run))
    g.add_node("investment", guarded("investment", investment.run))
    g.add_node("exclude", exclude)
    g.add_node("hold", hold)
    g.add_node("handle_error", handle_error)
    g.add_node("save", save)
    g.add_node("next_index", next_index)
    g.add_node("rank", rank)
    g.add_node("report", report.run)
    g.add_node("evaluator", evaluator.run)
    g.add_node("end_with_warning", evaluator.end_with_warning)

    g.add_edge(START, "load")
    g.add_conditional_edges("load", route_exists, ["select", "rank"])
    g.add_edge("select", "eligibility")
    g.add_conditional_edges("eligibility", route_eligibility, ["supervisor", "exclude", "hold", "handle_error"])
    g.add_conditional_edges("supervisor", supervisor.route,
                            ["technology", "market", "competitor", "investment", "handle_error"])
    for w in ("technology", "market", "competitor"):
        g.add_edge(w, "supervisor")  # 하위 에이전트는 supervisor와만 통신
    g.add_conditional_edges("investment", route_ok("save"), ["save", "handle_error"])
    for n in ("exclude", "hold", "handle_error"):
        g.add_edge(n, "save")
    g.add_edge("save", "next_index")
    g.add_conditional_edges("next_index", route_exists, ["select", "rank"])
    g.add_edge("rank", "report")
    g.add_edge("report", "evaluator")
    g.add_conditional_edges("evaluator", evaluator.route, {"__end__": END, "report": "report",
                                                           "end_with_warning": "end_with_warning"})
    g.add_edge("end_with_warning", END)
    return g.compile(checkpointer=checkpointer)
