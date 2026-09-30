"""⑤ 경쟁사 비교 에이전트 — 기존 인덱스 재조회(02~11, 15) + 웹서치(경쟁 제품 스펙). 신규 인덱스 없음."""

from state import State


def run(state: State) -> dict:
    """
    입력: technology_analysis, market_analysis, current_company
    출력: {
        "competitor_analysis": {경쟁제품[{기업명, 제품, 핵심지표값, 출처}], 비교표, 우위, 열위, 비교조건, 비교한계, 근거ID},
        "current_evidence": [...],
    }
    """
    raise NotImplementedError
