"""④ 시장성 평가 에이전트 [RAG] — doc_type="market" (12~15) 하이브리드 검색, 재검색 최대 1회."""

from state import State, next_attempt


def run(state: State) -> dict:
    """
    입력: current_company(사업Point·주요거래처·매출액), technology_analysis
    처리: 질의 생성 → rag.retriever.hybrid_search(doc_type="market") → 기업의 시장 주장과 SIA/WSTS/KIET/OECD 대조
    출력: {
        "market_analysis": {목표고객, 시장규모{값, 출처, 기준연도}, 성장률, 사업모델, 글로벌확장성, 성장요인, 위험, 미확인정보, 근거ID, "근거충분": bool},
        "current_evidence": [...],
        "retrieve_count": next_attempt(state, "market_analysis"),
    }
    """
    raise NotImplementedError
