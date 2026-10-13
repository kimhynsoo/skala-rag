"""⑧ 보고서 품질 평가 — Hybrid (1안 룰 검사 + 2안 LLM Judge).

세 항목(Groundedness·중립성·편향 통제)은 룰과 Judge가 모두 통과해야 통과다.
미달이면 issues를 피드백으로 report에 넘겨 다시 쓰게 하고, 상한을 넘으면 end_with_warning으로 종료한다.
"""

import json
from collections import Counter

from pydantic import BaseModel, Field

from agents._report_llm import structured_call
from agents._report_render import ID_RE
from config import MAX_REPORT_REVISIONS, MAX_SOURCE_SHARE, MIN_PUBLISHERS
from obs import log_decision
from state import State

CRITERIA = ("groundedness", "neutrality", "bias_control")
# 중립성: 투자 판정은 코드 점수로만 내린다. 주관적 추천·우열 단정 표현 금지
BANNED = ("강력 추천", "강력히 추천", "반드시 투자", "최고의", "압도적", "독보적", "완벽한", "유일한")


class Criterion(BaseModel):
    passed: bool
    reason: str


class EvaluationResult(BaseModel):
    """LLM Judge 체크리스트. description이 곧 평가 기준이다 (build_judge_prompt가 읽음)."""

    groundedness: bool = Field(description="보고서의 수치·사실 주장이 인용근거의 원문발췌로 뒷받침된다. 원문에 없는 수치가 하나라도 있으면 False")
    neutrality: bool = Field(description="점수 근거 없이 특정 기업·기술을 추천하거나 경쟁 제품보다 낫다고 단정하지 않고, 강점과 리스크를 함께 서술한다")
    bias_control: bool = Field(description="불리한 근거(미확인 항목·열위·리스크)를 누락하지 않고, 한 출처에 결론을 의존하지 않는다")
    issues: list[str] = Field(description="미달 항목별로 어느 문장/섹션이 왜 미달인지. 모두 통과면 빈 리스트")


def build_judge_prompt() -> str:
    """EvaluationResult의 bool 필드 description으로 체크리스트를 만든다 → 기준 변경은 스키마만 수정."""
    lines = [f"{i}. {name}: {f.description}"
             for i, (name, f) in enumerate(EvaluationResult.model_fields.items(), 1) if f.annotation is bool]
    return ("너는 AI 반도체 스타트업 투자 평가 보고서의 품질 검수자다. 룰검사는 형식 검사이므로 너는 내용을 본다.\n"
            "아래 기준을 각각 True/False로 판정하고, False인 항목은 issues에 구체적으로 쓴다.\n\n"
            "[평가 기준]\n" + "\n".join(lines))


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


def _all_evidence(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in records:
        for e in r.get("current_evidence") or []:
            if e.get("근거ID"):
                seen.setdefault(e["근거ID"], e)
    return list(seen.values())


def _log_state(state: State) -> dict:
    """결정 로그의 company_id는 보고서 대상(selected_company_id)이어야 한다. State의 current_company는 마지막 순회 기업이다."""
    selected = state.get("selected_company_id")
    rec = next((r for r in state.get("evaluation_results") or [] if r.get("company_id") == selected), {})
    return {**state, "current_company": rec.get("current_company") or ({"company_id": selected} if selected else {})}


def run(state: State) -> dict:
    report = state.get("final_report") or ""
    evidence = _all_evidence(state.get("evaluation_results") or [])
    rules = rule_checks(report, evidence)
    cited = set(ID_RE.findall(report.split("## REFERENCE")[0]))
    user = json.dumps({
        "보고서": report,
        "인용근거": [{"근거ID": e["근거ID"], "원문발췌": (e.get("원문발췌") or "")[:300]}
                    for e in evidence if e["근거ID"] in cited][:40],
        "룰검사": {k: v.model_dump() for k, v in rules.items()},
    }, ensure_ascii=False)
    try:
        judge = structured_call(EvaluationResult, build_judge_prompt(), user)
    except Exception as e:  # Judge 호출 실패가 전체 실행을 죽이지 않게: 미달 처리 → 재생성/end_with_warning 경로로 종료
        judge = EvaluationResult(groundedness=False, neutrality=False, bias_control=False,
                                 issues=[f"Judge 호출 실패({type(e).__name__}) → 미달 처리"])
    result = {k: {"passed": rules[k].passed and getattr(judge, k), "rule": rules[k].reason,
                  "judge": getattr(judge, k)} for k in CRITERIA}
    score = sum(v["passed"] for v in result.values()) / len(CRITERIA)
    passed = score == 1.0
    issues = [f"{k}: {v['rule']}" for k, v in result.items() if not v["passed"]] + judge.issues
    attempts = state.get("report_attempts", 0) + 1
    log_decision(_log_state(state), "evaluator", "pass" if passed else "fail", "; ".join(issues) or "3개 항목 충족")
    return {"eval_result": {"passed": passed, "score": score, **result, "issues": issues},
            "report_attempts": attempts}


def route(state: State) -> str:
    if (state.get("eval_result") or {}).get("passed"):
        return "__end__"
    if state.get("report_attempts", 0) > MAX_REPORT_REVISIONS:
        return "end_with_warning"
    return "report"


def end_with_warning(state: State) -> dict:
    """재생성 상한 초과 시 명시적 종료. 미달 상태를 기록하고 보고서는 그대로 둔다."""
    ev = state.get("eval_result") or {}
    reason = f"재생성 상한 {MAX_REPORT_REVISIONS}회 초과, 점수 {ev.get('score', 0):.2f}, 미달: {ev.get('issues', [])}"
    log_decision(_log_state(state), "end_with_warning", "stop", reason)
    return {"route_reason": f"[경고] {reason}"}
