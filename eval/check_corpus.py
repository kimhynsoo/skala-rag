"""실제 코퍼스 색인·검색 점검 (B1·B2·B3).

uv run python -m eval.check_corpus   (루트에서 모듈로 실행해야 config를 import할 수 있다)

1. 청크 품질: 문서별 청크 수, chunk_id 중복, 필수 메타데이터, bge-m3 토큰 수 분포(512 초과 = 잘림)
2. 색인: 최초 색인 시간, 캐시 재로드 시간
3. 검색: 질의 유형별(교차언어·정확일치·필터) 상위 결과
"""

import time
from collections import Counter

from transformers import AutoTokenizer

from config import CHUNK_SIZE, EMBEDDING_MODEL
from rag import retriever
from rag.parser import company_documents, load_corpus

REQUIRED = ("chunk_id", "doc_id", "doc_type", "title", "publisher", "pub_year", "source_type", "source_page")

QUERIES = [
    ("교차언어", "칩렛 간 다이 투 다이 인터커넥트 대역폭", "tech", None),
    ("교차언어", "메모리 확장을 위한 캐시 일관성 인터페이스 링크 속도", "tech", "interface"),
    ("교차언어", "전력반도체 SiC GaN 효율 로드맵", "tech", "power"),
    ("정확일치", "UCIe 3.0 64 GT/s", "tech", None),
    ("정확일치", "CXL 4.0 128 GT/s", "tech", None),
    ("시장·한글", "한국 반도체 수출 전망", "market", None),
    ("시장·교차", "AI 반도체 시장 규모 성장률 AI semiconductor market size growth", "market", None),
]


def verify_chroma(path, docs):
    """새 클라이언트로 DB 파일을 다시 열어 적재 결과를 원본 청크와 대조한다 (영속성 포함)."""
    import json

    import chromadb

    col = chromadb.PersistentClient(path=str(path), settings=chromadb.Settings(anonymized_telemetry=False)) \
        .get_collection(retriever.COLLECTION)
    got = col.get(include=["documents", "metadatas", "embeddings"])
    src = {d.metadata["chunk_id"]: d for d in docs}
    meta_ok = all(m == {k: v for k, v in src[i].metadata.items() if v is not None} for i, m in zip(got["ids"], got["metadatas"]))
    text_ok = all(t == src[i].page_content for i, t in zip(got["ids"], got["documents"]))
    dims = {len(e) for e in got["embeddings"]}
    norms = [float((e ** 2).sum() ** .5) for e in got["embeddings"][:50]]
    sparse = json.loads((path / "sparse.json").read_text())
    print(f"  [Chroma 적재] 건수 {col.count()} / 원본 {len(docs)} | ID 일치 {set(got['ids']) == set(src)} | "
          f"본문 일치 {text_ok} | 메타데이터 일치 {meta_ok}")
    print(f"  [Chroma 적재] 임베딩 차원 {dims} | L2 노름 {min(norms):.3f}~{max(norms):.3f} (정규화) | "
          f"거리 {col.metadata.get('hnsw:space')} | sparse 가중치 {len(sparse)}건")


def main():
    t0 = time.perf_counter()
    import json
    from pathlib import Path

    docs = load_corpus() + company_documents(json.loads(Path("data/processed/companies.json").read_text()))
    print(f"[load] {len(docs)} chunks in {time.perf_counter() - t0:.1f}s")

    print("\n[1] 청크 품질")
    per_doc = Counter(d.metadata["doc_id"] for d in docs)
    print("  문서별 청크:", dict(sorted(per_doc.items())))
    ids = [d.metadata["chunk_id"] for d in docs]
    print(f"  chunk_id 중복: {len(ids) - len(set(ids))}")
    missing = Counter(k for d in docs for k in REQUIRED if d.metadata.get(k) in (None, ""))
    print(f"  필수 메타데이터 누락: {dict(missing) or '없음'}")
    chars = [len(d.page_content) for d in docs]
    print(f"  글자 수: 최소 {min(chars)} / 평균 {sum(chars) // len(chars)} / 최대 {max(chars)} (설정 {CHUNK_SIZE})")

    tok = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
    ntok = [len(tok(d.page_content)["input_ids"]) for d in docs]
    lens = sorted(ntok)
    over = [(d.metadata["chunk_id"], n) for d, n in zip(docs, ntok) if n > 512]
    print(f"  토큰 수: 중앙값 {lens[len(lens) // 2]} / p95 {lens[int(len(lens) * .95)]} / 최대 {lens[-1]} → 512 초과 {len(over)}건 {over[:5]}")

    print("\n[2] 색인")
    t0 = time.perf_counter()
    path = retriever.build_index(docs)
    print(f"  최초(또는 캐시) 색인: {time.perf_counter() - t0:.1f}s → {path}")
    verify_chroma(path, docs)
    t0 = time.perf_counter()
    retriever.build_index(docs)
    print(f"  재호출(캐시): {(time.perf_counter() - t0) * 1000:.0f}ms")

    print("\n[3] 검색 (상위 3)")
    for kind, q, doc_type, sub in QUERIES:
        t0 = time.perf_counter()
        res = retriever.hybrid_search(q, doc_type=doc_type, sub_domain=sub, k=3)
        ms = (time.perf_counter() - t0) * 1000
        print(f"  [{kind}] {q}" + (f"  (sub_domain={sub})" if sub else "") + f"  {ms:.0f}ms")
        for d in res:
            m = d.metadata
            print(f"     {m['chunk_id']:9s} {m['score']:.4f}  {m['title'][:38]:38s} | {d.page_content[:70].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main()
