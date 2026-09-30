from agents.investment import decide, rank_key, total_score
from graph import build_graph
from rag.retriever import rrf
from state import merge_evidence


def test_merge_evidence_accumulates_and_resets():
    assert merge_evidence([{"id": 1}], [{"id": 2}]) == [{"id": 1}, {"id": 2}]
    assert merge_evidence([{"id": 1}], None) == []


def test_total_score():
    _, total = total_score({i: 5 for i in "A1 A2 A3 B1 B2 B3 C1 C2 C3 D1 D2 D3 E1 E2 E3".split()})
    assert total == 100
    averages, total = total_score({})  # 전부 확인 불가 → 2점
    assert total == 40 and averages["제품/기술력"] == 2


def test_decide():
    assert decide("부적격", 90, 5) == "제외"
    assert decide("확인필요", 90, 5) == "보류"
    assert decide("적격", 70, 3.0) == "투자 적격"
    assert decide("적격", 90, 2.9) == "보류"  # 기술 최소 조건
    assert decide("적격", 69.9, 5) == "보류"


def test_rrf_prefers_agreement():
    assert rrf({"dense": ["a", "b"], "sparse": ["b", "c"]})[0] == "b"


def test_graph_compiles():
    nodes = build_graph().get_graph().nodes
    assert {"load", "eligibility", "technology", "market", "competitor", "investment", "report"} <= set(nodes)


def test_rank_key_tiebreak():
    def rec(total, tech, unknown=0):
        return {"scorecard": {"total": total, "averages": {"제품/기술력": tech, "실적": 3}, "unknown_items": ["x"] * unknown}}

    a, b, c = rec(80, 3), rec(80, 4), rec(80, 4, unknown=2)
    assert sorted([a, c, b], key=rank_key) == [b, c, a]  # 총점 동점 → 기술력 → 확인 불가 적은 순


def test_loop_flow_with_fake_agents(monkeypatch):
    """c1 부적격 → c2 기술 단계 오류 → c3·c4 투자 적격(재검색 1회씩) → 끝까지 돈 뒤 총점 1위 c4 선정."""
    from agents import competitor, eligibility, investment, loader, market, report, technology
    from state import next_attempt

    calls = []
    verdicts = {"c1": "부적격", "c2": "적격", "c3": "적격", "c4": "적격"}
    cid = lambda s: s["current_company"]["company_id"]  # noqa: E731

    def tech(s):
        calls.append(("tech", cid(s)))
        if cid(s) == "c2":
            raise RuntimeError("boom")
        return {"technology_analysis": {"근거충분": False}, "retrieve_count": next_attempt(s, "technology_analysis"),
                "current_evidence": [{"id": f"{cid(s)}-t"}]}

    monkeypatch.setattr(loader, "run", lambda s: {"candidate_companies": [{"company_id": c} for c in verdicts]})
    monkeypatch.setattr(eligibility, "run", lambda s: {"eligibility": {"판정": verdicts[cid(s)], "사유": "x"}})
    monkeypatch.setattr(technology, "run", tech)
    monkeypatch.setattr(market, "run", lambda s: {"market_analysis": {"근거충분": True}, "retrieve_count": 1})
    monkeypatch.setattr(competitor, "run", lambda s: {"competitor_analysis": {}})
    totals = {"c3": 75, "c4": 80}
    monkeypatch.setattr(investment, "run", lambda s: {
        "decision": "투자 적격",
        "scorecard": {"total": totals[cid(s)], "averages": {"제품/기술력": 4, "실적": 3}, "unknown_items": []},
    })
    monkeypatch.setattr(report, "run", lambda s: {"final_report": "ok"})

    out = build_graph().invoke({})
    records = {r["company_id"]: r for r in out["evaluation_results"]}
    assert [r["decision"] for r in out["evaluation_results"]] == ["제외", "보류", "투자 적격", "투자 적격"]
    assert calls.count(("tech", "c3")) == 2  # 재검색 상한 1회
    assert out["ranking"] == ["c4", "c3"]
    assert out["selected_company_id"] == "c4"  # 처음 적격(c3)이 아니라 총점 1위
    assert records["c3"]["current_evidence"] == [{"id": "c3-t"}, {"id": "c3-t"}]  # 기업별 근거 분리 보존
    assert out["errors"][0]["stage"] == "technology"
