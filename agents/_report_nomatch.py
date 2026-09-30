"""투자 적격 기업이 없을 때의 보고서 양식: 미충족 사유 중심. 점수·부족분·시나리오는 전부 코드가 계산한다."""

from collections import Counter

from agents._report_render import ITEM_NAMES, _clip, _exclusion_reason, cite, friendly_reason, latest_round, md_table, scope_sentence
from agents.investment import rank_key, total_score
from config import INVEST_THRESHOLD, TECH_MIN, WEIGHTS

NEAR_MISS_N = 3      # 상세 분석할 근접 후보 수
LOW_ITEM_MAX = 2     # 이 점수 이하를 "낮은 항목"으로 본다
LOW_ITEM_SHOW = 3    # 후보당 표시할 낮은 항목 상한 (핵심 이유만 간단히)
TABLE_MAX = 8        # 점수 산출 후보 표 상한 (5장 이내 분량)
PASS_AVG = INVEST_THRESHOLD / 100 * 5  # 70점 = 전 항목 평균 3.5점


# ── 계산 ──────────────────────────────────────────────────────────────────

def _passes(total: float, tech: float) -> bool:
    return total >= INVEST_THRESHOLD and tech >= TECH_MIN


def _meets_criteria(rec: dict) -> bool:
    sc = rec["scorecard"]
    return _passes(sc["total"], sc["averages"]["제품/기술력"])


def _scored_holds_all(records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("decision") == "보류" and r.get("scorecard")]


def scored_holds(records: list[dict]) -> list[dict]:
    """점수가 산출되어 **실제로 기준에 못 미친** 보류 기업을 순위 규칙(총점 → 기술력 → 확인 불가 수 → 실적)으로 정렬."""
    return sorted([r for r in _scored_holds_all(records) if not _meets_criteria(r)], key=rank_key)


def inconsistent_holds(records: list[dict]) -> list[dict]:
    """점수는 투자 적격 기준을 충족하는데 보류로 기록된 기업. decide()가 막는 상태라 데이터·판정 로직 점검 대상이다."""
    return [r for r in _scored_holds_all(records) if _meets_criteria(r)]


def near_miss_candidates(records: list[dict], n: int = NEAR_MISS_N) -> list[dict]:
    return scored_holds(records)[:n]


def shortfall(rec: dict) -> dict:
    """미충족 기준·감점·개선 시나리오·유형. LLM은 이 값을 바꾸지 않고 인용만 한다."""
    sc = rec["scorecard"]
    total, tech = sc["total"], sc["averages"]["제품/기술력"]
    unknown = list(sc.get("unknown_items", []))
    scores = {i: it["점수"] for i, it in sc["items"].items()}
    low = [i for i in ITEM_NAMES if scores.get(i, 5) <= LOW_ITEM_MAX and i not in unknown]

    def scenario(label: str, raise_items: list[str], kind: str):
        avgs, tot = total_score({**scores, **{i: max(scores.get(i, 2), 3) for i in raise_items}})
        return {"label": label, "kind": kind, "total": tot, "tech": avgs["제품/기술력"], "pass": _passes(tot, avgs["제품/기술력"])}

    scenarios = []
    if unknown:
        scenarios.append(scenario(f"자료 없는 {len(unknown)}개 항목을 3점으로 가정", unknown, "unknown"))
    if low:
        scenarios.append(scenario(f"낮은 항목 {len(low)}개를 3점으로 개선", low, "low"))
    if unknown and low:
        scenarios.append(scenario("위 두 가지를 모두 반영", unknown + low, "both"))

    total_gap = round(INVEST_THRESHOLD - total, 1) if total < INVEST_THRESHOLD else 0.0
    tech_gap = round(TECH_MIN - tech, 2) if tech < TECH_MIN else 0.0
    if not total_gap and not tech_gap:
        cause = "기준 충족 (분류 재확인 필요)"  # decide()와 어긋난 데이터에 대한 방어
    elif unknown and scenarios[0]["pass"]:
        cause = "정보 부족형"
    elif tech_gap and total_gap:
        cause = "점수·기술력 동반 미달형"
    elif tech_gap:
        cause = "기술력 미달형"
    elif total_gap <= 5:
        cause = "종합 점수 근소 미달형"
    else:
        cause = "종합 점수 미달형"

    cats = sorted(((c, avg, WEIGHTS[c], (avg - PASS_AVG) / 5 * WEIGHTS[c]) for c, avg in sc["averages"].items()), key=lambda x: x[3])
    return {"total": total, "tech": tech, "total_gap": total_gap, "tech_gap": tech_gap, "categories": cats,
            "low_items": sorted(low, key=lambda i: (scores[i], i)), "unknown": unknown, "scenarios": scenarios, "cause": cause}


