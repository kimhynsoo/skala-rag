import pytest
from agents._report_scoring import score_e2, score_e3


@pytest.mark.parametrize("revenue", [
    {"상태": "확인불가", "국내": None, "해외": None},
    {"상태": "공개", "국내": None, "해외": 4_107_122, "해외단위": "USD"},
])
def test_unconvertible_or_unknown_revenue_is_unknown(revenue):
    result = score_e2({"매출액": revenue})
    assert result[:2] == (2, True)


def test_undisclosed_confirmed_investment_is_unknown():
    history = [{"금액": None, "확정": True, "투자자": ["Fund"]}]
    result = score_e3({"투자유치이력": history})
    assert result[:2] == (2, True)


def test_report_visuals_do_not_assume_exchange_rate():
    from agents._report_highlights import revenue_eok
    from agents._report_charts import revenue_chart

    sales = {"상태": "공개", "해외": 100_000, "해외단위": "USD"}
    assert revenue_eok(sales) is None
    assert "환산 근거" in revenue_chart({"매출액": sales})
