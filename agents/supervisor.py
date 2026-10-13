"""Supervisor — 기업 1곳의 분석 구간을 통제한다 (Hybrid: 규칙 가드 + LLM 판단).

- 하위 에이전트(technology·market·competitor)는 서로 통신하지 않고 항상 여기로 돌아온다.
- 규칙(코드): 필수 단계·실패 재시도·상한(종료 보장)을 강제한다. 재현성이 필요한 부분.
- LLM: 모든 관점이 한 번씩 실행된 뒤 "근거 부족 관점을 재작업할지, 투자 판단으로 넘어갈지"를 판단한다.
  LLM 응답이 선택지를 벗어나거나 호출이 실패하면 규칙 정책으로 대체한다.
- 결정 사유는 State에 마지막 1줄(route_reason)만 두고 전체 이력은 obs.log_decision으로 외부에 남긴다.
"""

import json
from typing import Literal

from pydantic import BaseModel

from config import MAX_REWORK, MAX_SUPERVISOR_STEPS, MIN_EVIDENCE
from obs import log_decision
from state import State

WORKERS = ("technology", "market", "competitor")
VIEWS = ("technology", "market")  # 서로 독립 → 첫 라운드 병렬


class RouteResponse(BaseModel):
    next: list[Literal["technology", "market", "competitor", "investment"]]
    reason: str


def build_system_prompt() -> str:
    """판단 규칙을 코드 상수에서 생성 → 상수를 바꾸면 프롬프트도 함께 바뀐다."""
    return (
        "너는 AI 반도체 스타트업 투자 심사팀의 Supervisor다. 직접 분석하지 않고 하위 에이전트에게 재작업을 지시하거나 "
        "투자 판단 단계로 넘긴다.\n\n"
        "[하위 에이전트]\n"
        "- technology: 기술력 (IRDS·UCIe·CXL 기준값 대조)\n"
        "- market: 시장성 (SIA·WSTS·KIET·OECD 대조)\n"
        "- competitor: 경쟁 제품 비교 (기술·시장 결과를 기준으로 사용)\n\n"
        "[판단 규칙]\n"
        f"- 관점별 근거ID가 {MIN_EVIDENCE}개 이상이고 근거충분=True면 충분하다.\n"
        f"- 재작업은 관점별 최대 {MAX_REWORK}회다. 입력의 재작업후보는 이 상한 안에 있다.\n"
        "- 재작업으로 보완될 가능성이 있는 관점만 고른다. 원인이 기업 공개자료 부족이라 재검색해도 나아지지 않으면 "
        "재작업하지 말고 investment를 고른다.\n"
        "- 여러 관점을 동시에 재작업할 수 있다 (병렬 실행).\n"
        "- investment를 고르면 다른 항목과 함께 고르지 않는다.\n\n"
        "next에는 선택지 중에서만 고르고, reason에 한두 문장으로 근거를 쓴다."
    )


def sufficient(stage: str, state: dict) -> tuple[bool, str]:
    out = state.get(f"{stage}_analysis")
    if out is None:
        return False, "미수행"
    ids = set(out.get("근거ID") or [])
    if stage == "competitor":
        n = len(out.get("경쟁제품") or [])
        ok = n > 0 and len(ids) >= MIN_EVIDENCE
        return ok, "" if ok else f"경쟁제품 {n}개, 근거ID {len(ids)}개"
    if not out.get("근거충분"):
        gaps = ", ".join((out.get("미확인정보") or [])[:3]) or "사유 미기재"
        return False, f"근거충분=False ({gaps})"
    if len(ids) < MIN_EVIDENCE:
        return False, f"근거ID {len(ids)}개 < {MIN_EVIDENCE}"
    return True, ""


def _must_run(stage: str, state: dict) -> str | None:
    """반드시 실행할 사유(미수행·실패 재시도). 상한에 도달했으면 None."""
    if (state.get("agent_attempts") or {}).get(stage, 0) > MAX_REWORK:
        return None
    if (state.get("node_status") or {}).get(stage) == "FAILED":
        return "이전 실행 실패 → 재시도"
    return "미수행" if state.get(f"{stage}_analysis") is None else None


