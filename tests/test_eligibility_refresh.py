"""실행 시 적격성 입력 준비: 캐시가 유효하면 재조사하지 않고, 없거나 만료되면 그때만 외부 조사를 실행한다."""

import json

import pytest

from agents import eligibility
from tools import g4_screening, run_tavily_eligibility
from tools.eligibility_cache import company_hash

COMPANIES = [{"company_id": "C01", "기업명": "가상"}, {"company_id": "C02", "기업명": "가상2"}]


@pytest.fixture
def paths(tmp_path, monkeypatch):
    companies = tmp_path / "companies.json"
    companies.write_text(json.dumps(COMPANIES, ensure_ascii=False), encoding="utf-8")
    g4 = tmp_path / "g4.json"
    g4.write_text(json.dumps({"results": [
        {"company_id": c["company_id"], "판정": "통과" if c["company_id"] == "C01" else "불통과",
         "company_hash": company_hash(c)} for c in COMPANIES]}, ensure_ascii=False), encoding="utf-8")
    ext = tmp_path / "ext.json"
    monkeypatch.setattr(eligibility, "COMPANIES_PATH", companies)
    monkeypatch.setattr(eligibility, "G4_RESULTS_PATH", g4)
    monkeypatch.setattr(eligibility, "EXTERNAL_RESULTS_PATH", ext)
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    calls = []
    monkeypatch.setattr(g4_screening, "screen", lambda *a, **k: calls.append("g4"))
    monkeypatch.setattr(run_tavily_eligibility, "refresh", lambda as_of_date, **k: calls.append(("ext", as_of_date)))
    return ext, calls


def _write_ext(ext, completed_at):
    ext.write_text(json.dumps({"results": [{"company_id": "C01", "completed_at": completed_at,
                                            "company_hash": company_hash(COMPANIES[0])}]}), encoding="utf-8")


def test_fresh_cache_skips_external_search(paths):
    ext, calls = paths
    _write_ext(ext, "2026-09-30T05:00:00+00:00")
    eligibility.ensure_external_inputs("2026-10-13")
    assert calls == []  # G4·외부 조사 모두 유효 → API 호출 없음


def test_expired_or_missing_cache_triggers_refresh(paths):
    ext, calls = paths
    _write_ext(ext, "2026-09-30T05:00:00+00:00")
    eligibility.ensure_external_inputs("2026-10-20")  # 20일 경과 → 만료
    assert calls == [("ext", "2026-10-20")]
    ext.unlink()
    calls.clear()
    eligibility.ensure_external_inputs("2026-10-13")  # 파일 없음
    assert calls == [("ext", "2026-10-13")]


def test_missing_g4_runs_screen_first(paths, monkeypatch, tmp_path):
    ext, calls = paths
    monkeypatch.setattr(eligibility, "G4_RESULTS_PATH", tmp_path / "none.json")
    eligibility.ensure_external_inputs("2026-10-13")
    assert calls[0] == "g4"


def test_no_tavily_key_warns_without_search(paths, monkeypatch, capsys):
    ext, calls = paths
    monkeypatch.delenv("TAVILY_API_KEY")
    eligibility.ensure_external_inputs("2026-10-13")
    assert calls == [] and "TAVILY_API_KEY" in capsys.readouterr().out
