"""bge-m3 하이브리드 검색 (설계 3-5): dense(Chroma) + sparse(lexical weight) → RRF.

에이전트는 hybrid_search()만 호출한다. 인덱스가 없으면 rag.parser.load_corpus()로 자동 구축.
색인은 (문서 내용 + 메타데이터 + 모델명) 해시로 .cache/index/<hash>/ 에 저장하고, 같으면 재사용한다.
  - dense: Chroma 벡터 DB (메타데이터 필터를 DB가 처리)
  - sparse: {토큰ID: 가중치} JSON (교재 04b-BGE-M3와 같은 방식)
FAISS는 torch와 OpenMP 충돌로 쓰지 않는다 (docs/TROUBLESHOOTING.md).
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

import chromadb
import numpy as np
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from config import CACHE_DIR, DATA_DIR, EMBEDDING_MODEL, RRF_WEIGHTS, TOP_K

CANDIDATES = 20  # RRF 전 dense·sparse 각각에서 뽑는 후보 수
COLLECTION = "corpus"

_store: Chroma | None = None
_docs: dict[str, Document] = {}  # chunk_id → 원본 청크
_sparse: dict[str, dict[str, float]] = {}  # chunk_id → {토큰ID: 가중치}


def rrf_scores(rankings: dict[str, list], weights: dict[str, float] = RRF_WEIGHTS, k: int = 60) -> dict:
    """Reciprocal Rank Fusion 점수. rankings = {"dense": [id, ...], "sparse": [...]}."""
    scores: dict = {}
    for name, ids in rankings.items():
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + weights[name] / (k + rank)
    return scores


def rrf(rankings: dict[str, list], weights: dict[str, float] = RRF_WEIGHTS, k: int = 60) -> list:
    """RRF로 융합한 id 순위."""
    scores = rrf_scores(rankings, weights, k)
    return sorted(scores, key=scores.get, reverse=True)


def lexical_score(query: dict[str, float], doc: dict[str, float]) -> float:
    """bge-m3 sparse 점수: 질의·문서에 공통으로 등장한 토큰 가중치 곱의 합."""
    return sum(w * doc[t] for t, w in query.items() if t in doc)


@lru_cache(maxsize=1)
def _model():
    import torch
    from FlagEmbedding import BGEM3FlagModel

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    return BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=device != "cpu", devices=[device])


def _encode(texts: list[str], query: bool = False) -> tuple[np.ndarray, list[dict[str, float]]]:
    """→ (정규화된 dense 벡터 [n, 1024] float32, 토큰별 sparse 가중치). 한 번의 추론으로 둘 다 얻는다."""
    m = _model()
    fn = m.encode_queries if query else m.encode_corpus
    out = fn(texts, batch_size=16, max_length=512, return_dense=True, return_sparse=True)
    dense = np.asarray(out["dense_vecs"], dtype="float32").reshape(len(texts), -1)
    sparse = [{t: float(w) for t, w in lw.items()} for lw in out["lexical_weights"]]
    return dense, sparse


class BGEM3Embeddings(Embeddings):
    """LangChain 임베딩 인터페이스로 감싼 bge-m3 dense. Chroma의 embedding_function으로 쓴다."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _encode(texts)[0].tolist()

    def embed_query(self, text: str) -> list[float]:
        return _encode([text], query=True)[0][0].tolist()


def _match(meta: dict, doc_type: str, sub_domain: str | None) -> bool:
    return meta.get("doc_type") == doc_type and sub_domain in (None, meta.get("sub_domain"))


def build_index(docs: list[Document]) -> Path:
    """dense는 Chroma에, sparse는 JSON에 저장(또는 캐시 로드)하고 모듈 전역 인덱스로 설정. → 색인 폴더 경로"""
    global _store, _docs, _sparse
    ids = [d.metadata["chunk_id"] for d in docs]
    payload = json.dumps([[d.page_content, d.metadata] for d in docs] + [EMBEDDING_MODEL],
                         ensure_ascii=False, sort_keys=True, default=str)
    path = CACHE_DIR / "index" / hashlib.sha256(payload.encode()).hexdigest()[:16]
    client = chromadb.PersistentClient(path=str(path), settings=chromadb.Settings(anonymized_telemetry=False))

    if (path / "sparse.json").exists():
        sparse = json.loads((path / "sparse.json").read_text())
    else:
        dense, sparse_list = _encode([d.page_content for d in docs])
        client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"}).upsert(
            ids=ids,
            embeddings=dense,
            documents=[d.page_content for d in docs],
            metadatas=[{k: v for k, v in d.metadata.items() if v is not None} for d in docs],  # Chroma는 None 불가
        )
        sparse = dict(zip(ids, sparse_list))
        (path / "sparse.json").write_text(json.dumps(sparse))  # 마지막에 저장 → 색인 완료 표식

    _store = Chroma(client=client, collection_name=COLLECTION, embedding_function=BGEM3Embeddings())
    _docs, _sparse = dict(zip(ids, docs)), sparse
    return path


def hybrid_search(
    query: str,
    doc_type: str,
    sub_domain: str | None = None,
    k: int = TOP_K,
    mode: Literal["hybrid", "dense", "sparse"] = "hybrid",
    doc_id: str | None = None,
) -> list[Document]:
    """메타데이터 필터 → dense(Chroma)·sparse 각각 검색 → RRF → 상위 k. metadata["score"]에 RRF 점수.

    mode는 임베딩 비교 실험(설계 3-6 비교군 1·2)용. 에이전트는 기본값 hybrid만 쓴다.
    """
    if _store is None:
        from rag.parser import load_corpus

        build_index(load_corpus(DATA_DIR))

    pool = [cid for cid, d in _docs.items() if _match(d.metadata, doc_type, sub_domain)
            and (doc_id is None or d.metadata.get("doc_id") == doc_id)]
    if not pool:
        return []
    q_dense, q_sparse = _encode([query], query=True)

    rankings: dict[str, list[str]] = {}
    if mode != "sparse":
        filters = [{"doc_type": doc_type}]
        if sub_domain is not None:
            filters.append({"sub_domain": sub_domain})
        if doc_id is not None:
            filters.append({"doc_id": doc_id})
        where = filters[0] if len(filters) == 1 else {"$and": filters}
        found = _store.similarity_search_by_vector(q_dense[0].tolist(), k=min(CANDIDATES, len(pool)), filter=where)
        rankings["dense"] = [d.metadata["chunk_id"] for d in found]
    if mode != "dense":
        scored = sorted(((lexical_score(q_sparse[0], _sparse[c]), c) for c in pool), reverse=True)
        # 공유 토큰이 없는(점수 0) 문서는 제외: 교차언어 질의에서 무의미한 sparse 순위가 RRF에 섞이는 것 방지
        rankings["sparse"] = [c for s, c in scored[:CANDIDATES] if s > 0]

    scores = rrf_scores(rankings)
    top = sorted(scores, key=scores.get, reverse=True)[:k]
    return [Document(page_content=_docs[c].page_content, metadata={**_docs[c].metadata, "score": round(scores[c], 5)})
            for c in top]
