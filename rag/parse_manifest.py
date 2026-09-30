"""A2 — data/raw/page_mapping.json(추출 시 생성) + 문서 메타데이터 → data/manifest.json

실행: uv run python -m rag.parse_manifest

url·pub_year가 None인 항목은 REFERENCE 표기에 필요하므로 아래 META에서 채운 뒤 다시 실행한다.
"""

import json

from config import DATA_DIR

IRDS = dict(publisher="IEEE", pub_year=2024, source_type="기관 보고서")

# doc_id → 메타데이터 (설계 2-1 적용 대상, CONTRACTS 3-9 sub_domain)
META = {
    "01": dict(doc_type="company", sub_domain=None,
               title="2025 초격차 스타트업 1000+ 프로젝트 디렉토리북 1권", publisher="창업진흥원", pub_year=2025,
               source_type="기관 보고서",
               url="https://www.kised.or.kr/synap/doc.html?fn=176102077249700.pdf&rs=/synap/result"),
    "02": dict(doc_type="tech", sub_domain="ai_computing", title="IRDS 2024 - More Moore", url=None, **IRDS),
    "03": dict(doc_type="tech", sub_domain="packaging", title="IRDS 2024 - Executive Packaging Tutorial Part 2",
               url=None, **IRDS),
    "04": dict(doc_type="tech", sub_domain="power", title="Power Electronics Roadmap 2024",
               publisher="APC / Automotive Council UK", pub_year=2024, source_type="기관 보고서", url=None),
    "05": dict(doc_type="tech", sub_domain="rf_sensor", title="IRDS 2024 - Outside System Connectivity",
               url=None, **IRDS),
    "06": dict(doc_type="tech", sub_domain="memory", title="IRDS 2024 - More Moore: Memory Technologies",
               url=None, **IRDS),
    "07": dict(doc_type="tech", sub_domain="interface", title="UCIe 3.0 White Paper", publisher="UCIe Consortium",
               pub_year=None, source_type="기관 보고서", url=None),
    "08": dict(doc_type="tech", sub_domain="interface", title="CXL 4.0 White Paper", publisher="CXL Consortium",
               pub_year=None, source_type="기관 보고서", url=None),
    "09": dict(doc_type="tech", sub_domain="materials", title="IRDS 2024 - Beyond CMOS", url=None, **IRDS),
    "10": dict(doc_type="tech", sub_domain="metrology", title="IRDS 2024 - Metrology", url=None, **IRDS),
    "11": dict(doc_type="tech", sub_domain="yield", title="IRDS 2024 - Yield Enhancement", url=None, **IRDS),
    "12": dict(doc_type="market", sub_domain=None, title="2026 State of the U.S. Semiconductor Industry",
               publisher="SIA", pub_year=2026, source_type="기관 보고서", url=None),
    "13": dict(doc_type="market", sub_domain=None, title="Spring 2026 Semiconductor Market Forecast",
               publisher="WSTS", pub_year=2026, source_type="기관 보고서", url="https://www.wsts.org"),
    "14": dict(doc_type="market", sub_domain=None, title="2026년 하반기 경제·산업 전망: 반도체산업",
               publisher="산업연구원(KIET)", pub_year=2026, source_type="기관 보고서", url=None),
    "15": dict(doc_type="market", sub_domain=None, title="Mapping the Semiconductor Value Chain",
               publisher="OECD", pub_year=2025, source_type="기관 보고서", url=None),
}


def build_manifest() -> list[dict]:
    mapping = json.loads((DATA_DIR / "raw" / "page_mapping.json").read_text(encoding="utf-8"))
    manifest, problems = [], []
    for e in mapping:
        doc_id = e["file"][:2]
        meta = META[doc_id]
        if not (DATA_DIR / "raw" / e["file"]).exists():
            problems.append(f"{e['file']}: data/raw에 파일 없음")
        problems += [f"{doc_id}: {k} 비어 있음" for k in ("url", "pub_year") if meta[k] is None]
        manifest.append({
            "doc_id": doc_id,
            "file": e["file"],
            **meta,
            "source_file": e["source"],
            "page_count": e["pages"],
            "page_map": {str(p["output_page"]): p["source_pdf_page"] for p in e["page_mapping"]},  # 추출 → 원본
        })

    out = DATA_DIR / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(m["page_count"] for m in manifest)
    print(f"saved: {out}  ({len(manifest)}개 문서, 합계 {total}p / 설계 169p)")
    if problems:
        print("[확인 필요]\n- " + "\n- ".join(problems))
    return manifest


if __name__ == "__main__":
    build_manifest()
