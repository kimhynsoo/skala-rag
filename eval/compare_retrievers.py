"""임베딩·검색 방식 비교 실험 (설계 3-6, B5).

uv sync --group eval
uv run python -m eval.compare_retrievers        → eval/results.md, eval/results.json

비교군 (모두 같은 청크·같은 doc_type 필터·top-k 5)
  1. bge-m3 dense            : hybrid_search(mode="dense")
  2. bge-m3 dense + sparse   : hybrid_search(mode="hybrid")  ← 채택안
  3. e5-base dense           : intfloat/multilingual-e5-base
  4. e5-base + Kiwi BM25     : e5 dense + 형태소 BM25, RRF 융합
정답 판정: 검색 청크가 정답 문서(doc_id)이고 answer_span과 30% 이상 겹치면 적중.
"""

import json
import tempfile
import time
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from config import RRF_WEIGHTS, TOP_K
from rag import retriever
from rag.parser import company_documents, load_corpus

HERE = Path(__file__).parent
E5 = "intfloat/multilingual-e5-base"
OVERLAP = 0.3


def overlap(span: str, chunk: str) -> float:
    """answer_span 글자 중 청크와 겹치는 비율."""
    blocks = SequenceMatcher(None, span, chunk, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks if b.size >= 5) / len(span)  # 5자 미만 우연 일치는 제외


def gold_ids(q: dict, docs: list) -> set[str]:
    return {d.metadata["chunk_id"] for d in docs
            if d.metadata["doc_id"] == q["doc_id"] and d.metadata["doc_type"] == q["doc_type"]
            and overlap(q["answer_span"], d.page_content) >= OVERLAP}


# ---------- 비교군 3·4: e5 (평가 전용, numpy 전수 검색) ----------

class E5Retriever:
    def __init__(self, docs, with_bm25: bool):
        import torch
        from sentence_transformers import SentenceTransformer

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.docs, self.model = docs, SentenceTransformer(E5, device=device)
        self.vecs = self.model.encode([f"passage: {d.page_content}" for d in docs], batch_size=16,
                                      normalize_embeddings=True, show_progress_bar=False)
        self.bm25 = None
        if with_bm25:
            from kiwipiepy import Kiwi
            from rank_bm25 import BM25Okapi

            self.kiwi = Kiwi()
            self.bm25 = BM25Okapi([self._tok(d.page_content) for d in docs])

    def _tok(self, text: str) -> list[str]:
        return [t.form.lower() for t in self.kiwi.tokenize(text) if not t.tag.startswith(("S", "J", "E"))] or ["_"]

    def search(self, query: str, doc_type: str, k: int = TOP_K) -> list[str]:
        pool = [i for i, d in enumerate(self.docs) if d.metadata["doc_type"] == doc_type]
        q = self.model.encode([f"query: {query}"], normalize_embeddings=True, show_progress_bar=False)[0]
        sims = self.vecs[pool] @ q
        rankings = {"dense": [pool[j] for j in np.argsort(-sims)[:retriever.CANDIDATES]]}
        if self.bm25:
            scores = self.bm25.get_scores(self._tok(query))[pool]
            rankings["sparse"] = [pool[j] for j in np.argsort(-scores)[:retriever.CANDIDATES] if scores[j] > 0]
        fused = retriever.rrf(rankings, RRF_WEIGHTS)[:k]
        return [self.docs[i].metadata["chunk_id"] for i in fused]


# ---------- 평가 ----------

