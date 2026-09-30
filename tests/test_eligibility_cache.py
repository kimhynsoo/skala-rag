import pytest
from tools.eligibility_cache import cache_is_current, company_hash


@pytest.mark.parametrize("completed,expected", [
    ("2026-09-30T01:00:00+00:00", True),
    ("2026-09-16T01:00:00+00:00", True),
    ("2026-09-15T01:00:00+00:00", False),
    ("2026-10-01T01:00:00+00:00", False),
    ("", False),
])
def test_external_verification_age_is_checked(completed, expected):
    assert cache_is_current(completed, "2026-09-30") is expected


def test_eligibility_rejects_changed_company_cache(monkeypatch):
    from agents import eligibility

    company = {"company_id": "C01", "기업명": "Chip", "메인아이템": "NPU"}
    old_company = company | {"메인아이템": "Power"}
    row = {"company_hash": company_hash(old_company), "completed_at": "2026-09-30",
           "criteria": {key: {"결과": "충족", "사유": "cached", "근거ID": []} for key in ("G1", "G2", "G3")}}
    monkeypatch.setattr(eligibility, "_read_external_result", lambda cid: row)
    monkeypatch.setattr(eligibility, "_read_g4_result", lambda cid: None)
    result = eligibility.run({"current_company": company, "as_of_date": "2026-09-30"})
    assert result["eligibility"]["G1"]["결과"] == "확인불가"
    assert result["eligibility"]["판정"] == "확인필요"
