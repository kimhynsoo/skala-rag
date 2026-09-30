import pytest

from agents import _report_llm, investment
from agents._report_scoring import (
    ITEM_IDS,
    Q_IDS,
    ChecklistOut,
    DetailsOut,
    InvestmentOut,
    ScoreOut,
    score_e2,
    score_e3,
)
from tests.fixtures.fake_results import company, fake_results


def test_e2_sales_rules():
    assert score_e2(company("C1", "a", {"연도": 2024, "국내": 1_000_000, "해외": None, "상태": "공개"}))[0] == 5
    assert score_e2(company("C1", "a", {"연도": 2024, "국내": 100_000, "해외": None, "상태": "공개"}))[0] == 3
    assert score_e2(company("C1", "a", {"연도": 2024, "국내": 99_999, "해외": None, "상태": "공개"}))[0] == 2
    s, unk, _ = score_e2(company("C1", "a", {"연도": 2024, "국내": None, "해외": None, "상태": "N/A"}))
    assert (s, unk) == (1, False)  # N/A = 매출 없음
    s, unk, _ = score_e2(company("C1", "a", {"연도": 2024, "국내": None, "해외": None, "상태": "비공개"}))
    assert (s, unk) == (2, True)  # 비공개 = 확인 불가


def test_e3_investment_rules():
    big = [{"금액": 10_000_000, "투자자": ["A", "B"], "확정": True}]
    assert score_e3(company("C1", "a", history=big))[0] == 5
    assert score_e3(company("C1", "a", history=[{"금액": 10_000_000, "투자자": ["A"], "확정": True}]))[0] == 4
    assert score_e3(company("C1", "a", history=[{"금액": 1_000_000, "투자자": ["A"], "확정": True}]))[0] == 3
    # 협의 중(미확정)은 금액에서 제외
    pending = [{"금액": 9_000_000, "투자자": ["A"], "확정": False}]
    assert score_e3(company("C1", "a", history=pending))[0] == 1
    assert score_e3(company("C1", "a", history=None)) [:2] == (2, True)


def _llm_out(score=4, unknown=(), bad_ids=False) -> InvestmentOut:
    ids = ["NOPE-C03-99", "DIR-C03-01"] if bad_ids else ["DIR-C03-01"]
    return InvestmentOut(
        checklist=[ChecklistOut(id=q, 판정="YES", 근거="x", 근거ID=ids) for q in Q_IDS],
        scorecard=[ScoreOut(id=i, 점수=score, 확인불가=i in unknown, 채점이유="r", 근거ID=ids) for i in ITEM_IDS],
        decision_details=DetailsOut(판단사유="s", 주요위험=["r"], 추가확인사항=[], 재검토조건=[]),
    )


def _state():
    rec = fake_results()[0]
    return {k: rec[k] for k in ("current_company", "eligibility", "technology_analysis", "market_analysis",
                                "competitor_analysis", "current_evidence")}


def test_run_computes_in_code(monkeypatch):
    monkeypatch.setattr(investment, "structured_call", lambda *a, **k: _llm_out(4, unknown={"B1"}, bad_ids=True))
    monkeypatch.setattr(investment, "load_prompt", lambda n: "p")
    out = investment.run(_state())
    sc = out["scorecard"]
    assert set(sc["items"]) == set(ITEM_IDS)
    assert sc["items"]["B1"]["점수"] == 2 and sc["unknown_items"] == ["B1"]  # 확인 불가는 2점 고정
    assert sc["items"]["E2"]["점수"] == 5 and "코드 산출" in sc["items"]["E2"]["채점이유"]  # LLM 값 덮어씀
    assert "NOPE-C03-99" not in sc["items"]["A1"]["근거ID"]  # 없는 근거 ID 제거
    assert sc["items"]["A1"]["근거ID"] == ["DIR-C03-01"]
    assert sc["total"] == investment.total_score({i: v["점수"] for i, v in sc["items"].items()})[1]
    assert out["decision"] == "투자 적격"
    assert set(out["checklist"]) == set(Q_IDS)


def test_run_missing_items_become_unknown(monkeypatch):
    partial = _llm_out(5)
    partial.scorecard = [s for s in partial.scorecard if s.id != "C3"]
    partial.checklist = partial.checklist[:5]
    monkeypatch.setattr(investment, "structured_call", lambda *a, **k: partial)
    monkeypatch.setattr(investment, "load_prompt", lambda n: "p")
    out = investment.run(_state())
    assert "C3" in out["scorecard"]["unknown_items"] and out["scorecard"]["items"]["C3"]["점수"] == 2
    assert out["checklist"]["Q11"]["판정"] == "확인불가"


def test_ineligible_or_pending_never_invests(monkeypatch):
    monkeypatch.setattr(investment, "structured_call", lambda *a, **k: _llm_out(5))
    monkeypatch.setattr(investment, "load_prompt", lambda n: "p")
    st = _state()
    st["eligibility"] = {**st["eligibility"], "판정": "확인필요"}
    assert investment.run(st)["decision"] == "보류"


def test_prompt_file_exists():
    assert "Q11" in _report_llm.load_prompt("investment")
