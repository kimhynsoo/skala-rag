"""선정 근거 하이라이트: 점수가 높은 강점 영역을 고르고, 영역마다 한 줄 사실(fact)을 데이터에서 뽑는다.
표시할 그래프는 이 결과로 정한다 — 강점이 아닌 영역의 그래프는 넣지 않아 5장 이내를 지킨다."""

import re
from dataclasses import dataclass

# (영역 이름, 채점 항목, 시각화 종류) — 순서는 동점일 때의 우선순위
AREAS = [
    ("기술력", ["C1", "C2", "C3"], "tech"),
    ("투자 유치", ["E3", "D3"], "funding"),
    ("지식재산", ["D1"], "ip"),
    ("매출·고객", ["E1", "E2"], "revenue"),
    ("시장성", ["B1", "B2", "B3"], "market"),
    ("팀 역량", ["A1", "A2", "A3"], "team"),
]
STRONG_MIN = 3.5   # 평균 3.5점(= 70점 수준) 이상이면 강점
MAX_FEATURED = 3


@dataclass
class Strength:
    area: str
    kind: str
    avg: float
    fact: str


def _eok(thousand_won: float) -> str:
    v = thousand_won / 100_000
    return f"{v:,.0f}억 원" if v >= 10 else f"{v:,.1f}억 원"


def confirmed_funding(company: dict) -> list[dict]:
    return [h for h in company.get("투자유치이력") or [] if h.get("확정", True) and h.get("금액")]


def patents(company: dict) -> tuple[int, int]:
    ip = company.get("지식재산권") or {}
    return len(ip.get("등록") or []), len(ip.get("출원") or [])


def revenue_eok(sales: dict) -> float | None:
    """최근 연도 매출(국내+해외 환산)을 억 원으로. 공개되지 않았거나 없으면 None."""
    if not sales or sales.get("상태") != "공개":
        return None
    if sales.get("해외") and sales.get("해외단위") not in (None, "천원", "KRW_THOUSAND"):
        return None
    overseas = sales.get("해외") or 0
    total = (sales.get("국내") or 0) + overseas
    return total / 100_000 if total > 0 else None


def _fact(kind: str, rec: dict) -> str:
    co, tech, mkt = rec["current_company"], rec.get("technology_analysis") or {}, rec.get("market_analysis") or {}
    if kind == "funding":
        conf = confirmed_funding(co)
        if not conf:
            return ""
        total = sum(h["금액"] for h in conf)
        last = max(conf, key=lambda h: str(h.get("일자") or ""))
        return f"확정 누적 {_eok(total)} · 최근 {last.get('단계') or '라운드'} ({last.get('일자') or '시기 미상'})"
    if kind == "ip":
        reg, app = patents(co)
        return f"등록 특허 {reg}건 · 출원 특허 {app}건" if reg + app else ""
    if kind == "tech":
        mat = tech.get("제품성숙도") or {}
        bench = next((b for b in tech.get("기준대조") or [] if b.get("비교결과") in ("상회", "동등")), None)
        metric = next((m for m in tech.get("성능지표") or [] if bench and m.get("지표명") == bench.get("지표명")), None)
        stage = f"기술 성숙도 {('TRL ' + str(mat['TRL'])) if mat.get('TRL') else mat.get('단계') or '확인 불가'}"
        if bench and metric:
            return f"{metric['지표명']} {metric['값']}: 업계 기준({bench['업계기준']}) {bench['비교결과']} · {stage}"
        return stage
    if kind == "revenue":
        s = co.get("매출액") or {}
        r = revenue_eok(s)
        clients = len([c for c in co.get("주요거래처") or [] if c and c != "비공개"])
        head = f"{s.get('연도')}년 매출 {_eok(r * 100_000)}" if r else "매출 비공개·없음"
        return f"{head} · 주요 거래처 {clients}곳" if clients else head
    if kind == "market":
        size, growth = mkt.get("시장규모") or {}, mkt.get("성장률") or {}
        parts = [p for p in (f"시장 규모 {size.get('값')}" if size.get("값") else "", growth.get("값")) if p]
        return " · ".join(parts)
    if kind == "team":
        m = next((m for m in co.get("주요구성원") or [] if m.get("학력") or m.get("경력")), None)
        return f"{m['직책']} · {(m.get('학력') or m.get('경력'))[:34]}" if m else ""
    return ""


def area_scores(sc: dict) -> dict[str, float]:
    items = sc["items"]
    return {name: sum(items[i]["점수"] for i in ids if i in items) / len([i for i in ids if i in items])
            for name, ids, _ in AREAS if any(i in items for i in ids)}


def pick_strengths(rec: dict) -> list[Strength]:
    """평균 점수가 높은 영역 상위 3개(3.5점 이상, 부족하면 최고점 순으로 2개까지 채움). 사실 문장이 없는 영역은 제외."""
    scores = area_scores(rec["scorecard"])
    order = {name: n for n, (name, _, _) in enumerate(AREAS)}
    kinds = {name: kind for name, _, kind in AREAS}
    ranked = sorted(scores, key=lambda a: (-scores[a], order[a]))
    cands = [Strength(a, kinds[a], scores[a], plain(_fact(kinds[a], rec))) for a in ranked]
    cands = [c for c in cands if c.fact]
    strong = [c for c in cands if c.avg >= STRONG_MIN][:MAX_FEATURED]
    return strong if len(strong) >= 2 else cands[:2]


def strong_items(rec: dict, n: int = 4) -> list[tuple[str, dict]]:
    """점수 4점 이상 항목 상위 n개 (동점이면 항목 순서)."""
    items = rec["scorecard"]["items"]
    unk = set(rec["scorecard"].get("unknown_items", []))
    return sorted(((i, v) for i, v in items.items() if v["점수"] >= 4 and i not in unk), key=lambda kv: (-kv[1]["점수"], kv[0]))[:n]


def weak_items(rec: dict, n: int = 4) -> list[tuple[str, dict, bool]]:
    """보완할 항목: 2점 이하(자료 없음 포함). (id, 항목, 자료없음 여부)"""
    items = rec["scorecard"]["items"]
    unk = set(rec["scorecard"].get("unknown_items", []))
    weak = [(i, v, i in unk) for i, v in items.items() if v["점수"] <= 2 or i in unk]
    return sorted(weak, key=lambda t: (t[1]["점수"], t[0]))[:n]


_ID_TAG = re.compile(r"\s*\[(?:(?:DIR|ELG|TEC|MKT|CMP)-[^\]]*)\]")


def plain(text) -> str:
    """그래프·카드에 들어가는 데이터 문자열에서 내부 근거 ID 표기([DIR-C01-01] 등)를 지운다."""
    return _ID_TAG.sub("", str(text or "")).strip()


def first_number(text) -> float | None:
    m = re.search(r"\d[\d,]*\.?\d*", str(text or ""))
    return float(m.group(0).replace(",", "")) if m else None
