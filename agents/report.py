"""⑦ 보고서 생성 에이전트 — State만 사용 (신규 검색 금지). SUMMARY + 1~3장 + REFERENCE, 5장 이내."""

import json

from pydantic import BaseModel

from agents._report_llm import load_prompt, structured_call
from agents._report_render import (
    MAX_REPORT_CHARS,
    build_reference,
    candidate_status,
    candidate_summary_table,
    checklist_table,
    company_info_table,
    decision_sentence,
    eligibility_table,
    limitations,
    scope_sentence,
    scorecard_tables,
    strip_invalid_ids,
)
from state import State


class ReportProse(BaseModel):
    summary: str
    idea: str = ""
    team: str = ""
    tech: str = ""
    market: str = ""
    competition: str = ""
    risks: str


def _evidence_of(rec: dict) -> list[dict]:
    return rec.get("current_evidence") or []


def _all_evidence(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in records:
        for e in _evidence_of(r):
            seen.setdefault(e["근거ID"], e)
    return list(seen.values())


def _prose(mode: str, payload: dict, evidence: list[dict]) -> tuple[ReportProse, list[str]]:
    """LLM 서술 생성 후 유효하지 않은 근거 ID를 제거한다. 반환: (서술, 제거된 ID)."""
    user = json.dumps({"mode": mode, **payload,
                       "사용 가능한 근거ID": [e["근거ID"] for e in evidence if e.get("근거ID")]},
                      ensure_ascii=False, default=str)
    prose = structured_call(ReportProse, load_prompt("report"), user)
    valid = {e["근거ID"] for e in evidence if e.get("근거ID")}
    removed: list[str] = []
    cleaned = {}
    for k, v in prose.model_dump().items():
        cleaned[k], r = strip_invalid_ids(v, valid)
        removed += r
    return ReportProse(**cleaned), removed


def _or_unknown(text: str) -> str:
    return text.strip() or "확인 불가"


def _selected_report(state: State, records: list[dict], by_id: dict[str, dict]) -> str:
    rec = by_id[state["selected_company_id"]]
    company, sc = rec["current_company"], rec["scorecard"]
    dir_ids = [e["근거ID"] for e in _evidence_of(rec) if e["근거ID"].startswith("DIR-")]
    payload = {
        "기업": company, "적격성": rec.get("eligibility"), "기술분석": rec.get("technology_analysis"),
        "시장분석": rec.get("market_analysis"), "경쟁분석": rec.get("competitor_analysis"),
        "체크리스트": rec.get("checklist"), "스코어카드": sc, "판정": rec["decision"],
        "판단상세": rec.get("decision_details"), "순위": state.get("ranking"),
        "투자적격 수": len(state.get("ranking") or []),
    }
    prose, _ = _prose("selected", payload, _evidence_of(rec))
    cl_table, cl_warn = checklist_table(rec.get("checklist") or {})
    n_ok = len(state.get("ranking") or [])
    head = (f"**투자 추천: {company['기업명']}** (투자 적격 {n_ok}곳 중 1위, 총점 {sc['total']}점). "
            f"{scope_sentence(state, records)}")
    sections = [
        f"# 투자 평가 보고서: {company['기업명']}",
        f"## SUMMARY\n\n{head}\n\n{_or_unknown(prose.summary)}",
        "## 1. 기업 개요",
        f"### 1.1 기업 정보\n\n{company_info_table(company, dir_ids)}",
        f"### 1.2 사업 아이디어\n\n{_or_unknown(prose.idea)}",
        f"### 1.3 팀 구성\n\n{_or_unknown(prose.team)}",
        "## 2. 기술·시장·경쟁 분석",
        f"### 2.1 기술력\n\n{_or_unknown(prose.tech)}",
        f"### 2.2 시장성\n\n{_or_unknown(prose.market)}",
        f"### 2.3 경쟁 구도\n\n{_or_unknown(prose.competition)}",
        "## 3. 투자 판단",
        f"### 3.1 평가 범위 및 후보 현황\n\n{candidate_status(state, records, by_id)}",
        f"### 3.2 평가 결과\n\n**자격 요건**\n\n{eligibility_table(rec['eligibility'])}\n\n**체크리스트** "
        f"(판정에는 미반영, 스코어카드 근거 확인용)\n\n{cl_table}\n\n**스코어카드**\n\n{scorecard_tables(sc)}\n\n{decision_sentence(rec)}",
        f"### 3.3 사업 리스크\n\n{_or_unknown(prose.risks)}",
        f"### 3.4 한계점\n\n{limitations(state, rec, cl_warn)}",
    ]
    return "\n\n".join(sections), _evidence_of(rec)


def _no_selection_report(state: State, records: list[dict], by_id: dict[str, dict]) -> tuple[str, list[dict]]:
    payload = {"후보요약": [{"기업": r["current_company"]["기업명"], "판정": r["decision"],
                          "총점": (r.get("scorecard") or {}).get("total"), "사유": r.get("route_reason"),
                          "판단상세": r.get("decision_details")} for r in records if r.get("current_company")][:20]}
    evidence = _all_evidence(records)
    prose, _ = _prose("no_selection", payload, evidence)
    head = f"**투자 대상 없음.** {scope_sentence(state, records)}"
    sections = [
        "# 투자 평가 보고서: 투자 대상 없음",
        f"## SUMMARY\n\n{head}\n\n{_or_unknown(prose.summary)}",
        f"## 1~2. 후보별 평가 요약\n\n{candidate_summary_table(records)}",
        "## 3. 투자 판단",
        f"### 3.1 평가 범위 및 후보 현황\n\n{candidate_status(state, records, by_id)}",
        f"### 3.2 평가 결과\n\n투자 적격 판정을 받은 기업이 없다. 후보별 판정과 총점은 위 요약표에 정리했다.",
        f"### 3.3 사업 리스크\n\n{_or_unknown(prose.risks)}",
        f"### 3.4 한계점\n\n{limitations(state, None, [])}",
    ]
    return "\n\n".join(sections), evidence


def run(state: State) -> dict:
    """
    입력: evaluation_results, selected_company_id, ranking, source_document, as_of_date
    처리: selected_company_id가 있으면 evaluation_results에서 그 기업 레코드를 찾아 보고서 작성,
          없으면 '후보별 평가 요약' 구성 (설계: 투자 보고서 › 4)
          ※ State의 current_company·current_evidence 등은 마지막 후보 값이므로 사용하지 않는다
          3.1에 ranking 2·3위와 미선정 사유 요약
          REFERENCE는 본문에서 실제 인용한 근거 ID만, 레코드의 current_evidence에서 source_type별 가이드 표기 형식으로 생성
    출력: {"final_report": str (markdown)}
    """
    records = state.get("evaluation_results") or []
    by_id = {r["company_id"]: r for r in records}
    selected = state.get("selected_company_id")
    if selected and selected not in by_id:
        raise KeyError(f"selected_company_id {selected!r} 가 evaluation_results에 없음")

    body, evidence = (_selected_report if selected else _no_selection_report)(state, records, by_id)
    report = f"{body}\n\n## REFERENCE\n\n{build_reference(body, evidence)}"
    if len(report) > MAX_REPORT_CHARS:
        report += f"\n\n<!-- 경고: {len(report):,}자 (5장 추정 상한 {MAX_REPORT_CHARS:,}자 초과) -->"
    return {"final_report": report}
