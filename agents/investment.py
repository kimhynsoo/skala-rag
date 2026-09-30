"""⑥ 투자 판단 에이전트 — LLM은 항목별 점수·근거만, 총점·판정은 코드(total_score, decide)."""

import json
from concurrent.futures import ThreadPoolExecutor

from agents._report_llm import load_prompt, structured_call
from agents._report_scoring import SCORING_RUNS, InvestmentOut, aggregate, normalize
from config import INVEST_THRESHOLD, ITEMS, TECH_MIN, UNKNOWN_SCORE, WEIGHTS
from state import State


def total_score(item_scores: dict[str, int]) -> tuple[dict[str, float], float]:
    """세부 항목 점수(1~5) → (대분류 평균, 가중 총점 0~100). 누락 항목은 확인 불가(2점)."""
    averages = {
        cat: sum(item_scores.get(i, UNKNOWN_SCORE) for i in items) / len(items)
        for cat, items in ITEMS.items()
    }
    total = sum(averages[cat] / 5 * WEIGHTS[cat] for cat in ITEMS)
    return averages, round(total, 1)


def decide(verdict: str, total: float, tech_avg: float) -> str:
    """최종 판정 규칙 (투자 판단 기준 5)."""
    if verdict == "부적격":
        return "제외"
    if verdict != "적격":
        return "보류"
    if total >= INVEST_THRESHOLD and tech_avg >= TECH_MIN:
        return "투자 적격"
    return "보류"


def rank_key(record: dict) -> tuple:
    """투자 적격 기업 순위 (투자 판단 기준 5): 총점 → 제품/기술력 → 확인 불가 항목 수(적은 순) → 실적."""
    sc = record["scorecard"]
    return (-sc["total"], -sc["averages"]["제품/기술력"], len(sc.get("unknown_items", [])), -sc["averages"]["실적"])


def run(state: State) -> dict:
    """
    입력: current_company, eligibility, technology_analysis, market_analysis, competitor_analysis, evaluation_criteria
    처리: LLM → checklist 11문항 {판정, 근거, 근거ID} + 세부 항목 {점수, 채점이유, 근거ID}
          → total_score() → decide(eligibility["판정"], total, averages["제품/기술력"])
    출력: {"checklist": ..., "scorecard": {items, averages, total, unknown_items: [확인 불가 항목 ID]},
          "decision": ..., "decision_details": {...}}
    """
    company = state["current_company"]
    evidence = state.get("current_evidence") or []
    payload = {
        "기업": company,
        "적격성": state.get("eligibility"),
        "기술분석": state.get("technology_analysis"),
        "시장분석": state.get("market_analysis"),
        "경쟁분석": state.get("competitor_analysis"),
        "사용 가능한 근거ID": [
            {"근거ID": e["근거ID"], "출처명": e.get("출처명"), "원문발췌": (e.get("원문발췌") or "")[:200]}
            for e in evidence
            if e.get("근거ID")
        ],
    }
    system, user = load_prompt("investment"), json.dumps(payload, ensure_ascii=False, default=str)

    def one_run(_: int):
        return structured_call(InvestmentOut, system, user)

    # 같은 입력도 LLM 채점은 실행마다 흔들리므로 SCORING_RUNS번 동시에 채점해 중앙값을 쓴다.
    with ThreadPoolExecutor(max_workers=SCORING_RUNS) as pool:
        futures = [pool.submit(one_run, k) for k in range(SCORING_RUNS)]
        outs, errors = [], []
        for f in futures:
            try:
                outs.append(f.result())
            except Exception as e:  # 일부 회차 실패는 허용, 전부 실패하면 그대로 실패
                errors.append(e)
    if not outs:
        raise errors[0]
    runs = [normalize(o, state) for o in outs]
    checklist, items, unknown, details, repeat = aggregate(runs, [o.decision_details.model_dump() for o in outs], total_score)

    item_scores = {i: v["점수"] for i, v in items.items()}
    averages, total = total_score(item_scores)
    verdict = (state.get("eligibility") or {}).get("판정", "확인필요")
    return {
        "checklist": checklist,
        "scorecard": {"items": items, "averages": averages, "total": total, "unknown_items": unknown, "repeat": repeat},
        "decision": decide(verdict, total, averages["제품/기술력"]),
        "decision_details": details,
    }
