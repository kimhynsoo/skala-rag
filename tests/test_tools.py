"""도구(tools/)와 Pydantic 스키마(schemas.py) 테스트. 모델·API 키 없이 실행된다."""

import inspect
import json
import re

import pytest
from pydantic import BaseModel

import schemas
from agents.investment import total_score
from rag import retriever
from tests.test_retriever import DOCS, fake_encode
from tools.dart import find_corps
from tools.retrieval import search_market_docs, search_tech_docs, to_evidence


@pytest.fixture
def index(monkeypatch, tmp_path):
    monkeypatch.setattr(retriever, "_encode", fake_encode)
    monkeypatch.setattr(retriever, "CACHE_DIR", tmp_path)
    retriever.build_index(DOCS)


# ---------- tools/retrieval ----------

def test_search_tools_label_evidence_ids(index):
    content, docs = search_tech_docs.func("memory 128 GT/s", sub_domain="interface")
    assert "[TEC-08-0001]" in content and all(d.metadata["doc_type"] == "tech" for d in docs)
    content, docs = search_market_docs.func("market demand")
    assert content.startswith("[MKT-13-0001]")


def test_to_evidence_dedupes_repeated_chunks(index):
    _, first = search_tech_docs.func("memory")
    _, again = search_tech_docs.func("memory roadmap")  # 재검색으로 같은 청크가 다시 나와도
    ev = to_evidence(first + again, checked="2026-09-30")
    ids = [e["근거ID"] for e in ev]
    assert len(ids) == len(set(ids)) and "TEC-06-0001" in ids
    assert ev[0]["확인일"] == "2026-09-30" and ev[0]["chunk_id"]


def test_tools_expose_llm_schema():
    args = search_tech_docs.args
    assert set(args) == {"query", "sub_domain"} and "interface" in json.dumps(args["sub_domain"])


# ---------- tools/dart ----------

def test_dart_find_corps(tmp_path):
    xml = tmp_path / "CORPCODE.xml"
    xml.write_text(
        "<result>"
        "<list><corp_code>001</corp_code><corp_name>(주)딥칩스</corp_name><stock_code> </stock_code></list>"
        "<list><corp_code>002</corp_code><corp_name>상장반도체</corp_name><stock_code>123456</stock_code></list>"
        "</result>", encoding="utf-8")
    assert find_corps("딥칩스 주식회사", xml)[0]["stock_code"] == ""  # 법인 표기·공백 무시, 비상장
    assert find_corps("상장반도체", xml)[0]["stock_code"] == "123456"
    assert find_corps("없는회사", xml) == []


# ---------- schemas ----------

def _check(result="충족"):
    return {"결과": result, "사유": "-", "근거ID": []}


def test_eligibility_verdict_computed_by_code():
    ok = schemas.Eligibility(G1=_check(), G2=_check(), G3=_check(), G4=_check(), 사유="-", 판정="부적격")
    assert ok.판정 == "적격"  # LLM이 쓴 값은 무시
    assert schemas.Eligibility(G1=_check(), G2=_check("확인불가"), G3=_check(), G4=_check(), 사유="-").판정 == "확인필요"
    assert schemas.Eligibility(G1=_check("미충족"), G2=_check("확인불가"), G3=_check(), G4=_check(), 사유="-").판정 == "부적격"


def test_scorecard_unknown_is_two_and_feeds_total_score():
    item = {"점수": 5, "채점이유": "-", "근거ID": []}
    items = schemas.ScorecardItems(**{k: item for k in schemas.ScorecardItems.model_fields}
                                   | {"E3": item | {"확인불가": True}})
    assert items.E3.점수 == 2 and items.unknown_items() == ["E3"]
    averages, total = total_score(items.scores())
    assert averages["실적"] == 4 and total == 97.0  # 85 + 4/5×15


def test_models_are_openai_structured_output_safe():
    """클래스명이 OpenAI 함수명 규칙(^[a-zA-Z0-9_-]+$)을 지키고, 임의 키 객체(dict 필드)가 없어야 한다."""
    models = [m for _, m in inspect.getmembers(schemas, inspect.isclass)
              if issubclass(m, BaseModel) and m is not BaseModel and m.__module__ == "schemas"]
    assert len(models) > 15
    for m in models:
        assert re.fullmatch(r"[a-zA-Z0-9_-]+", m.__name__), m.__name__
        assert '"additionalProperties": {' not in json.dumps(m.model_json_schema()), m.__name__


def test_model_dump_matches_contract_keys():
    dumped = schemas.TechnologyAnalysis(핵심기술="NPU", 제품성숙도={"단계": "시제품"}, 근거충분=False).model_dump()
    assert {"핵심기술", "제품성숙도", "성능지표", "기준대조", "근거ID", "근거충분"} <= set(dumped)
