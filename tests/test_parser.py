"""레인 A: 변환 규칙 + 파이프라인 (LLM은 가짜로 대체, API 키 불필요)."""

import pytest

from rag import parser
from rag.parser import CompanyExtract, IPItem, Investment, RevenueCell, money, normalize_stage, revenue, to_date


def test_money_units():
    assert money("169,569천원") == (169569, "공개")
    assert money("3,000,000천원(협의 중)") == (3000000, "공개")
    assert money("11.2억") == (1120000, "공개")
    assert money("N/A") == (None, "N/A")
    assert money("비공개") == (None, "비공개")
    assert money("") == (None, "확인불가")


def test_stage_normalization():
    assert normalize_stage("Seed Round") == "Seed"
    assert normalize_stage("Angel") == "Seed"
    assert normalize_stage("Pre A") == "Seed"          # 직전 단계
    assert normalize_stage("Pre B") == "Series A"
    assert normalize_stage("Series A-Bridge") == "Series A"
    assert normalize_stage("Series A(SAFE)") == "Series A"
    assert normalize_stage("Series A,B") == "Series B"
    assert normalize_stage("벤처투자") == "확인불가"


def test_date_and_revenue():
    assert to_date("2021년 5월 25일") == "2021-05-25"
    rev = revenue([RevenueCell(year=2023, region="국내", raw="169,569천원"),
                   RevenueCell(year=2024, region="국내", raw="565,800천원"),
                   RevenueCell(year=2024, region="해외", raw="N/A")])
    assert (rev["연도"], rev["국내"], rev["해외"], rev["상태"]) == (2024, 565800, None, "공개")
    assert revenue([RevenueCell(year=2024, region="국내", raw="N/A")])["상태"] == "N/A"


def _fake_extract(text: str) -> CompanyExtract:
    return CompanyExtract(
        name=text.splitlines()[1], homepage="", founded="2021년 5월 25일", ceo="홍길동", employees="13명",
        industry="", tech_field="", main_item="AI 검사", members=[],
        revenue=[RevenueCell(year=2024, region="국내", raw="565,800천원")], customers=["① 제너셈"],
        investments=[Investment(year="2025", investors="복수 VC", stage="Pre A", amount_raw="3,000,000천원(협의 중)")],
        ip=[IPItem(kind="출원", number="10-2024-0153586", title="품질검사", date="2024.11")],
        awards=[], dev_progress="", trl=None, innovation="", business_point="", headline="", sub_domain="yield",
    )


class _FakeLLM:
    def batch(self, inputs, config=None, return_exceptions=False):
        return [_fake_extract(msgs[1][1][0]["text"]) for msgs in inputs]


def test_parse_company_pages_real_pdf(monkeypatch):
    pdf = parser.DATA_DIR / "raw" / "01_기업정보.pdf"
    if not pdf.exists():
        pytest.skip("data/raw/01_기업정보.pdf 없음")
    monkeypatch.setattr(parser, "_llm", lambda: _FakeLLM())
    monkeypatch.setattr(parser, "classify_sub_domains", lambda records: records)
    records = parser.parse_company_pages(pdf)
    assert len(records) == 45                                  # 47쪽 - 이미지 전용 16·20쪽
    first, last = records[0], records[-1]
    assert (first["company_id"], first["기업명"]) == ("C01", "디에스 주식회사")
    assert (last["company_id"], last["기업명"]) == ("C45", "하이퍼비주얼에이아이")
    assert first["source_page"] == 6 and first["인쇄페이지"] == "010-011"
    assert first["투자유치이력"][0]["확정"] is False           # '협의 중'은 미확정
    assert "[오른쪽 페이지]" in first["원문"] and "사업 Point" in first["원문"]
