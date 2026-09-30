import json
import pytest
from agents import competitor
from schemas import CompetitorAnalysis


def test_competitor_schema_has_no_arbitrary_objects():
    schema = competitor.CompetitorComparison.model_json_schema()
    assert '"additionalProperties": {' not in json.dumps(schema)


def test_competitor_output_uses_shared_product_and_comparison_shapes():
    result = competitor.CompetitorComparison.model_validate({
        "경쟁제품": [{"기업명": "Rival", "제품": "Chip", "핵심지표값": [{"이름": "TOPS", "값": "12"}],
                   "source_url": "https://example.com", "source_excerpt": "12 TOPS"}],
        "비교표": [{"지표": "TOPS", "대상기업": "확인 불가", "경쟁사": [{"이름": "Rival", "값": "12"}]}],
    })
    output = result.model_dump() | {"근거ID": []}
    assert CompetitorAnalysis.model_validate(output).경쟁제품[0].핵심지표값[0].값 == "12"


def test_competitor_reuses_rag_evidence_id(monkeypatch):
    from types import SimpleNamespace

    context = {"근거ID": "TEC-02-0007", "doc_type": "tech", "chunk_id": "02-0007",
               "text": "industry reference", "title": "IRDS", "pub_year": 2024}
    comparison = competitor.CompetitorComparison()
    model = SimpleNamespace(with_structured_output=lambda *a, **k: SimpleNamespace(invoke=lambda messages: comparison))
    monkeypatch.setenv("TAVILY_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(competitor, "_retrieve_context", lambda *a: ([context], ""))
    monkeypatch.setattr(competitor, "_search_sources", lambda *a: ([{"url": "https://example.com"}], ""))
    monkeypatch.setattr(competitor, "get_llm", lambda: model)
    result = competitor.run({"current_company": {"company_id": "C01"}, "technology_analysis": {"핵심기술": "NPU"},
                             "market_analysis": {"목표고객": []}, "as_of_date": "2026-09-30",
                             "current_evidence": [{"근거ID": "TEC-02-0007"}]})
    assert result["current_evidence"] == []
    assert result["competitor_analysis"]["근거ID"] == ["TEC-02-0007"]


def test_agent_structured_output_retry_is_bounded(monkeypatch):
    from types import SimpleNamespace
    from langchain.agents.structured_output import StructuredOutputValidationError
    from langchain_core.messages import AIMessage
    import llm

    calls = []
    failure = StructuredOutputValidationError("GroundedTechnology", ValueError("Extra data"), AIMessage(content="bad"))
    def invoke(*args):
        calls.append(args)
        raise failure
    monkeypatch.setattr(llm, "get_llm", lambda: object())
    monkeypatch.setattr(llm, "create_agent", lambda *a, **k: SimpleNamespace(invoke=invoke))
    with pytest.raises(StructuredOutputValidationError):
        llm.run_agent("prompt", "input", competitor.CompetitorComparison)
    assert len(calls) == 2
    assert all(call[1]["recursion_limit"] == 12 for call in calls)
