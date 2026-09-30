"""⑦ 보고서 보조: 코드로 만드는 결정적 섹션(표·점수·후보 현황·한계점), 인용 검증, REFERENCE 생성."""

import re
from collections import Counter
from urllib.parse import urlparse

from agents.investment import rank_key
from config import INVEST_THRESHOLD, TECH_MIN, WEIGHTS

QUESTIONS = {
    "Q1": "목표 시장이 구체적인가?", "Q2": "구체적인 문제를 해결하는가?", "Q3": "고객이 구매할 이유가 있는가?",
    "Q4": "차별성이 있는가?", "Q5": "주요 구성원을 신뢰할 수 있는가?", "Q6": "초기 고객이 있는가?",
    "Q7": "매출이 발생하는가?", "Q8": "글로벌 기회가 있는가?", "Q9": "창업자가 분야에 꾸준히 몸담아 왔는가?",
    "Q10": "개발이 어디까지 진행됐는가?", "Q11": "외부에서 검증받았는가?",
}
ITEM_NAMES = {
    "A1": "기술 전문성", "A2": "팀 완성도", "A3": "분야 몰입도", "B1": "시장 규모·성장성", "B2": "고객 가치",
    "B3": "글로벌 확장성", "C1": "문제 해결력", "C2": "개발 성숙도", "C3": "분야별 핵심 기술 지표",
    "D1": "지식재산", "D2": "경쟁사 대비 차별성", "D3": "외부 검증", "E1": "고객 확보", "E2": "매출", "E3": "투자 유치",
}

MAX_REPORT_CHARS = 12_000  # 5장(SUMMARY·REFERENCE 포함) 추정 상한. 최종 PDF에서 페이지 수로 재확인한다.

ID_RE = re.compile(r"\b(?:DIR|ELG|TEC|MKT|CMP)-[A-Za-z0-9]+-\d{2}\b")


# ── 인용 검증 ──────────────────────────────────────────────────────────────

def strip_invalid_ids(text: str, valid: set[str]) -> tuple[str, list[str]]:
    """본문에서 유효하지 않은 근거 ID를 제거한다. 반환: (정리된 본문, 제거된 ID 목록)."""
    removed: list[str] = []

    def repl(m: re.Match) -> str:
        if m.group(0) in valid:
            return m.group(0)
        removed.append(m.group(0))
        return ""

    out = ID_RE.sub(repl, text)
    out = re.sub(r"\[[\s,]*\]", "", out)  # 빈 대괄호
    out = re.sub(r"\[\s*,\s*", "[", out)
    out = re.sub(r"\s*,\s*\]", "]", out)
    return out, removed


def cited_ids(body: str) -> list[str]:
    seen: list[str] = []
    for i in ID_RE.findall(body):
        if i not in seen:
            seen.append(i)
    return seen


def cite(ids: list[str]) -> str:
    return "[" + ", ".join(ids) + "]" if ids else ""


# ── REFERENCE ──────────────────────────────────────────────────────────────

def format_reference(e: dict) -> str:
    """가이드 표기 형식 3종. source_type별로 사용 필드가 다르다."""
    pub, year, title = e.get("publisher") or "", e.get("pub_year") or "n.d.", e.get("출처명") or e.get("title") or ""
    url = e.get("url")
    kind = e.get("source_type")
    if kind == "학술 논문":
        page = f", {e['source_page']}." if e.get("source_page") else "."
        return f"{pub}({year}). {title}{page}"
    if kind == "웹페이지":
        site = urlparse(url).netloc if url else pub
        return f"{pub}({year}). {title}. {site}" + (f", {url}" if url else "")
    return f"{pub}({year}). {title}." + (f" {url}" if url else "")


def build_reference(body: str, evidence: list[dict]) -> str:
    """본문에서 실제 인용된 근거 ID의 출처만. 같은 출처(표기 동일)는 한 줄로 합치고 ID를 병기한다."""
    by_id = {e["근거ID"]: e for e in evidence if e.get("근거ID")}
    grouped: dict[str, list[str]] = {}
    for i in cited_ids(body):
        if i in by_id:
            grouped.setdefault(format_reference(by_id[i]), []).append(i)
    lines = [f"{n}. {ref} — {cite(ids)}" for n, (ref, ids) in enumerate(grouped.items(), 1)]
    return "\n".join(lines) if lines else "인용된 근거가 없습니다."


# ── 공통 표 헬퍼 ───────────────────────────────────────────────────────────

def md_table(header: list[str], rows: list[list]) -> str:
    esc = lambda v: str(v).replace("|", "/").replace("\n", " ")  # noqa: E731
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


# ── 1.1 기업 정보 ──────────────────────────────────────────────────────────