def rework_candidates(state: dict) -> dict[str, str]:
    """근거가 부족하고 재작업 상한이 남은 관점 → 사유."""
    out = {}
    for s in WORKERS:
        if (state.get("agent_attempts") or {}).get(s, 0) > MAX_REWORK:
            continue
        ok, why = sufficient(s, state)
        if not ok:
            out[s] = why
    return out


def decide_next(state: dict) -> tuple[list[str], dict[str, str], str]:
    """규칙 정책. 반환: (다음 노드들, 재작업 사유, 분기 사유). LLM 판단이 없거나 무효일 때도 이 결과를 쓴다."""
    if state.get("step_count", 0) >= state.get("max_steps", MAX_SUPERVISOR_STEPS):
        return ["investment"], {}, "step 상한 도달 → 보유 근거로 투자 판단"
    status = state.get("node_status") or {}
    attempts = state.get("agent_attempts") or {}
    if status.get("technology") == "FAILED" and attempts.get("technology", 0) > MAX_REWORK:
        return ["handle_error"], {}, "기술 분석 재시도 후에도 실패 → 기술력 없이 판단 불가, 보류"
    todo = {s: why for s in VIEWS if (why := _must_run(s, state))}
    if todo:
        return list(todo), todo, "필수 실행: " + "; ".join(f"{s}={w}" for s, w in todo.items())
    if why := _must_run("competitor", state):
        return ["competitor"], {"competitor": why}, f"기술·시장 확보 → 경쟁 비교 ({why})"
    if cands := rework_candidates(state):
        return list(cands), cands, "근거 부족 재작업: " + "; ".join(f"{s}={w}" for s, w in cands.items())
    return ["investment"], {}, "모든 관점 근거 충분 또는 재작업 상한 도달 → 투자 판단"


def _ask_llm(state: dict, candidates: dict[str, str]) -> RouteResponse | None:
    """재작업 vs 진행 판단. 실패하면 None (규칙 정책으로 대체). 테스트는 이 함수를 monkeypatch한다."""
    from llm import get_llm

    company = state.get("current_company") or {}
    user = json.dumps({
        "기업": {k: company.get(k) for k in ("company_id", "기업명", "메인아이템")},
        "재작업후보": candidates,
        "실행횟수": state.get("agent_attempts") or {},
        "미확인정보": {s: (state.get(f"{s}_analysis") or {}).get("미확인정보") for s in WORKERS},
        "선택지": [*candidates, "investment"],
    }, ensure_ascii=False, default=str)
    try:
        llm = get_llm().with_structured_output(RouteResponse, method="json_schema", strict=True)
        return llm.invoke([("system", build_system_prompt()), ("user", user)])
    except Exception:
        return None


def _valid(resp: RouteResponse | None, candidates: dict[str, str]) -> list[str] | None:
    if resp is None or not resp.next:
        return None
    chosen = set(resp.next)
    if chosen == {"investment"}:
        return ["investment"]
    if chosen <= set(candidates):
        return [s for s in WORKERS if s in chosen]
    return None


def run(state: State) -> dict:
    nxt, rework, reason = decide_next(state)
    if nxt[0] in WORKERS and set(nxt) <= set(rework_candidates(state)) and not any(
            _must_run(s, state) for s in WORKERS):
        resp = _ask_llm(state, rework)
        if chosen := _valid(resp, rework):
            nxt, reason = chosen, f"LLM 판단: {resp.reason}"
            rework = {s: w for s, w in rework.items() if s in chosen}
        else:
            reason = f"{reason} (LLM 무응답·무효 → 규칙 정책)"
    errors = state.get("errors") or []
    cid = (state.get("current_company") or {}).get("company_id")
    last = next((e for e in reversed(errors) if e.get("company_id") == cid), None)
    log_decision(state, "supervisor", nxt, reason)
    return {"next": nxt, "rework_reason": rework, "route_reason": reason,
            "step_count": state.get("step_count", 0) + 1, "last_error": last}


def route(state: State) -> list[str]:
    return state["next"]
