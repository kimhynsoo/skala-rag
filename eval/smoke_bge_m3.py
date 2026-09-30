"""bge-m3 로컬 동작·속도 확인 (B1 사전 점검).

uv run python eval/smoke_bge_m3.py [--device mps|cpu]

확인 항목
1. 한국어 질의 → 영문 문서 교차언어 (dense 담당, 설계 R1)
2. 수치·식별자 정확일치 (sparse 담당, 설계 R2)
3. 700자 청크 인코딩 속도 → 코퍼스 약 627청크 색인 예상 시간
"""

import argparse
import resource
import time

from FlagEmbedding import BGEM3FlagModel

QUERIES = [
    ("교차언어", "칩렛 간 인터커넥트 대역폭 표준은?", 0),
    ("교차언어", "차세대 메모리 확장 인터페이스의 링크 속도", 1),
    ("정확일치", "특허 10-2532099", 2),
    ("정확일치", "128 GT/s", 1),
]
PASSAGES = [
    "UCIe 3.0 doubles the die-to-die bandwidth for chiplet interconnect, supporting up to 64 GT/s per lane "
    "for standard and advanced packages.",
    "CXL 4.0 is based on PCIe 7.0 and delivers 128 GT/s link speed for memory expansion and pooling "
    "across heterogeneous compute.",
    "주요 지식재산권: 등록 특허 10-2532099 (저전력 신경망 가속 회로), 10-2601877 (메모리 내 연산 구조).",
    "WSTS forecasts the global semiconductor market to grow driven by logic and memory demand for AI servers.",
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="mps")
    args = p.parse_args()

    t0 = time.perf_counter()
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=args.device != "cpu", devices=[args.device])
    print(f"[load] {time.perf_counter() - t0:.1f}s on {args.device}")

    q = model.encode_queries([x[1] for x in QUERIES], return_dense=True, return_sparse=True)
    d = model.encode_corpus(PASSAGES, return_dense=True, return_sparse=True)
    dense = q["dense_vecs"] @ d["dense_vecs"].T

    ok = 0
    for i, (kind, query, gold) in enumerate(QUERIES):
        sparse = [model.compute_lexical_matching_score(q["lexical_weights"][i], w) for w in d["lexical_weights"]]
        d_top, s_top = int(dense[i].argmax()), max(range(len(sparse)), key=sparse.__getitem__)
        ok += (d_top == gold) + (s_top == gold)
        print(f"[{kind}] {query}\n  dense  top={d_top} {'O' if d_top == gold else 'X'}  "
              f"scores={[round(float(x), 3) for x in dense[i]]}\n  sparse top={s_top} {'O' if s_top == gold else 'X'}  "
              f"scores={[round(x, 3) for x in sparse]}")
    print(f"[hit] {ok}/{len(QUERIES) * 2}")
    print(f"[query tokens] {model.convert_id_to_token(q['lexical_weights'])[3]}")

    chunks = [("CXL 4.0 delivers 128 GT/s link speed. " * 20)[:700]] * 64
    t0 = time.perf_counter()
    model.encode_corpus(chunks, batch_size=16, max_length=512, return_dense=True, return_sparse=True)
    per = (time.perf_counter() - t0) / len(chunks)
    print(f"[speed] {per * 1000:.0f} ms/chunk → 627청크 약 {per * 627:.0f}s")
    print(f"[memory] peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**3:.2f} GB")


if __name__ == "__main__":
    main()