def latest_round(company: dict) -> str:
    confirmed = [h for h in company.get("투자유치이력") or [] if h.get("확정", True)]
    if not confirmed:
        return "확인 불가"
    last = max(confirmed, key=lambda h: h.get("일자") or "")
    return f"{last.get('단계') or '단계 미상'} ({last.get('일자') or '일자 미상'})"


def company_info_table(company: dict, dir_ids: list[str]) -> str:
    rows = [
        ["설립일", company.get("설립일") or "확인 불가"],
        ["직원 수", f"{company['직원수']}명" if company.get("직원수") is not None else "확인 불가"],
        ["대표자", company.get("대표자명") or "확인 불가"],
        ["업종 / 기술분야", f"{company.get('업종') or '-'} / {company.get('기술분야') or '-'}"],
        ["최신 투자 단계", latest_round(company)],
        ["메인 아이템", company.get("메인아이템") or "확인 불가"],
    ]
    return md_table(["항목", f"내용 {cite(dir_ids)}".strip()], rows)


# ── 3.1 평가 범위 및 후보 현황 ─────────────────────────────────────────────

def not_selected_reason(top: dict, other: dict) -> str:
    """1위와 순위 규칙(총점 → 기술력 → 확인 불가 수 → 실적)을 차례로 비교해 미선정 사유를 만든다."""
    a, b = rank_key(top), rank_key(other)
    ta, tb = top["scorecard"], other["scorecard"]
    if a[0] != b[0]:
        return f"총점 {tb['total']}점으로 1위({ta['total']}점)보다 {ta['total'] - tb['total']:.1f}점 낮음"
    if a[1] != b[1]:
        return f"총점 동점, 제품/기술력 {tb['averages']['제품/기술력']:.2f} < 1위 {ta['averages']['제품/기술력']:.2f}"
    if a[2] != b[2]:
        return f"총점·기술력 동점, 확인 불가 항목 {len(tb.get('unknown_items', []))}건 > 1위 {len(ta.get('unknown_items', []))}건"
    return f"앞선 기준 동점, 실적 {tb['averages']['실적']:.2f} < 1위 {ta['averages']['실적']:.2f}"


def _exclusion_reason(r: dict) -> str:
    """제외·보류 사유: 분기 사유 → 자격 요건 미충족 사유(적격이 아닐 때만) → 판단 사유 순."""
    elig = r.get("eligibility") or {}
    eligibility_reason = elig.get("사유") if elig.get("판정") != "적격" else None
    return (r.get("route_reason") or eligibility_reason
            or (r.get("decision_details") or {}).get("판단사유") or "사유 미기재")


def scope_sentence(state: dict, records: list[dict]) -> str:
    c = Counter(r.get("decision") for r in records)
    return (
        f"평가 범위: {state.get('source_document', '디렉토리북')} 수록 후보 {len(records)}개사(조사 기준일 {state.get('as_of_date', '확인 불가')})를 "
        f"평가하여 투자 적격 {c['투자 적격']}곳, 보류 {c['보류']}곳, 제외 {c['제외']}곳으로 판정했다."
    )


def candidate_status(state: dict, records: list[dict], by_id: dict[str, dict]) -> str:
    ranking = [i for i in state.get("ranking") or [] if i in by_id]
    parts = [scope_sentence(state, records)]
    if ranking:
        top = by_id[ranking[0]]
        rows = []
        for n, cid in enumerate(ranking, 1):
            r = by_id[cid]
            note = "투자 추천" if n == 1 else not_selected_reason(top, r)
            rows.append([n, r["current_company"]["기업명"], r["scorecard"]["total"],
                         f"{r['scorecard']['averages']['제품/기술력']:.2f}", len(r["scorecard"].get("unknown_items", [])), note])
        rows = rows[:3]  # 2·3위까지 (보고서 분량)
        parts.append(md_table(["순위", "기업", "총점", "기술력", "확인불가", "비고 / 미선정 사유"], rows))
        if len(ranking) > 3:
            parts.append(f"그 외 투자 적격 {len(ranking) - 3}곳은 분량상 생략했다.")
    others = [r for r in records if r.get("decision") in ("제외", "보류")]
    reasons = Counter(_clip(_exclusion_reason(r), 40) for r in others)
    if reasons:
        parts.append("제외·보류 주요 사유: " + "; ".join(f"{k} ({v}곳)" for k, v in reasons.most_common(5)))
    return "\n\n".join(parts)


