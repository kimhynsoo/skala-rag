"""⑧ 보고서 품질 평가 — Hybrid (1안 룰 검사 + 2안 LLM Judge)."""

from collections import Counter

from pydantic import BaseModel

from agents._report_render import ID_RE

MIN_PUBLISHERS = 3  # Task 5에서 config 값으로 교체
MAX_SOURCE_SHARE = 0.5  # Task 5에서 config 값으로 교체
# 중립성: 투자 판정은 코드 점수로만 내린다. 주관적 추천·우열 단정 표현 금지
BANNED = ("강력 추천", "강력히 추천", "반드시 투자", "최고의", "압도적", "독보적", "완벽한", "유일한")


class Criterion(BaseModel):
    passed: bool
    reason: str


def rule_checks(report: str, evidence: list[dict]) -> dict[str, Criterion]:
    """1안: 형식만 검사한다 (내용은 보지 않음)."""
    body = report.split("## REFERENCE")[0]
    cited = ID_RE.findall(body)
    known = {e["근거ID"]: e for e in evidence if e.get("근거ID")}
    unknown = sorted(set(cited) - set(known))
    ground = Criterion(
        passed=bool(cited) and not unknown,
        reason="인용 없음" if not cited else (f"출처 없는 근거ID {unknown}" if unknown else f"인용 {len(set(cited))}건 모두 추적 가능"),
    )
    hits = [w for w in BANNED if w in body]
    neutral = Criterion(passed=not hits, reason=f"금지 표현 {hits}" if hits else "금지 표현 없음")
    # 기업 디렉토리(DIR-)는 평가 대상 자체 소개라 출처 편중 계산에서 제외하고 외부 근거로만 판정한다
    external = [i for i in cited if i in known and not i.startswith("DIR-")]
    pubs = Counter(known[i].get("publisher") or known[i].get("출처명") or "미상" for i in external)
    share = max(pubs.values()) / sum(pubs.values()) if pubs else 1.0
    bias = Criterion(
        passed=len(pubs) >= MIN_PUBLISHERS and share <= MAX_SOURCE_SHARE,
        reason=f"외부 출처 기관 {len(pubs)}곳, 최다 비중 {share:.0%} (기준 {MIN_PUBLISHERS}곳 이상, {MAX_SOURCE_SHARE:.0%} 이하)",
    )
    return {"groundedness": ground, "neutrality": neutral, "bias_control": bias}