def funnel_counts(records: list[dict]) -> Counter:
    c = Counter()
    for r in records:
        d = r.get("decision")
        if d == "투자 적격":
            c["ok"] += 1
        elif d == "제외":
            c["excluded"] += 1
        elif d == "보류":
            c["scored" if r.get("scorecard") else "pending"] += 1
    return c


# ── 섹션 ──────────────────────────────────────────────────────────────────

def _top_reasons(rs: list[dict], k: int = 2) -> str:
    c = Counter(_clip(friendly_reason(_exclusion_reason(r)), 60) for r in rs)
    return "; ".join(f"{t} ({n}곳)" for t, n in c.most_common(k)) or "-"


def overview_section(state: dict, records: list[dict]) -> str:
    c = funnel_counts(records)
    excluded = [r for r in records if r.get("decision") == "제외"]
    pending = [r for r in records if r.get("decision") == "보류" and not r.get("scorecard")]
    funnel = md_table(["단계", "수", "주요 사유"], [
        ["① 투자 요건 미충족 → 제외", c["excluded"], _top_reasons(excluded)],
        ["② 자료 확인 불가·분석 오류 → 보류 (점수 미산출)", c["pending"], _top_reasons(pending)],
        ["③ 종합 점수 기준 미달 → 보류", len(scored_holds(records)), f"종합 점수 {INVEST_THRESHOLD}점 미만 또는 기술력 평균 {TECH_MIN} 미만"],
        ["④ 투자 적격", c["ok"], "-"],
    ])
    odd = inconsistent_holds(records)
    holds = scored_holds(records)
    parts = [f"### 1.1 단계별 탈락 현황\n\n{scope_sentence(state, records)}\n\n{funnel}"]
    if odd:
        names = ", ".join(f"{r['current_company']['기업명']}(종합 {r['scorecard']['total']}점·기술력 {r['scorecard']['averages']['제품/기술력']:.2f})" for r in odd)
        parts[0] += (f"\n\n**⚠ 분류 재확인 필요 {len(odd)}곳**: {names}. 점수는 투자 적격 기준(종합 점수 {INVEST_THRESHOLD}점 이상, 기술력 {TECH_MIN} 이상)을 "
                     "충족하지만 보류로 분류되어 있어 이 보고서의 미충족 분석에서는 제외했다. 분류 기준을 별도로 확인해야 한다.")
    if holds:
        rows = []
        for n, r in enumerate(holds[:TABLE_MAX], 1):
            g = shortfall(r)
            rows.append([n, r["current_company"]["기업명"], g["total"], f"-{g['total_gap']}" if g["total_gap"] else "충족",
                         f"{g['tech']:.2f}", f"-{g['tech_gap']:.2f}" if g["tech_gap"] else "충족", len(g["unknown"]), g["cause"]])
        more = f"\n\n점수 산출 후보 {len(holds)}곳 중 상위 {min(len(holds), TABLE_MAX)}곳만 표시했다." if len(holds) > TABLE_MAX else ""
        parts.append("### 1.2 점수 산출 후보 (정렬 기준: 종합 점수 → 기술력 → 자료 없는 항목 수 → 실적)\n\n<!--chart:candidates-->\n\n<!--chart:skip_table-->\n\n" +
                     md_table(["#", "기업", "종합 점수", "기준 미달분", "기술력", "기술력 미달분", "자료 없음", "미충족 유형"], rows) + more)
    else:
        parts.append("### 1.2 점수 산출 후보\n\n점수가 산출된 후보가 없다. 투자 요건 미충족·확인 필요 또는 분석 오류로 투자 채점까지 완료한 후보가 없다.")
    return "\n\n".join(parts)


