"""D ↔ A/B/E 연결 검증. 실제 팀 데이터·검색 도구를 사용하되 LLM·임베딩 호출은 대체한다."""

import json
from copy import deepcopy

import pytest

import schemas
from agents import _rag_utils as rag, investment, loader, market, technology
from agents._report_scoring import ChecklistOut, DetailsOut, InvestmentOut, Q_IDS, ScoreOut, ITEM_IDS
from rag import parser
from tools.retrieval import to_evidence
from tests.fixtures.fake_results import company
from tests.test_rag_agents import (
    TECH_TEXT, apply_update, company_state, document, market_output, tech_output,
)


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, "CACHE_DIR", tmp_path)


def test_d_and_b_use_the_same_ids_and_source_metadata():
    doc = document()
    first, _ = rag.collect_evidence(company_state("C01"), [doc, doc], "technology")
    second, _ = rag.collect_evidence(company_state("C02"), [doc], "technology")
    assert first == second == to_evidence([doc], checked="2026-09-30")
    assert first[0]["근거ID"] == "TEC-02-0001"
    again, _ = rag.collect_evidence({**company_state(), "current_evidence": first}, [doc], "technology")
    assert again == []


@pytest.mark.parametrize("stage,agent,schema", [
    ("technology", technology, schemas.TechnologyAnalysis),
    ("market", market, schemas.MarketAnalysis),
])
def test_empty_outputs_follow_the_shared_schema(monkeypatch, stage, agent, schema):
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *a, **k: [])
    data = agent.run(company_state())[f"{stage}_analysis"]
    assert schema.model_validate(data).근거충분 is False
    if stage == "market":
        assert data["시장규모"]["값"] == "확인 불가" and data["시장규모"]["기준연도"] is None
        assert data["성장률"]["기간"] == "확인 불가"
    else:
        assert data["제품성숙도"]["TRL"] is None


def test_shared_agent_additional_search_artifacts_are_validated_and_merged(monkeypatch):
    initial = document(text="기술 문서 목차")
    additional = document(chunk="02-0002", text=TECH_TEXT)
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *a, **k: [initial])
    searches = []

    def search(query, **filters):
        searches.append((query, filters))
        return [additional]

    monkeypatch.setattr(rag.retrieval_tools, "hybrid_search", search)

    def fake_agent(system, user, schema, tools):
        content, docs = tools[0].func("NPU TOPS/W INT8 benchmark")
        assert "[TEC-02-0002]" in content
        assert tools[0].func("다시 검색")[1] == []
        result = json.loads(json.dumps(tech_output()).replace("TEC-02-0001", "TEC-02-0002"))
        audit = result.pop("_검증")
        return schema.model_validate({"분석": result, **audit}), docs

    monkeypatch.setattr(rag.llm, "run_agent", fake_agent)
    update = technology.run(company_state())
    assert update["technology_analysis"]["근거충분"] is True
    assert update["technology_analysis"]["기준대조"][0]["비교결과"] == "상회"
    assert [e["근거ID"] for e in update["current_evidence"]] == ["TEC-02-0001", "TEC-02-0002"]
    assert searches == [("NPU TOPS/W INT8 benchmark", {"doc_type": "tech", "sub_domain": "ai_computing"})]
    assert "_검증" not in update["technology_analysis"] and "_검색문서" not in update["technology_analysis"]


def test_search_tool_filters_future_material_before_the_model_can_read_it(monkeypatch):
    future = document()
    future.metadata["pub_year"] = 2027
    monkeypatch.setattr(rag.retrieval_tools, "hybrid_search", lambda *a, **k: [future])

    def fake_agent(system, user, schema, tools):
        content, docs = tools[0].func("NPU benchmark")
        assert docs == [] and "TEC-" not in content
        result = tech_output()
        audit = result.pop("_검증")
        return schema.model_validate({"분석": result, **audit}), docs

    monkeypatch.setattr(rag.llm, "run_agent", fake_agent)
    rag.generate_analysis("technology", {"기업정보": company_state()["current_company"], "조사기준일": "2026-09-30"})


@pytest.fixture(scope="module")
def real_corpus():
    return parser.load_corpus()


@pytest.mark.parametrize("cid", ["C01", "C18", "C40"])
def test_actual_a_records_and_corpus_connect_to_d_without_losing_directory_text(monkeypatch, real_corpus, cid):
    records = loader.run({})["candidate_companies"]
    assert len(records) == 45
    selected = next(c for c in records if c["company_id"] == cid)
    payloads = []

    def search(query, doc_type, sub_domain=None, k=5):
        if cid == "C18" and doc_type == "tech":
            assert "memory expansion" in query and "UCIe" not in query
        return [d for d in real_corpus if d.metadata["doc_type"] == doc_type
                and (sub_domain is None or d.metadata["sub_domain"] == sub_domain)][:k]

    def generate(stage, payload):
        payloads.append(deepcopy(payload))
        data = rag._empty_analysis(stage)
        data["근거ID"] = [e["근거ID"] for e in payload["검색근거"]]
        return data

    monkeypatch.setattr(rag.retriever, "hybrid_search", search)
    monkeypatch.setattr(rag, "generate_analysis", generate)
    state = {"current_company": selected, "as_of_date": "2026-09-30", "current_evidence": []}
    tech = technology.run(state)
    state = apply_update(state, tech)
    out = market.run(state)
    schemas.TechnologyAnalysis.model_validate(tech["technology_analysis"])
    schemas.MarketAnalysis.model_validate(out["market_analysis"])
    directory = next(e for e in tech["current_evidence"] if e["근거ID"].startswith("DIR-"))
    schemas.Evidence.model_validate(directory)
    assert directory["source_page"] == selected["source_page"]
    assert directory["원문발췌"] == selected["원문"][:300]
    assert rag.evidence_text(directory) == selected["원문"]
    assert not any(e["근거ID"].startswith("DIR-") for e in out["current_evidence"])
    assert all(any(e["검색원문"] == selected["원문"] for e in payload["기존근거"]) for payload in payloads)


