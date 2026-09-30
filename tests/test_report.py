import pytest

from agents import report
from agents._report_render import (
    MAX_REPORT_CHARS,
    build_reference,
    format_reference,
    not_selected_reason,
    strip_invalid_ids,
)
from agents.report import ReportProse
from tests.fixtures.fake_results import evidence, fake_results


def _fake_llm(monkeypatch, **over):
    prose = dict(
        summary="총점이 높고 기술력이 우수하다 [TEC-C07-01]. 시장 성장이 크다 [MKT-C07-01, TEC-C99-01].",
        idea="엣지 NPU로 전력 문제를 해결한다 [DIR-C07-01].",
        team="CEO는 박사다 [DIR-C07-01].",
        tech="TOPS/W 12 (자체 발표) [DIR-C07-01].",
        market="CAGR 25% [MKT-C07-01].",
        competition="Hailo 대비 우위 [CMP-C07-01].",
        risks="- 양산 이력 없음 [DIR-C07-01]",
    ) | over
    monkeypatch.setattr(report, "structured_call", lambda *a, **k: ReportProse(**prose))
    monkeypatch.setattr(report, "load_prompt", lambda n: "p")


def _state(**over):
    results = fake_results()
    s = {
        "evaluation_results": results, "selected_company_id": "C07", "ranking": ["C07", "C03"],
        "source_document": "2025 초격차 스타트업 1000+ 디렉토리북", "as_of_date": "2026-09-30", "errors": [],
        # 마지막 후보 값이 남아 있는 상황을 흉내: 보고서가 이걸 쓰면 안 된다
        "current_company": results[-1]["current_company"], "current_evidence": results[-1]["current_evidence"],
    }
    return s | over


def test_selected_report_structure(monkeypatch):
    _fake_llm(monkeypatch)
    text = report.run(_state())["final_report"]
    for h in ["## SUMMARY", "## 1. 기업 개요", "### 1.1", "### 1.2", "### 1.3", "## 2.", "### 2.1", "### 2.2", "### 2.3",
              "## 3. 투자 판단", "### 3.1", "### 3.2", "### 3.3", "### 3.4", "## REFERENCE"]:
        assert h in text, h
    assert text.index("## SUMMARY") < text.index("## 1.") < text.index("## REFERENCE")
    assert "베타실리콘" in text and "감마반도체" not in text.split("## REFERENCE")[0].split("### 3.1")[0]  # 선정 기업(C07)
    assert len(text) <= MAX_REPORT_CHARS


def test_uses_selected_record_not_current_fields(monkeypatch):
    _fake_llm(monkeypatch)
    text = report.run(_state())["final_report"]
    assert "감마반도체" not in text.split("### 3.1")[0]  # current_company(마지막 후보 C09)가 섞이지 않음
    assert "DIR-C09" not in text


def test_reference_only_cited_and_invalid_ids_stripped(monkeypatch):
    _fake_llm(monkeypatch)
    text = report.run(_state())["final_report"]
    body, ref = text.split("## REFERENCE")
    assert "TEC-C99-01" not in body  # 존재하지 않는 근거 ID는 본문에서 제거
    assert "TEC-C07-01" in ref and "WSTS" in ref and "Hailo" in ref
    # 인용되지 않은 근거는 REFERENCE에 없다: 이 픽스처의 ELG는 3.2 표에서 인용되므로 포함, 다른 기업 것은 제외
    assert "C03-" not in ref and "C09-" not in ref


def test_unknown_evidence_not_in_reference():
    ev = [evidence("TEC", "C01"), evidence("MKT", "C01", 출처명="사용되지 않음", publisher="X")]
    ref = build_reference("본문 [TEC-C01-01] 만 인용", ev)
    assert "IEEE(2024)" in ref and "사용되지 않음" not in ref


def test_reference_formats_by_source_type():
    org = format_reference(evidence("TEC", "C1"))
    assert org == "IEEE(2024). IRDS 2024 More Moore. https://irds.ieee.org/"
    web = format_reference(evidence("CMP", "C1", source_type="웹페이지", publisher="Hailo", pub_year="2026-08-01",
                                    출처명="Hailo-8", url="https://hailo.ai/p"))
    assert web == "Hailo(2026-08-01). Hailo-8. hailo.ai, https://hailo.ai/p"
    paper = format_reference(evidence("TEC", "C1", source_type="학술 논문", publisher="Kim", pub_year=2023, 출처명="논문", source_page="12-20"))
    assert paper == "Kim(2023). 논문, 12-20."


def test_strip_invalid_ids_cleans_brackets():
    valid = {"TEC-C01-01"}
    assert strip_invalid_ids("값 [TEC-C01-01, TEC-C09-01].", valid)[0] == "값 [TEC-C01-01]."
    assert strip_invalid_ids("값 [TEC-C09-01].", valid) == ("값 .", ["TEC-C09-01"])


def test_not_selected_reason_follows_rank_order():
    a, b = fake_results()[1], fake_results()[0]  # C07(총점 높음) vs C03
    assert "총점" in not_selected_reason(a, b) and "낮음" in not_selected_reason(a, b)
    import copy
    c = copy.deepcopy(a)
    c["scorecard"]["averages"]["제품/기술력"] = 3.0
    assert "기술력" in not_selected_reason(a, c)  # 총점 동점이면 기술력 비교로 넘어감


def test_status_lists_second_place_with_reason(monkeypatch):
    _fake_llm(monkeypatch)
    text = report.run(_state())["final_report"]
    sec = text.split("### 3.1")[1].split("### 3.2")[0]
    assert "알파칩스" in sec and "낮음" in sec  # 2위 + 미선정 사유


def test_no_selection_report(monkeypatch):
    _fake_llm(monkeypatch, summary="투자 대상 없음. 보류 사유는 기술력 부족이다.", risks="- 공통 약점")
    results = fake_results()
    for r in results:
        r["decision"] = "보류"
    text = report.run(_state(evaluation_results=results, selected_company_id=None, ranking=[]))["final_report"]
    assert "투자 대상 없음" in text and "## 1~2. 후보별 평가 요약" in text
    assert "### 3.1" in text and "### 3.3" in text and "### 3.4" in text and "## REFERENCE" in text
    assert "### 1.1" not in text


def test_missing_selected_record_raises(monkeypatch):
    _fake_llm(monkeypatch)
    with pytest.raises(KeyError):
        report.run(_state(selected_company_id="C99"))


def test_empty_prose_becomes_unknown_not_invented(monkeypatch):
    _fake_llm(monkeypatch, tech="")
    text = report.run(_state())["final_report"]
    assert "### 2.1 기술력\n\n확인 불가" in text


def test_hold_reason_is_not_eligibility_text(monkeypatch):
    """점수 미달 보류 기업의 사유로 'G1~G4 모두 충족'이 나오면 오해를 부른다."""
    _fake_llm(monkeypatch)
    text = report.run(_state())["final_report"]
    line = [ln for ln in text.splitlines() if ln.startswith("제외·보류 주요 사유")][0]
    assert "모두 충족" not in line and "기술력 우수" in line