def evaluate(name: str, search, golden: list[dict], golds: dict[str, set]) -> dict:
    ranks, latency = {}, []
    for q in golden:
        t0 = time.perf_counter()
        found = search(q["query"], q["doc_type"])
        latency.append(time.perf_counter() - t0)
        ranks[q["id"]] = next((i for i, c in enumerate(found, 1) if c in golds[q["id"]]), None)

    def metrics(ids):
        r = [ranks[i] for i in ids]
        return {f"Hit@{k}": sum(x is not None and x <= k for x in r) / len(r) for k in (1, 3, 5)} | {
            "MRR@5": sum(1 / x for x in r if x) / len(r)}

    types = sorted({q["type"] for q in golden}, key=[q["type"] for q in golden].index)
    return {"name": name, "all": metrics([q["id"] for q in golden]),
            "by_type": {t: metrics([q["id"] for q in golden if q["type"] == t]) for t in types},
            "latency_ms": 1000 * sum(latency) / len(latency), "ranks": ranks}


def main():
    golden = json.loads((HERE / "golden.json").read_text())
    docs = load_corpus() + company_documents(json.loads(Path("data/processed/companies.json").read_text()))
    golds = {q["id"]: gold_ids(q, docs) for q in golden}
    empty = [i for i, g in golds.items() if not g]
    assert not empty, f"정답 청크를 찾지 못한 문항 (골든셋 오류): {empty}"
    print(f"[golden] {len(golden)}문항, 문항당 정답 청크 {min(map(len, golds.values()))}~{max(map(len, golds.values()))}개 / 코퍼스 {len(docs)}청크")

    results, index_time = [], {}
    retriever.CACHE_DIR = Path(tempfile.mkdtemp())  # 캐시 없이 색인 시간 측정
    t0 = time.perf_counter()
    retriever.build_index(docs)
    index_time["bge-m3"] = time.perf_counter() - t0
    for name, mode in [("1. bge-m3 dense", "dense"), ("2. bge-m3 dense+sparse (채택안)", "hybrid")]:
        results.append(evaluate(name, lambda q, dt, m=mode: [d.metadata["chunk_id"] for d in
                                                             retriever.hybrid_search(q, dt, mode=m)], golden, golds))
    for name, bm25 in [("3. e5-base dense", False), ("4. e5-base + Kiwi BM25", True)]:
        t0 = time.perf_counter()
        e5 = E5Retriever(docs, with_bm25=bm25)
        index_time[name] = time.perf_counter() - t0
        results.append(evaluate(name, e5.search, golden, golds))

    lines = ["| 비교군 | Hit@1 | Hit@3 | Hit@5 | MRR@5 | 질의 지연 |", "|---|---|---|---|---|---|"]
    for r in results:
        a = r["all"]
        lines.append(f"| {r['name']} | {a['Hit@1']:.3f} | {a['Hit@3']:.3f} | {a['Hit@5']:.3f} | {a['MRR@5']:.3f} | {r['latency_ms']:.0f}ms |")
    types = list(results[0]["by_type"])
    lines += ["", "**유형별 MRR@5**", "", "| 비교군 | " + " | ".join(f"{t} ({sum(q['type'] == t for q in golden)})" for t in types) + " |",
              "|---|" + "---|" * len(types)]
    for r in results:
        lines.append(f"| {r['name']} | " + " | ".join(f"{r['by_type'][t]['MRR@5']:.3f}" for t in types) + " |")
    lines += ["", "**색인 시간** (" + str(len(docs)) + "청크): " + ", ".join(f"{k} {v:.1f}s" for k, v in index_time.items())]
    lines += ["", "**문항별 정답 순위** (— = top-5 밖)", "", "| 문항 | 유형 | " + " | ".join(r["name"].split(".")[0] for r in results) + " |",
              "|---|---|" + "---|" * len(results)]
    for q in golden:
        lines.append(f"| {q['id']} | {q['type']} | " + " | ".join(str(r["ranks"][q["id"]] or "—") for r in results) + " |")

    table = "\n".join(lines)
    print(table)
    (HERE / "results.md").write_text(f"# 검색 비교 실험 결과\n\n골든셋 {len(golden)}문항 / top-k {TOP_K} / 정답 판정: answer_span 30% 이상 겹침\n\n{table}\n")
    (HERE / "results.json").write_text(json.dumps({"index_time_s": index_time, "results": results}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