def candidate_summary_table(records: list[dict], limit: int = 10) -> str:
    """투자 대상이 없을 때 1~2장을 대체하는 후보별 평가 요약."""
    scored = sorted([r for r in records if r.get("scorecard")], key=lambda r: -r["scorecard"]["total"])[:limit]
    rows = []
    for r in scored:
        sc = r["scorecard"]
        reason = _clip((r.get("decision_details") or {}).get("판단사유") or r.get("route_reason") or "", 50)
        rows.append([r["current_company"]["기업명"], r["decision"], sc["total"], f"{sc['averages']['제품/기술력']:.2f}", reason])
    unscored = len(records) - len(scored)
    tail = f"\n\n점수가 산출된 기업 상위 {len(scored)}곳만 표시했다. 그 외 {unscored}곳은 자격 요건 단계에서 제외되었거나 오류로 채점되지 않았다." if unscored > 0 else ""
    return md_table(["기업", "판정", "총점", "기술력", "핵심 사유"], rows) + tail


# ── 3.2 평가 결과 ──────────────────────────────────────────────────────────

def eligibility_table(elig: dict) -> str:
    rows = [[g, elig.get(g, {}).get("결과", "확인불가"), _clip(elig.get(g, {}).get("사유", ""), 60), cite(elig.get(g, {}).get("근거ID", []))]
            for g in ("G1", "G2", "G3", "G4")]
    return md_table(["요건", "결과", "사유", "근거"], rows)


def checklist_table(checklist: dict) -> tuple[str, list[str]]:
    rows, warn = [], []
    for q, text in QUESTIONS.items():
        c = checklist.get(q, {"판정": "확인불가", "근거": "", "근거ID": []})
        mark = " ⚠주의" if c["판정"] in ("NO", "확인불가") else ""
        if mark:
            warn.append(f"{q} {text} ({c['판정']})")
        rows.append([q, text, c["판정"] + mark, _clip(c.get("근거", ""), 40), cite(c.get("근거ID", []))])
    return md_table(["#", "질문", "판정", "근거", "근거ID"], rows), warn


def scorecard_tables(sc: dict) -> str:
    cat_rows = [[cat, WEIGHTS[cat], f"{avg:.2f}", f"{avg / 5 * WEIGHTS[cat]:.1f}"] for cat, avg in sc["averages"].items()]
    cat_rows.append(["합계", 100, "-", f"{sc['total']}"])
    unknown = set(sc.get("unknown_items", []))
    item_rows = []
    for i, name in ITEM_NAMES.items():
        it = sc["items"][i]
        item_rows.append([i, name, f"{it['점수']}{'*' if i in unknown else ''}", _clip(it.get("채점이유", ""), 50), cite(it.get("근거ID", []))])
    return (md_table(["대분류", "가중치", "평균(1~5)", "환산 점수"], cat_rows) + "\n\n"
            + md_table(["항목", "명칭", "점수", "채점 이유", "근거ID"], item_rows)
            + "\n\n`*` 확인 불가로 2점 처리한 항목.")


def decision_sentence(rec: dict) -> str:
    sc = rec["scorecard"]
    tech = sc["averages"]["제품/기술력"]
    return (f"**최종 판정: {rec['decision']}.** 총점 {sc['total']}점(기준 {INVEST_THRESHOLD}점 이상), "
            f"제품/기술력 {tech:.2f}(기준 {TECH_MIN} 이상), 자격 요건 {rec['eligibility'].get('판정')}.")


# ── 3.4 한계점 ─────────────────────────────────────────────────────────────

def limitations(state: dict, rec: dict | None, checklist_warn: list[str]) -> str:
    items = [
        "자료 시점: 후보 정보의 원천은 2025년 디렉토리북(홍보용 자료)이며, 상장·투자 단계·Exit는 조사 기준일 "
        f"{state.get('as_of_date', '확인 불가')}의 외부 자료로 별도 확인했다.",
        "차트 중심 문서(WSTS·KIET 등 시장 자료)는 텍스트 레이어만 사용해 그래프 내부 수치가 누락되었을 수 있다. 이미지 전용 2쪽은 분석에서 제외했다.",
        "평가 방법: 항목 채점은 LLM이 수행하고 총점·판정·순위는 코드로 고정했으나, 채점 자체의 편차는 남는다. 투자 적격 임계값 70점은 전 항목 평균 3.5점에 해당하는 설계 기준이다.",
    ]
    if rec:
        sc = rec["scorecard"]
        unk = sc.get("unknown_items", [])
        items.append("확인 불가 항목(2점 처리): " + (", ".join(f"{i} {ITEM_NAMES[i]}" for i in unk) if unk else "없음"))
        if checklist_warn:
            items.append("체크리스트 주의 문항: " + "; ".join(checklist_warn))
        for label, key in (("기술", "technology_analysis"), ("시장", "market_analysis")):
            for u in (rec.get(key) or {}).get("미확인정보") or []:
                items.append(f"{label} 미확인 정보: {u}")
    errs = state.get("errors") or []
    if errs:
        items.append(f"평가 중 오류 {len(errs)}건(기업 {', '.join(sorted({e.get('company_id', '?') for e in errs}))})으로 해당 기업은 보류 처리되었다.")
    return "\n".join(f"- {t}" for t in items)
