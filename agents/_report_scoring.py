"""⑥ 투자 판단 보조: LLM 출력 스키마, 코드 산출 항목(E2·E3), 근거 ID 검증, 정규화."""

from typing import Literal

from pydantic import BaseModel, Field

from config import ITEMS, UNKNOWN_SCORE

Q_IDS = [f"Q{i}" for i in range(1, 12)]
ITEM_IDS = [i for items in ITEMS.values() for i in items]

# E2 매출 (천원 단위): 10억 / 1억
SALES_HIGH = 1_000_000
SALES_MID = 100_000
# E3 누적 투자 (천원 단위): 100억 / 10억
INVEST_HIGH = 10_000_000
INVEST_MID = 1_000_000


class ChecklistOut(BaseModel):
    id: Literal["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10", "Q11"]
    판정: Literal["YES", "PARTIAL", "NO", "확인불가"]
    근거: str
    근거ID: list[str] = Field(default_factory=list)


class ScoreOut(BaseModel):
    id: Literal["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "D3", "E1", "E2", "E3"]
    점수: int = Field(ge=1, le=5)
    확인불가: bool = Field(description="자료에 없거나 비공개라 판단할 수 없으면 true")
    채점이유: str
    근거ID: list[str] = Field(default_factory=list)


class DetailsOut(BaseModel):
    판단사유: str
    주요위험: list[str]
    추가확인사항: list[str]
    재검토조건: list[str]


class InvestmentOut(BaseModel):
    checklist: list[ChecklistOut]
    scorecard: list[ScoreOut]
    decision_details: DetailsOut


# ── 코드 산출 항목 ─────────────────────────────────────────────────────────

def score_e2(company: dict) -> tuple[int, bool, str]:
    """E2 매출 — 최근 연도 매출(국내+해외, 천원). N/A는 1점, 비공개는 확인 불가 2점."""
    s = company.get("매출액") or {}
    status = s.get("상태")
    if status == "비공개" or (status is None and not s):
        return UNKNOWN_SCORE, True, "매출 비공개 또는 기재 없음 → 확인 불가"
    if status == "N/A":
        return 1, False, "매출 N/A → 매출 없음"
    total = (s.get("국내") or 0) + (s.get("해외") or 0)
    year = s.get("연도")
    if total >= SALES_HIGH:
        return 5, False, f"{year}년 매출 {total:,}천원 (10억 원 이상)"
    if total >= SALES_MID:
        return 3, False, f"{year}년 매출 {total:,}천원 (1억~10억 원)"
    if total > 0:
        return 2, False, f"{year}년 매출 {total:,}천원 (1억 원 미만)"
    return 1, False, f"{year}년 매출 없음"


def score_e3(company: dict) -> tuple[int, bool, str]:
    """E3 투자 유치 — 확정 투자만 합산(협의 중 제외). 100억↑이며 투자자 2곳↑이면 5점."""
    history = company.get("투자유치이력")
    if history is None:
        return UNKNOWN_SCORE, True, "투자 유치 이력 기재 없음 → 확인 불가"
    confirmed = [h for h in history if h.get("확정", True)]
    total = sum(h.get("금액") or 0 for h in confirmed)
    investors = {i for h in confirmed for i in (h.get("투자자") or [])}
    text = f"확정 투자 누적 {total:,}천원, 투자자 {len(investors)}곳 (협의 중 제외)"
    if total >= INVEST_HIGH:
        return (5 if len(investors) >= 2 else 4), False, text
    if total >= INVEST_MID:
        return 3, False, text
    return 1, False, text


CODE_SCORED = {"E2": score_e2, "E3": score_e3}


# ── 근거 ID ────────────────────────────────────────────────────────────────

def allowed_evidence_ids(state: dict) -> set[str]:
    """이번 기업에서 실제로 확보된 근거 ID (current_evidence + 각 분석 결과에 적힌 ID)."""
    ids = {e["근거ID"] for e in state.get("current_evidence") or [] if e.get("근거ID")}
    for key in ("eligibility", "technology_analysis", "market_analysis", "competitor_analysis"):
        ids.update((state.get(key) or {}).get("근거ID") or [])
    return ids


def _clean_ids(ids: list[str], allowed: set[str]) -> list[str]:
    seen: list[str] = []
    for i in ids:
        if i in allowed and i not in seen:
            seen.append(i)
    return seen


# ── 정규화 ─────────────────────────────────────────────────────────────────

def normalize(out: InvestmentOut, state: dict) -> tuple[dict, dict, list[str]]:
    """LLM 출력 → (checklist, score items, unknown_items).

    - 없는 ID는 버리고, 누락 문항은 확인 불가로 채운다(점수 2).
    - 확인 불가는 LLM 점수와 무관하게 2점으로 고정한다.
    - E2·E3는 숫자 규칙으로 코드가 다시 계산해 LLM 값을 덮어쓴다.
    - 허용되지 않은 근거 ID는 제거한다(보고서 REFERENCE가 만들 수 없는 ID 방지).
    """
    allowed = allowed_evidence_ids(state)
    company = state.get("current_company") or {}

    checklist = {
        q.id: {"판정": q.판정, "근거": q.근거, "근거ID": _clean_ids(q.근거ID, allowed)} for q in out.checklist
    }
    for q in Q_IDS:
        checklist.setdefault(q, {"판정": "확인불가", "근거": "LLM 출력 누락", "근거ID": []})

    items: dict[str, dict] = {}
    unknown: list[str] = []
    for s in out.scorecard:
        score = UNKNOWN_SCORE if s.확인불가 else s.점수
        items[s.id] = {"점수": score, "채점이유": s.채점이유, "근거ID": _clean_ids(s.근거ID, allowed)}
        if s.확인불가:
            unknown.append(s.id)

    dir_ids = sorted(i for i in allowed if i.startswith("DIR-"))
    for item_id, fn in CODE_SCORED.items():
        score, is_unknown, reason = fn(company)
        items[item_id] = {"점수": score, "채점이유": f"{reason} (코드 산출)", "근거ID": dir_ids}
        if is_unknown and item_id not in unknown:
            unknown.append(item_id)
        if not is_unknown and item_id in unknown:
            unknown.remove(item_id)

    for item_id in ITEM_IDS:
        if item_id not in items:
            items[item_id] = {"점수": UNKNOWN_SCORE, "채점이유": "LLM 출력 누락 → 확인 불가", "근거ID": []}
            unknown.append(item_id)

    return checklist, items, [i for i in ITEM_IDS if i in unknown]
