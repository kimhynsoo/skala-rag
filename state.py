"""Graph State (설계: 그래프 설계 › 1. State 설계). 생명주기별 4개 그룹."""

import operator
from typing import Annotated, Literal, TypedDict


def merge_evidence(old: list[dict], new: list[dict] | None) -> list[dict]:
    """None을 받으면 리셋, 리스트를 받으면 누적."""
    if new is None:
        return []
    return old + new


def merge_dict(old: dict, new: dict | None) -> dict:
    """병렬 노드가 서로 다른 키를 동시에 써도 합쳐지도록. None이면 리셋 (기업 전환)."""
    if new is None:
        return {}
    return {**(old or {}), **new}


Decision = Literal["투자 적격", "보류", "제외"]


class State(TypedDict, total=False):
    # ① 입력·설정 (실행 전 고정)
    source_document: str
    as_of_date: str
    evaluation_criteria: dict
    candidate_companies: list[dict]

    # ② 흐름 제어 (라우팅·종료·재개에 필요한 최소치)
    trace_id: str  # 상관 키: outputs/logs/{trace_id}.jsonl·LangSmith metadata·checkpointer thread_id
    current_index: int
    route_reason: str  # 마지막 분기 사유 1줄 (전체 이력은 외부 로그)
    retrieve_count: int  # 구 구조용, Task 2a에서 삭제
    next: list[str]  # Supervisor가 고른 다음 노드 (conditional edge가 읽음)
    step_count: int  # 기업별 Supervisor 방문 수 (Supervisor만 씀)
    max_steps: int  # 종료 가드 상한 (config.MAX_SUPERVISOR_STEPS)
    rework_reason: dict[str, str]  # 에이전트별 재작업 사유 → 질의 재작성
    node_status: Annotated[dict[str, str], merge_dict]  # {"technology": "SUCCESS"|"FAILED"} 병렬 쓰기 병합
    agent_attempts: Annotated[dict[str, int], merge_dict]  # 에이전트별 실행 횟수, MAX_REWORK 상한
    last_error: dict | None  # 마지막 오류 {company_id, stage, type, error, ts} (Supervisor만 씀)
    company_filter: list[str]  # 지정 시 해당 company_id만 평가 (트레이스 캡처용)

    # ③ 작업 산출물 (후보 전환 시 리셋)
    current_company: dict | None
    eligibility: dict | None
    checklist: dict | None
    technology_analysis: dict | None
    market_analysis: dict | None
    competitor_analysis: dict | None
    current_evidence: Annotated[list[dict], merge_evidence]
    scorecard: dict | None
    decision: Decision | None
    decision_details: dict | None

    # ④ 실행 전체 (후보 경계를 넘어 유지)
    evaluation_results: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]
    selected_company_id: str | None  # 투자 적격 중 1위, 없으면 None
    ranking: list[str]  # 투자 적격 기업 ID 순위
    final_report: str
    eval_result: dict | None  # 품질 평가 verdict (EvaluationResult + score)
    report_attempts: int  # 품질 평가 횟수, MAX_REPORT_REVISIONS 상한


def next_attempt(state: State, output_key: str) -> int:
    """RAG 에이전트의 retrieve_count 갱신값. 해당 에이전트 첫 진입(산출물 None)이면 1부터 센다."""
    return 1 if state.get(output_key) is None else state.get("retrieve_count", 0) + 1
