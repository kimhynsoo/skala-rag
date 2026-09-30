"""bge-m3 하이브리드 검색 (설계 3-5): dense(FAISS) + sparse(lexical weight) → RRF."""

from langchain_core.documents import Document

from config import RRF_WEIGHTS, TOP_K


def rrf(rankings: dict[str, list[str]], weights: dict[str, float] = RRF_WEIGHTS, k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion. rankings = {"dense": [chunk_id, ...], "sparse": [...]}."""
    scores: dict[str, float] = {}
    for name, ids in rankings.items():
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + weights[name] / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)


def build_index(docs: list[Document]) -> None:
    """bge-m3 dense/sparse 임베딩 → .cache/ 에 저장. 문서 해시가 같으면 재사용."""
    raise NotImplementedError


def hybrid_search(query: str, doc_type: str, sub_domain: str | None = None, k: int = TOP_K) -> list[Document]:
    """메타데이터 필터 → dense·sparse 각각 검색 → rrf() → 상위 k."""
    raise NotImplementedError
