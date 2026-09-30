"""제공된 RAG_PDF 추출본의 실제 발췌와 적대적 입력으로 D 검증을 회귀 테스트한다.

PDF 발췌는 실제 원문이다. 기업 레코드·LLM 응답·검색 순위는 테스트용이며 실측 결과가 아니다.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from agents import _rag_utils as rag, market, technology
from tests.test_rag_agents import (
    DIR_TEXT, MARKET_TEXT, TECH_TEXT, apply_update, company_state, document, market_output, tech_output,
)


EXCERPTS = json.loads((Path(__file__).parent / "fixtures/rag_source_excerpts.json").read_text())


@pytest.fixture(autouse=True)
def isolate_text_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, "CACHE_DIR", tmp_path)


def evaluate_tech(monkeypatch, result, state=None, doc=None):
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *args, **kwargs: [doc or document()])
    monkeypatch.setattr(rag, "generate_analysis", lambda *args: result)
    return technology.run(state or company_state())["technology_analysis"]


def evaluate_market(monkeypatch, result, state=None, doc=None):
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *args, **kwargs: [doc or document("market")])
    monkeypatch.setattr(rag, "generate_analysis", lambda *args: result)
    return market.run(state or company_state())["market_analysis"]


@pytest.mark.parametrize("field,value", [("metric", "9999 TOPS/W"), ("TRL", 9)])
def test_existing_id_does_not_validate_fabricated_number(monkeypatch, field, value):
    result = tech_output()
    if field == "metric":
        result["성능지표"][0]["값"] = value
    else:
        result["제품성숙도"]["TRL"] = value
    analysis = evaluate_tech(monkeypatch, result)
    assert analysis["근거충분"] is False
    assert (analysis["성능지표"][0]["값"] if field == "metric" else analysis["제품성숙도"]["TRL"]) == ("확인 불가" if field == "metric" else None)


def test_fabricated_quote_is_rejected(monkeypatch):
    result = tech_output()
    result["성능지표"][0]["값"] = "9999 TOPS/W"
    result["_검증"]["수치근거"][1]["원문구절"] = "제품 실측 9999 TOPS/W INT8 7nm"
    analysis = evaluate_tech(monkeypatch, result)
    assert analysis["성능지표"][0]["값"] == "확인 불가"
    assert any("인용 구절" in gap for gap in analysis["미확인정보"])


def test_missing_audit_cannot_be_sufficient(monkeypatch):
    result = tech_output()
    del result["_검증"]
    analysis = evaluate_tech(monkeypatch, result)
    assert analysis["근거충분"] is False
    assert analysis["성능지표"][0]["값"] == "확인 불가"


@pytest.mark.parametrize("field", ["TRL", "metric", "baseline", "market_size", "market_growth"])
def test_mixed_ids_cannot_launder_a_number_from_another_source_lane(monkeypatch, field):
    state = company_state()
    if field in ("market_size", "market_growth"):
        # 기업 발췌에 같은 숫자가 있어도, 시장 수치의 증명은 MKT 원문이어야 한다.
        state["current_evidence"][0]["원문발췌"] += " " + MARKET_TEXT
        result = market_output()
        key = "시장규모" if field == "market_size" else "성장률"
        result[key]["근거ID"] = ["DIR-C01-01", "MKT-13-0001"]
        for support in result["_검증"]["수치근거"]:
            if support["경로"] == f"{key}.값":
                support.update(근거ID="DIR-C01-01", 원문구절=MARKET_TEXT)
        analysis = evaluate_market(monkeypatch, result, state)
        assert analysis[key]["값"] == "확인 불가"
        other = "성장률" if key == "시장규모" else "시장규모"
        assert analysis[other]["값"] != "확인 불가"
    else:
        result, doc = tech_output(), document(text=TECH_TEXT + " 기준 성숙도 TRL 9.")
        if field == "TRL":
            item, path, value, support_ref, quote = result["제품성숙도"], "제품성숙도.TRL", 9, "TEC-02-0001", doc.page_content
            item["TRL"] = value
        elif field == "metric":
            item, path, value, support_ref, quote = result["성능지표"][0], "성능지표.0.값", "10 TOPS/W", "TEC-02-0001", TECH_TEXT
            item["값"] = value
        else:
            item, path, value, support_ref, quote = result["기준대조"][0], "기준대조.0.업계기준", "12 TOPS/W", "DIR-C01-01", DIR_TEXT
            item["업계기준"] = value
        item["근거ID"] = ["DIR-C01-01", "TEC-02-0001"]
        for support in result["_검증"]["수치근거"]:
            if support["경로"] == path:
                support.update(근거ID=support_ref, 원문구절=quote)
        analysis = evaluate_tech(monkeypatch, result, state, doc)
        if field == "TRL":
            assert analysis["제품성숙도"]["TRL"] is None
            assert analysis["성능지표"][0]["값"] == "12 TOPS/W"
        elif field == "metric":
            assert analysis["성능지표"][0]["값"] == "확인 불가"
        else:
            assert analysis["기준대조"][0]["업계기준"] == "확인 불가"
            assert analysis["성능지표"][0]["값"] == "12 TOPS/W"
    assert analysis["근거충분"] is False


@pytest.mark.parametrize("stage", ["technology", "market"])
def test_verified_quotes_repair_omitted_field_ids_without_rejecting_the_analysis(monkeypatch, stage):
    result = tech_output() if stage == "technology" else market_output()
    items = [result["제품성숙도"], *result["성능지표"], *result["기준대조"]] if stage == "technology" else [result["시장규모"], result["성장률"]]
    for item in items:
        item["근거ID"] = []
    result["근거ID"] = []
    evaluate = evaluate_tech if stage == "technology" else evaluate_market
    analysis = evaluate(monkeypatch, result)
    assert analysis["근거충분"] is True
    assert {"DIR-C01-01", "TEC-02-0001" if stage == "technology" else "MKT-13-0001"} <= set(analysis["근거ID"])
    key = "성능지표" if stage == "technology" else "시장규모"
    item = analysis[key][0] if stage == "technology" else analysis[key]
    assert item["근거ID"] == ["DIR-C01-01" if stage == "technology" else "MKT-13-0001"]


@pytest.mark.parametrize("stage", ["technology", "market"])
def test_context_citations_do_not_reject_a_correct_numeric_source(monkeypatch, stage):
    result = tech_output() if stage == "technology" else market_output()
    if stage == "technology":
        result["제품성숙도"]["근거ID"].append("TEC-02-0001")
        result["성능지표"][0]["근거ID"].append("TEC-02-0001")
        result["기준대조"][0]["근거ID"].append("DIR-C01-01")
        analysis = evaluate_tech(monkeypatch, result)
        assert analysis["성능지표"][0]["값"] == "12 TOPS/W"
        assert analysis["기준대조"][0]["비교결과"] == "상회"
    else:
        result["시장규모"]["근거ID"].append("DIR-C01-01")
        result["성장률"]["근거ID"].append("DIR-C01-01")
        analysis = evaluate_market(monkeypatch, result)
        assert analysis["시장규모"]["값"] == "USD 1B"
    assert analysis["근거충분"] is True and analysis["미확인정보"] == []


@pytest.mark.parametrize("title", [None, "없는 보고서", "가상 기관"])
def test_market_source_title_is_repaired_from_the_actual_numeric_source(monkeypatch, title):
    result = market_output()
    result["시장규모"]["출처"] = title
    # 함께 인용한 다른 문서를 출처명으로 섞지 않는다.
    state = company_state()
    additions, _ = rag.collect_evidence(state, [document("market")], "market")
    state["current_evidence"].extend(additions)
    state["current_evidence"].append({"근거ID": "MKT-13-0002", "출처명": "관계없는 보고서", "원문발췌": "배경 설명"})
    result["시장규모"]["근거ID"].append("MKT-13-0002")
    analysis = evaluate_market(monkeypatch, result, state)
    assert analysis["시장규모"]["출처"] == "가상 기관 보고서"
    assert analysis["근거충분"] is True and analysis["미확인정보"] == []


def test_contract_example_optional_fields_do_not_break_valid_analysis(monkeypatch):
    result = tech_output()
    del result["제품성숙도"]["근거ID"]
    assert evaluate_tech(monkeypatch, result)["근거충분"] is True
    result = market_output()
    del result["시장규모"]["출처"]
    analysis = evaluate_market(monkeypatch, result)
    assert analysis["시장규모"]["출처"] == "가상 기관 보고서"
    assert analysis["근거충분"] is True


def test_year_and_period_can_share_the_numeric_quote(monkeypatch):
    result = market_output()
    result["_검증"]["수치근거"] = [s for s in result["_검증"]["수치근거"] if s["경로"].endswith(".값")]
    analysis = evaluate_market(monkeypatch, result)
    assert analysis["시장규모"]["기준연도"] == 2025
    assert analysis["성장률"]["기간"] == "2025-2030"
    assert analysis["근거충분"] is True


def test_verified_numbers_survive_missing_comparison_conditions(monkeypatch):
    result = tech_output()
    result["_검증"]["기술비교"][0]["조건"] = []
    analysis = evaluate_tech(monkeypatch, result)
    assert analysis["성능지표"][0]["값"] == "12 TOPS/W"
    assert analysis["기준대조"][0]["업계기준"] == "10 TOPS/W INT8 7nm"
    assert analysis["기준대조"][0]["비교결과"] == "비교불가"
    assert analysis["근거충분"] is False


def test_comparison_accepts_spacing_and_missing_optional_conditions(monkeypatch):
    text = TECH_TEXT.replace("INT8", "int 8").replace("7nm", "7 nm").replace("ResNet50", "resnet 50")
    result = tech_output()
    result["_검증"]["수치근거"][2]["원문구절"] = text
    for pair in result["_검증"]["기술비교"][0]["조건"]:
        pair["기준조건"] = {"정밀도": "int 8", "공정": "7 nm", "워크로드": "resnet 50", "측정방식": "실측"}[pair["항목"]]
    result["_검증"]["기술비교"][0]["조건"].append({"항목": "부가메모", "기업조건": None, "기준조건": None})
    analysis = evaluate_tech(monkeypatch, result, doc=document(text=text))
    assert analysis["기준대조"][0]["비교결과"] == "상회"
    assert analysis["근거충분"] is True


@pytest.mark.parametrize("field,changed", [("정밀도", "FP16"), ("공정", "3nm"), ("워크로드", "MobileNet")])
def test_mismatched_conditions_are_not_ranked(monkeypatch, field, changed):
    result = tech_output()
    text = TECH_TEXT
    for pair in result["_검증"]["기술비교"][0]["조건"]:
        if pair["항목"] == field:
            text = text.replace(pair["기준조건"], changed)
            pair["기준조건"] = changed
    result["기준대조"][0]["업계기준"] = "10 TOPS/W"
    result["_검증"]["수치근거"][2]["원문구절"] = text
    analysis = evaluate_tech(monkeypatch, result, doc=document(text=text))
    assert analysis["기준대조"][0]["업계기준"] == "10 TOPS/W"
    assert analysis["기준대조"][0]["비교결과"] == "비교불가"
    assert analysis["근거충분"] is False


def test_comparison_direction_is_computed(monkeypatch):
    result = tech_output()
    result["기준대조"][0]["비교결과"] = "하회"
    assert evaluate_tech(monkeypatch, result)["기준대조"][0]["비교결과"] == "상회"


@pytest.mark.parametrize("claim,quote", [
    ("12 GHz", "12 MHz"), ("12 kg", "12 mg"), ("EUR 1 billion", "USD 1 billion"),
    ("768 GT/s", EXCERPTS["cxl"]["text"]),
])
def test_numeric_match_keeps_units_and_currency(claim, quote):
    assert rag._numeric_matches(claim, quote) is False


@pytest.mark.parametrize("claim,quote", [
    ("USD 1.51T", "USD 1.51 trillion"), ("90%", "90 percent"), ("10 μm", "10 µm"),
])
def test_only_explicit_unit_aliases_are_normalized(claim, quote):
    assert rag._numeric_matches(claim, quote) is True


def test_numeric_narrative_without_support_is_removed(monkeypatch):
    result = tech_output()
    result["강점"] = ["해외 고객 100곳 확보", "매출 9999억 [DIR-C01-01]"]
    analysis = evaluate_tech(monkeypatch, result)
    assert analysis["강점"] == [] and analysis["근거충분"] is False


def interface_result(text, value="128 GT/s", baseline="128 GT/s"):
    state = company_state(domain="interface", item="가상 CXL IP")
    company_quote = "가상 CXL 4.0 PAM4 시제품: TRL 6. 규격 128 GT/s 자체 발표."
    state["current_evidence"][0]["원문발췌"] = company_quote
    result = tech_output()
    result["핵심기술"] = "가상 CXL IP [DIR-C01-01]"
    result["성능지표"][0].update(지표명="data rate", 값=value, 측정조건="CXL 4.0 PAM4")
    result["기준대조"][0].update(지표명="data rate", 업계기준=baseline)
    result["_검증"] = {"수치근거": [
        {"경로": "제품성숙도.TRL", "근거ID": "DIR-C01-01", "원문구절": company_quote},
        {"경로": "성능지표.0.값", "근거ID": "DIR-C01-01", "원문구절": company_quote},
        {"경로": "기준대조.0.업계기준", "근거ID": "TEC-02-0001", "원문구절": text},
    ], "기술비교": [{"지표명": "data rate", "조건": [
        {"항목": "프로토콜", "기업조건": "CXL 4.0", "기준조건": "CXL 4.0"},
        {"항목": "신호방식", "기업조건": "PAM4", "기준조건": None},
    ]}]}
    return state, result


@pytest.mark.parametrize("claimed", ["128 GT/s", "768 GB/s", "768 GT/s"])
def test_real_cxl_caption_preserves_units(monkeypatch, claimed):
    text = EXCERPTS["cxl"]["text"]
    state, result = interface_result(text, baseline=claimed)
    doc = document(domain="interface", text=text)
    doc.metadata["source_page"] = EXCERPTS["cxl"]["source_page"]
    analysis = evaluate_tech(monkeypatch, result, state, doc)
    if claimed == "768 GT/s":
        assert analysis["기준대조"][0]["업계기준"] == "확인 불가"
    else:
        assert analysis["기준대조"][0]["업계기준"] == claimed
    # PAM4는 이 캡션에 없으므로 문서 다른 쪽을 추정해서 비교하지 않는다.
    assert analysis["기준대조"][0]["비교결과"] == "비교불가"


def test_real_ucie_number_is_not_a_cxl_reference(monkeypatch):
    text = EXCERPTS["ucie"]["text"]
    state, result = interface_result(text, baseline="64 GT/s")
    result["_검증"]["기술비교"][0]["조건"][0]["기준조건"] = "UCIe 3.0"
    analysis = evaluate_tech(monkeypatch, result, state, document(domain="interface", text=text))
    assert analysis["기준대조"][0]["업계기준"] == "64 GT/s"
    assert analysis["기준대조"][0]["비교결과"] == "비교불가"


def test_irds_scaling_factor_is_not_absolute_tops_per_w(monkeypatch):
    text = EXCERPTS["irds"]["text"]
    result = tech_output()
    result["기준대조"][0]["업계기준"] = "2.0 TOPS/W"
    result["_검증"]["수치근거"][2]["원문구절"] = text
    analysis = evaluate_tech(monkeypatch, result, doc=document(text=text))
    assert analysis["기준대조"][0]["업계기준"] == "확인 불가"
    assert analysis["기준대조"][0]["비교결과"] == "비교불가"


def test_yield_document_does_not_supply_detection_accuracy(monkeypatch):
    text = EXCERPTS["yield"]["text"]
    state = company_state(domain="yield", item="가상 AI 결함 검사")
    quote = "가상 결함 검사 시제품: TRL 6. 정확도 98% 자체 발표."
    state["current_evidence"][0]["원문발췌"] = quote
    result = tech_output()
    result["핵심기술"] = "가상 AI 결함 검사 [DIR-C01-01]"
    result["성능지표"][0].update(지표명="검출 정확도", 값="98%", 측정조건="확인 불가")
    result["기준대조"][0].update(지표명="검출 정확도", 업계기준="99%")
    result["_검증"]["수치근거"] = [
        {"경로": "제품성숙도.TRL", "근거ID": "DIR-C01-01", "원문구절": quote},
        {"경로": "성능지표.0.값", "근거ID": "DIR-C01-01", "원문구절": quote},
        {"경로": "기준대조.0.업계기준", "근거ID": "TEC-02-0001", "원문구절": text},
    ]
    analysis = evaluate_tech(monkeypatch, result, state, document(domain="yield", text=text))
    assert analysis["성능지표"][0]["값"] == "98%"
    assert analysis["기준대조"][0]["업계기준"] == "확인 불가"
    assert analysis["근거충분"] is False


def test_wsts_total_market_cannot_be_npu_direct_market(monkeypatch):
    text = EXCERPTS["wsts"]["text"]
    result = market_output()
    result["시장규모"].update(값="USD 1.51 trillion 전망", 기준연도=2026)
    result["성장률"].update(값="90 percent 전년대비 전망", 기간="2026")
    for support in result["_검증"]["수치근거"]:
        support["원문구절"] = text
    for audit in result["_검증"]["시장검증"]:
        audit.update(수치유형="전망", 성장유형="전년대비" if audit["항목"] == "성장률" else "해당없음")
    analysis = evaluate_market(monkeypatch, result, doc=document("market", text=text))
    assert analysis["시장규모"]["값"] == "확인 불가" and analysis["성장률"]["값"] == "확인 불가"
    assert analysis["근거충분"] is False


@pytest.mark.parametrize("scope", ["상위시장", "확인불가"])
def test_background_market_is_not_direct_market(monkeypatch, scope):
    result = market_output()
    for audit in result["_검증"]["시장검증"]:
        audit["범위"] = scope
    assert evaluate_market(monkeypatch, result)["시장규모"]["값"] == "확인 불가"


def test_yoy_cannot_be_relabelled_as_cagr(monkeypatch):
    text = "Global edge NPU market: 2025 USD 1 billion, projected to grow 10 percent year over year in 2026."
    result = market_output()
    result["시장규모"]["값"] = "USD 1 billion 전망"
    result["성장률"].update(값="CAGR 10% 전망", 기간="2026")
    for support in result["_검증"]["수치근거"]:
        support["원문구절"] = text
    for audit in result["_검증"]["시장검증"]:
        audit["수치유형"] = "전망"
    analysis = evaluate_market(monkeypatch, result, doc=document("market", text=text))
    assert analysis["시장규모"]["값"] != "확인 불가"
    assert analysis["성장률"]["값"] == "확인 불가"


def test_unlabelled_forecast_is_not_an_actual_result(monkeypatch):
    text = MARKET_TEXT.replace("2025 USD", "projected 2025 USD")
    result = market_output()
    for support in result["_검증"]["수치근거"]:
        support["원문구절"] = text
    assert evaluate_market(monkeypatch, result, doc=document("market", text=text))["시장규모"]["값"] == "확인 불가"


@pytest.mark.parametrize("published", [2027, "2026-10-01"])
def test_future_publication_is_filtered_before_generation(monkeypatch, published):
    doc = document("market")
    doc.metadata["pub_year"] = published
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *args, **kwargs: [doc])
    monkeypatch.setattr(rag, "generate_analysis", lambda *args: pytest.fail("조사 시점 이후 자료 사용"))
    update = market.run(company_state())
    assert update["current_evidence"] == [] and update["market_analysis"]["근거충분"] is False


def test_future_forecast_year_in_past_publication_is_allowed(monkeypatch):
    text = "Global edge NPU market: forecast 2027 USD 1 billion, 2025-2030 CAGR 10%."
    result = market_output()
    result["시장규모"].update(값="USD 1 billion 전망", 기준연도=2027)
    result["성장률"]["값"] = "CAGR 10% 전망"
    for support in result["_검증"]["수치근거"]:
        support["원문구절"] = text
    for audit in result["_검증"]["시장검증"]:
        audit["수치유형"] = "전망"
    analysis = evaluate_market(monkeypatch, result, doc=document("market", text=text))
    assert analysis["시장규모"]["기준연도"] == 2027 and analysis["근거충분"] is True


def test_full_previous_text_survives_disjoint_retry_with_disk_cache(monkeypatch):
    text = "일반 설명 " * 70 + TECH_TEXT
    first = document(text=text)
    docs = [[first], []]
    payloads = []
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *args, **kwargs: docs.pop(0))

    def generate(stage, payload):
        payloads.append(deepcopy(payload))
        return tech_output(enough=len(payloads) == 2)

    monkeypatch.setattr(rag, "generate_analysis", generate)
    state = company_state()
    initial = technology.run(state)
    assert "10 TOPS/W" not in initial["current_evidence"][0]["원문발췌"]
    retry = technology.run(apply_update(state, initial))
    old = [e for e in payloads[1]["기존근거"] if e["근거ID"] == "TEC-02-0001"][0]
    assert old["검색원문"] == text
    assert retry["technology_analysis"]["근거충분"] is True
    assert retry["current_evidence"] == []
    assert set(initial["current_evidence"][0]) == {
        "근거ID", "출처명", "publisher", "pub_year", "source_type", "url", "source_page", "확인일", "원문발췌", "chunk_id",
    }


def test_actual_excerpt_original_page_mapping():
    assert EXCERPTS["irds"]["source_page"] == 7
    assert EXCERPTS["yield"]["source_page"] == 29
    assert all(len(e["text"]) <= 700 for e in EXCERPTS.values())


@pytest.mark.parametrize("item,expected,unrelated", [
    ("가상 CXL 메모리 IP", "Bundled Ports", "UCIe"),
    ("가상 UCIe 칩렛 IP", "Advanced Package", "CXL"),
])
def test_interface_query_targets_the_products_protocol(item, expected, unrelated):
    query = rag.build_query(company_state(domain="interface", item=item), "technology")
    assert expected in query and unrelated not in query


def test_evidence_ids_are_not_market_search_keywords():
    state = company_state()
    state["technology_analysis"] = {"핵심기술": "엣지 NPU [DIR-C01-01]"}
    query = rag.build_query(state, "market")
    assert "DIR-C01-01" not in query and "NPU" in query