def test_current_e_judgement_accepts_d_outputs_and_shared_rag_ids(monkeypatch):
    state = company_state()
    state["current_company"] = company("C01", "가상기업")
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda q, **f: [document(f["doc_type"])])
    monkeypatch.setattr(rag, "generate_analysis", lambda stage, payload: tech_output() if stage == "technology" else market_output())
    state = apply_update(state, technology.run(state))
    state = apply_update(state, market.run(state))
    state.update(eligibility={"판정": "적격"}, competitor_analysis={})
    ids = [e["근거ID"] for e in state["current_evidence"]]

    def judgement(schema, system, user):
        payload = json.loads(user)
        assert payload["기술분석"]["성능지표"][0]["값"] == "12 TOPS/W"
        assert payload["시장분석"]["시장규모"]["값"] == "USD 1B"
        return InvestmentOut(
            checklist=[ChecklistOut(id=q, 판정="YES", 근거="테스트", 근거ID=ids) for q in Q_IDS],
            scorecard=[ScoreOut(id=i, 점수=4, 확인불가=False, 채점이유="테스트", 근거ID=ids) for i in ITEM_IDS],
            decision_details=DetailsOut(판단사유="테스트", 주요위험=[], 추가확인사항=[], 재검토조건=[]),
        )

    monkeypatch.setattr(investment, "structured_call", judgement)
    out = investment.run(state)
    assert out["decision"] == "투자 적격"
    assert {"TEC-02-0001", "MKT-13-0001"} <= set(out["scorecard"]["items"]["C3"]["근거ID"])


@pytest.mark.parametrize("stage,schema", [
    ("technology", rag.GroundedTechnology), ("market", rag.GroundedMarket),
])
def test_prompt_json_example_satisfies_the_actual_output_tool(stage, schema):
    import re

    prompt = rag.llm.load_prompt(stage)
    example = json.loads(re.search(r"```json\s*(.*?)\s*```", prompt, re.S).group(1))
    output = schema.model_validate(example)
    assert output.분석.근거충분 is False
    assert "근거충분" not in example


def _structured_model(stage, repair):
    """실제 ToolStrategy에 사용자가 관측한 잘못된 도구 인자를 반환한다."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage

    class ToolCallingModel(FakeMessagesListChatModel):
        calls: int = 0

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.calls += 1
            result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            for generation in result.generations:
                generation.message = generation.message.model_copy(update={"id": f"test-llm-{self.calls}"})
            return result

    expected = tech_output() if stage == "technology" else market_output()
    audit = expected.pop("_검증")
    enough = expected["근거충분"]
    bad = {"분석": {k: v for k, v in expected.items() if k != "근거충분"}, "근거충분": "잘못된 불리언"}
    schema = rag.GroundedTechnology if stage == "technology" else rag.GroundedMarket

    def message(args):
        return AIMessage(content="", tool_calls=[{"name": schema.__name__, "args": args, "id": "grounded-output"}])

    responses = [message(bad)]
    if repair:
        responses.append(message({"분석": expected, **audit}))
    return ToolCallingModel(responses=responses)


@pytest.mark.parametrize("stage", ["technology", "market"])
def test_real_tool_strategy_can_correct_one_malformed_response(monkeypatch, stage):
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.runnables import RunnableLambda

    class Observer(BaseCallbackHandler):
        def __init__(self):
            self.calls = 0

        def on_chat_model_start(self, serialized, messages, **kwargs):
            self.calls += 1

    model = _structured_model(stage, repair=True)
    monkeypatch.setattr(rag.llm, "get_llm", lambda: model)
    observer = Observer()
    result = RunnableLambda(lambda _: rag.generate_analysis(stage, {})).invoke(None, config={"callbacks": [observer]})
    assert model.calls == 2
    assert observer.calls == 2  # 노트북의 진행 로그도 내부 호출에 계속 전달된다.
    assert result == (tech_output() if stage == "technology" else market_output())


@pytest.mark.parametrize("stage", ["technology", "market"])
def test_malformed_output_loop_is_bounded_even_under_the_full_pipeline_limit(monkeypatch, stage):
    from langchain_core.runnables import RunnableLambda

    model = _structured_model(stage, repair=False)
    monkeypatch.setattr(rag.llm, "get_llm", lambda: model)
    outer = RunnableLambda(lambda _: rag.generate_analysis(stage, {}))
    with pytest.raises(RuntimeError, match="LLM 호출 6회 제한 초과"):
        outer.invoke(None, config={"recursion_limit": 1000})
    assert model.calls == 6


@pytest.mark.parametrize("stage", ["technology", "market"])
def test_misplaced_flag_and_missing_audits_are_conservative(stage):
    data = tech_output() if stage == "technology" else market_output()
    data.pop("_검증")
    flag = data.pop("근거충분")
    schema = rag.GroundedTechnology if stage == "technology" else rag.GroundedMarket
    result = schema.model_validate({"분석": data, "근거충분": flag})
    assert result.분석.근거충분 is flag
    assert result.수치근거 == []
    assert (result.기술비교 if stage == "technology" else result.시장검증) == []


def test_competitor_table_preserves_list_and_numeric_contents():
    from agents.competitor import CompetitorComparison
    result = CompetitorComparison.model_validate({"비교표": [{"기업": "실제 기업", "특징": ["특징 A", "특징 B"], "수치": 12}]})
    assert json.loads(result.비교표[0]["특징"]) == ["특징 A", "특징 B"]
    assert result.비교표[0]["수치"] == "12"
