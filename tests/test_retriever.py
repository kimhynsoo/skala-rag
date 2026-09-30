"""rag.retriever 동작 테스트. bge-m3 대신 가짜 인코더를 끼워 모델 없이 실행된다."""

import numpy as np
import pytest
from langchain_core.documents import Document

from rag import retriever

TOPICS = ["chiplet", "memory", "market", "patent"]


def fake_encode(texts, query=False):
    """dense: 주제 단어 one-hot / sparse: 공백 분리 토큰 가중치 1.0 (한글 질의 '칩렛' → chiplet 주제로 매핑)."""
    calls.append(len(texts))
    dense = np.zeros((len(texts), len(TOPICS)), dtype="float32")
    for r, t in enumerate(texts):
        for c, topic in enumerate(TOPICS):
            if topic in t.lower() or {"칩렛": "chiplet", "메모리": "memory"}.get(t.split()[0]) == topic:
                dense[r, c] = 1.0
    dense /= np.linalg.norm(dense, axis=1, keepdims=True).clip(min=1e-9)
    return dense, [{tok: 1.0 for tok in t.split()} for t in texts]


calls: list[int] = []

DOCS = [
    Document(page_content="UCIe chiplet interconnect 64 GT/s", metadata={"chunk_id": "07-0001", "doc_type": "tech", "sub_domain": "interface"}),
    Document(page_content="CXL memory expansion 128 GT/s", metadata={"chunk_id": "08-0001", "doc_type": "tech", "sub_domain": "interface"}),
    Document(page_content="HBM memory bandwidth roadmap", metadata={"chunk_id": "06-0001", "doc_type": "tech", "sub_domain": "memory"}),
    Document(page_content="global market forecast memory demand", metadata={"chunk_id": "13-0001", "doc_type": "market"}),
    Document(page_content="patent 10-2532099 accelerator", metadata={"chunk_id": "01-0001", "doc_type": "tech", "sub_domain": "ai_computing"}),
]


@pytest.fixture(autouse=True)
def index(monkeypatch, tmp_path):
    monkeypatch.setattr(retriever, "_encode", fake_encode)
    monkeypatch.setattr(retriever, "CACHE_DIR", tmp_path)
    calls.clear()
    retriever.build_index(DOCS)
    return tmp_path


def ids(results):
    return [d.metadata["chunk_id"] for d in results]


def test_doc_type_and_sub_domain_filter():
    assert "13-0001" not in ids(retriever.hybrid_search("memory demand", doc_type="tech"))
    assert ids(retriever.hybrid_search("memory", doc_type="tech", sub_domain="memory")) == ["06-0001"]
    assert retriever.hybrid_search("memory", doc_type="none") == []


@pytest.mark.parametrize("mode", ["hybrid", "dense", "sparse"])
def test_doc_id_filter_applies_before_ranking(mode):
    docs = [Document(page_content="market memory demand", metadata={"chunk_id": f"{doc_id}-0001",
            "doc_type": "market", "doc_id": doc_id}) for doc_id in ("13", "15")]
    retriever.build_index(docs)
    assert ids(retriever.hybrid_search("market memory", doc_type="market", doc_id="15", mode=mode)) == ["15-0001"]
    assert retriever.hybrid_search("market", doc_type="market", doc_id="99", mode=mode) == []


def test_exact_match_via_sparse():
    # sparse는 "128"·"GT/s"가 모두 일치하는 08을 1위로 둔다
    assert ids(retriever.hybrid_search("128 GT/s", doc_type="tech", mode="sparse"))[0] == "08-0001"
    # hybrid: dense 신호가 없는 07(GT/s만 일치)보다 08이 위
    res = ids(retriever.hybrid_search("memory 128 GT/s", doc_type="tech"))
    assert res.index("08-0001") < res.index("07-0001")
    assert ids(retriever.hybrid_search("10-2532099", doc_type="tech", mode="sparse")) == ["01-0001"]


def test_cross_lingual_zero_sparse_excluded():
    """한국어 질의는 영문 문서와 공유 토큰이 없다 → sparse 순위가 비고 dense 결과만 남는다."""
    res = retriever.hybrid_search("칩렛 인터커넥트", doc_type="tech")
    assert ids(res)[0] == "07-0001"
    assert retriever.hybrid_search("칩렛 인터커넥트", doc_type="tech", mode="sparse") == []


def test_score_metadata_and_k():
    res = retriever.hybrid_search("memory", doc_type="tech", k=2)
    assert len(res) == 2 and all(d.metadata["score"] > 0 for d in res)
    assert DOCS[0].metadata.get("score") is None  # 원본 문서 메타데이터 오염 없음


def test_index_cache_reused(index):
    assert list(index.glob("index/*/sparse.json")) and list(index.glob("index/*/chroma.sqlite3"))
    calls.clear()
    retriever.build_index(DOCS)
    assert calls == []  # 같은 문서 → 재인코딩 없이 캐시 로드
    retriever.build_index(DOCS[:3])
    assert calls == [3]  # 문서가 바뀌면 재색인