def candidate_block(rec: dict, n: int, commentary: str = "") -> str:
    """후보 1곳의 미충족 사유: 기준 대비 표 → 낮은 항목 → 자료 보완으로 해결되는지 → 한 줄 해설."""
    sc, co, g = rec["scorecard"], rec["current_company"], shortfall(rec)
    parts = [f"### 2.{n} {co['기업명']}: {g['cause']} (종합 점수 {g['total']}점)",
             f"메인 아이템: {co.get('메인아이템') or '확인 불가'}"]
    parts.append(md_table(["기준", "요구 수준", "실제", "판정"], [
        ["종합 점수", f"{INVEST_THRESHOLD}점 이상", f"{g['total']}점", f"미충족 ({g['total_gap']}점 부족)" if g["total_gap"] else "충족"],
        ["기술력 평균", f"{TECH_MIN} 이상", f"{g['tech']:.2f}", f"미충족 ({g['tech_gap']:.2f} 부족)" if g["tech_gap"] else "충족"],
    ]))

    if g["low_items"]:
        shown = g["low_items"][:LOW_ITEM_SHOW]
        rows = [[ITEM_NAMES[i], f"{sc['items'][i]['점수']}점", (_clip(sc["items"][i].get("채점이유", ""), 64) + " " + cite(sc["items"][i].get("근거ID", []))).strip()] for i in shown]
        more = f"\n\n그 외 낮은 항목 {len(g['low_items']) - len(shown)}개" if len(g["low_items"]) > len(shown) else ""
        parts.append("**점수를 깎은 항목**\n\n" + md_table(["항목", "점수", "이유"], rows) + more)
    if g["unknown"]:
        parts.append("**자료 없음(2점 부여)**: " + ", ".join(ITEM_NAMES[i] for i in g["unknown"]))

    if g["scenarios"]:
        first = next((s for s in g["scenarios"] if s["pass"]), None)
        hint = {"unknown": "자료가 확인되면 재검토할 여지가 있다.", "low": "해당 항목의 실제 개선이 확인되면 재검토할 여지가 있다.",
                "both": "자료 확인과 항목 개선이 함께 이뤄지면 재검토할 여지가 있다."}
        parts.append(f"**보완하면 통과하는가?** {first['label']}하면 종합 {first['total']}점으로 기준을 넘는다. {hint[first['kind']]}" if first
                     else "**보완하면 통과하는가?** 자료를 보완하거나 낮은 항목을 3점으로 올려도 기준에 못 미친다. 항목 자체의 개선이 필요하다.")
    if commentary.strip():
        parts.append(f"**해설**: {commentary.strip()}")
    cond = (rec.get("decision_details") or {}).get("재검토조건") or []
    if cond:
        parts.append("**재검토 조건**: " + "; ".join(cond[:2]))
    return "\n\n".join(parts)


def followup_section(top: list[dict]) -> str:
    if not top:
        return "재검토 대상으로 삼을 점수 산출 후보가 없다."
    rows = []
    for r in top:
        g, det = shortfall(r), r.get("decision_details") or {}
        need = []
        if g["total_gap"]:
            need.append(f"종합 점수 +{g['total_gap']}점")
        if g["tech_gap"]:
            need.append(f"기술력 평균 +{g['tech_gap']:.2f}")
        first = next((s for s in g["scenarios"] if s["pass"]), None)
        if first:
            need.append(f"({first['label']} 시 충족)")
        rows.append([r["current_company"]["기업명"], " ".join(need) or "-", "; ".join(det.get("재검토조건") or ["미기재"]),
                     "; ".join(det.get("추가확인사항") or ["미기재"])])
    return md_table(["기업", "통과에 필요한 개선", "재검토 조건", "추가로 확인할 사항"], rows)
