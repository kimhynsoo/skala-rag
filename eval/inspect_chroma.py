"""Chroma에 실제로 적재된 청크를 문서별로 순서대로 본다.

uv run python -m eval.inspect_chroma              # 문서별 청크 수·길이 요약
uv run python -m eval.inspect_chroma 08           # 08번 문서 청크 전체 (경계·겹침 표시)
uv run python -m eval.inspect_chroma 14 --full    # 본문을 자르지 않고 출력
"""

import argparse
from collections import defaultdict
from pathlib import Path

import chromadb

from config import CACHE_DIR
from rag.retriever import COLLECTION


def latest_index() -> Path:
    return max((CACHE_DIR / "index").iterdir(), key=lambda p: p.stat().st_mtime)


def overlap_len(prev: str, cur: str, max_len: int = 200) -> int:
    """앞 청크의 끝과 현재 청크의 시작이 겹치는 글자 수 (청크 중첩)."""
    return next((k for k in range(min(max_len, len(prev), len(cur)), 9, -1) if prev.endswith(cur[:k])), 0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("doc_id", nargs="?", help="문서 번호 (예: 08). 없으면 요약만")
    p.add_argument("--full", action="store_true", help="본문 전체 출력")
    args = p.parse_args()

    path = latest_index()
    col = chromadb.PersistentClient(path=str(path), settings=chromadb.Settings(anonymized_telemetry=False)) \
        .get_collection(COLLECTION)
    got = col.get(include=["documents", "metadatas"])
    rows = sorted(zip(got["ids"], got["documents"], got["metadatas"]))
    print(f"[index] {path.name} · 총 {col.count()}청크\n")

    if not args.doc_id:
        by_doc, titles = defaultdict(list), {}
        for _, text, m in rows:
            by_doc[m["doc_id"]].append(len(text))
            titles[m["doc_id"]] = m.get("title", "")
        print(f"{'doc':4s} {'청크':>4s} {'평균':>5s} {'최소':>4s} {'최대':>4s}  제목")
        for doc, lens in sorted(by_doc.items()):
            print(f"{doc:4s} {len(lens):4d} {sum(lens) // len(lens):5d} {min(lens):4d} {max(lens):4d}  {titles[doc][:45]}")
        return

    doc_rows = [r for r in rows if r[2]["doc_id"] == args.doc_id]
    if not doc_rows:
        raise SystemExit(f"doc_id {args.doc_id} 없음")
    m0 = doc_rows[0][2]
    print(f"{m0.get('title')} ({m0.get('publisher')}, {m0.get('pub_year')}) · {len(doc_rows)}청크   «…» = 앞 청크와 겹친 부분\n")
    prev = ""
    for cid, text, m in doc_rows:
        ov = overlap_len(prev, text) if prev else 0
        print(f"━━ {cid} ━━ p.{m.get('source_page')} (추출 p.{m.get('output_page')}) · {len(text)}자"
              + (f" · 앞 청크와 {ov}자 겹침" if ov else ""))
        body = text if args.full or len(text) <= 400 else text[:250] + "\n… (중략) …\n" + text[-120:]
        if ov:  # ov ≤ 200 < 250이라 잘린 본문에도 겹친 부분이 온전히 남아 있다
            body = f"«{body[:ov]}»{body[ov:]}"
        print("   " + body.replace("\n", "\n   ") + "\n")
        prev = text


if __name__ == "__main__":
    main()
