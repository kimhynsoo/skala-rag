"""③ 기술 요약 에이전트 [RAG] — doc_type="tech" (02~11) 하이브리드 검색, top-k=5, 재검색 최대 1회."""

from agents._rag_utils import run_analysis
from state import State


def run(state: State) -> dict:
    """
    입력: current_company(메인아이템·기술분야·혁신성·개발진척도), 재시도 시 이전 technology_analysis
    처리: 질의 생성(재시도면 재작성) → rag.retriever.hybrid_search(doc_type="tech") → IRDS·UCIe·CXL 기준값과 대조
    출력: {
        "technology_analysis": {핵심기술, 제품성숙도, 성능지표, 기준대조, 강점, 한계, 미확인정보, 근거ID, "근거충분": bool},
        "current_evidence": [...],
        "retrieve_count": next_attempt(state, "technology_analysis"),
    }
    """
    return run_analysis(state, "technology")
