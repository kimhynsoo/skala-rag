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
    assert {"load", "eligibility", "supervisor", "technology", "market", "competitor", "investment", "report"} <= set(nodes)


def test_rank_key_tiebreak():
    def rec(total, tech, unknown=0):
        return {"scorecard": {"total": total, "averages": {"제품/기술력": tech, "실적": 3}, "unknown_items": ["x"] * unknown}}

    a, b, c = rec(80, 3), rec(80, 4), rec(80, 4, unknown=2)
    assert sorted([a, c, b], key=rank_key) == [b, c, a]  # 총점 동점 → 기술력 → 확인 불가 적은 순


def test_loop_flow_with_supervisor(monkeypatch):
    """c1 부적격 → c2 기술 계속 실패(재시도 1회 후 보류) → c3·c4 적격.
    기술은 항상 근거 부족(재작업 1회), 시장은 충분, 경쟁은 비어 있음(재작업 1회). 총점 1위 c4."""
    import obs
    from agents import competitor, eligibility, investment, loader, market, report, technology

    calls = []
    verdicts = {"c1": "부적격", "c2": "적격", "c3": "적격", "c4": "적격"}
    cid = lambda s: s["current_company"]["company_id"]  # noqa: E731

    def tech(s):
        calls.append(("tech", cid(s)))
        if cid(s) == "c2":
            raise RuntimeError("boom")
        return {"technology_analysis": {"근거충분": False, "근거ID": []}, "current_evidence": [{"id": f"{cid(s)}-t"}]}

    def mkt(s):
        calls.append(("mkt", cid(s)))
        return {"market_analysis": {"근거충분": True, "근거ID": ["MKT-1", "MKT-2"]}}

    def cmp_(s):
        calls.append(("cmp", cid(s)))
        return {"competitor_analysis": {"경쟁제품": [], "근거ID": []}}

    monkeypatch.setattr(loader, "run", lambda s: {"candidate_companies": [{"company_id": c} for c in verdicts]})
    monkeypatch.setattr(eligibility, "run", lambda s: {"eligibility": {"판정": verdicts[cid(s)], "사유": "x"}})
    monkeypatch.setattr(technology, "run", tech)
    monkeypatch.setattr(market, "run", mkt)
    monkeypatch.setattr(competitor, "run", cmp_)
    totals = {"c3": 75, "c4": 80}
    monkeypatch.setattr(investment, "run", lambda s: {
        "decision": "투자 적격",
        "scorecard": {"total": totals[cid(s)], "averages": {"제품/기술력": 4, "실적": 3}, "unknown_items": []},
    })
    monkeypatch.setattr(report, "run", lambda s: {"final_report": "ok"})

    out = build_graph().invoke({"trace_id": "t"}, {"recursion_limit": 300})
    records = {r["company_id"]: r for r in out["evaluation_results"]}
    assert [r["decision"] for r in out["evaluation_results"]] == ["제외", "보류", "투자 적격", "투자 적격"]
    assert calls.count(("tech", "c2")) == 2  # 실패 → 재시도 1회 → handle_error
    for c in ("c3", "c4"):  # 기업 전환 시 실행 횟수 리셋 확인 (c4도 같은 횟수)
        assert calls.count(("tech", c)) == 2  # 근거 부족 → 재작업 1회
        assert calls.count(("mkt", c)) == 1  # 충분 → 재작업 없음
        assert calls.count(("cmp", c)) == 2
    assert out["ranking"] == ["c4", "c3"] and out["selected_company_id"] == "c4"
    assert records["c3"]["current_evidence"] == [{"id": "c3-t"}, {"id": "c3-t"}]
    assert out["errors"][0]["stage"] == "technology"
    assert obs.summarize("t")["reworks"] == 5  # c2 기술 재시도 1 + c3·c4 각각 (기술 1 + 경쟁 1)
