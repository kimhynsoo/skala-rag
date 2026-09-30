"""⑥ 투자 판단 에이전트 — LLM은 항목별 점수·근거만, 총점·판정은 코드(total_score, decide)."""

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
    raise NotImplementedError
