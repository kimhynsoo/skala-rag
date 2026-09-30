"""② 적격성 검증 에이전트 — G1~G4. G1~G3 웹/DART + 규칙, G4 LLM. RAG 미사용."""

from state import State


def run(state: State) -> dict:
    """
    입력: current_company, as_of_date
    출력: {
        "eligibility": {"판정": "적격"|"부적격"|"확인필요", "G1": ..., "G2": ..., "G3": ..., "G4": ..., "사유": str, "근거ID": [...]},
        "current_evidence": [근거 레코드, ...],
    }
    분기는 graph.route_eligibility가 eligibility["판정"]으로 결정한다.
    """
    raise NotImplementedError
