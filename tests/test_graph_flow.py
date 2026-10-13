"""실제 technology·market 노드를 Supervisor 그래프에 넣은 통합 검증. 외부 API는 호출하지 않는다."""

from collections import Counter

from agents import _rag_utils as rag, technology
from graph import build_graph, guarded_worker
from tests.test_rag_agents import company_state, document, market_output, tech_output


def test_worker_failure_is_recorded_with_status_and_attempts(monkeypatch):
    def failing_search(*args, **kwargs):
        raise RuntimeError("검색기 오류")

    monkeypatch.setattr(rag.retriever, "hybrid_search", failing_search)
    update = guarded_worker("technology", technology.run)(company_state())
    assert update["errors"][0]["company_id"] == "C01" and update["errors"][0]["type"] == "RuntimeError"
    assert update["node_status"] == {"technology": "FAILED"}
    assert update["agent_attempts"] == {"technology": 1}


def test_real_d_nodes_in_graph_rework_and_reset_between_companies(monkeypatch):
    from agents import competitor, eligibility, investment, loader, report

    companies = [company_state(cid)["current_company"] for cid in ("C01", "C02")]
    calls = Counter()
    monkeypatch.setattr(loader, "run", lambda state: {"candidate_companies": companies})
    monkeypatch.setattr(eligibility, "run", lambda state: {
        "eligibility": {"판정": "적격"},
        "current_evidence": company_state(state["current_company"]["company_id"])["current_evidence"],
    })
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda query, **filters: [document(filters["doc_type"])])

    def generate(stage, payload):
        cid = payload["기업정보"]["company_id"]
        calls[(cid, stage)] += 1
        assert all(not e["근거ID"].startswith("DIR-") or f"-{cid}-" in e["근거ID"]
                   for e in payload["기존근거"] + payload["검색근거"])
        # 기술은 재작업으로 충분해지고, 시장은 상한 이후에도 부족한 상태로 투자 판단에 전달된다.
        return tech_output(cid, enough=calls[(cid, stage)] == 2) if stage == "technology" else market_output(cid, enough=False)

    monkeypatch.setattr(rag, "generate_analysis", generate)
    monkeypatch.setattr(competitor, "run", lambda state: {"competitor_analysis": {}})
    monkeypatch.setattr(investment, "run", lambda state: {"decision": "보류"})
    monkeypatch.setattr(report, "run", lambda state: {"final_report": "가상 보고서"})
    result = build_graph().invoke({"as_of_date": "2026-09-30"}, {"recursion_limit": 200})
    assert len(result["evaluation_results"]) == 2
    assert all(calls[(cid, stage)] == 2 for cid in ("C01", "C02") for stage in ("technology", "market"))
    for record in result["evaluation_results"]:
        ids = sorted(e["근거ID"] for e in record["current_evidence"])
        cid = record["company_id"]
        assert ids == sorted([f"DIR-{cid}-01", "TEC-02-0001", "MKT-13-0001"])
        assert record["technology_analysis"]["근거충분"] is True
        assert record["market_analysis"]["근거충분"] is False
    assert not result.get("errors")
