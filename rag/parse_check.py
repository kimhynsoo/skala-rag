"""레인 A 점검·실행 도구.

  uv run python -m rag.parse_check page 1          # 01_기업정보 p.1 복원 텍스트 (LLM 없음)
  uv run python -m rag.parse_check extract         # 45개사 LLM 추출 → data/processed/companies.json
  uv run python -m rag.parse_check extract 3 7     # 특정 페이지만 다시 추출해 json에 덮어쓰기
  uv run python -m rag.parse_check extract 3 --image   # 페이지 이미지도 함께 넣어 재추출
  uv run python -m rag.parse_check subdomain       # sub_domain만 다시 분류해 json 갱신
  uv run python -m rag.parse_check companies       # 추출 결과 요약표 + 빈 필드 경고
  uv run python -m rag.parse_check corpus          # 02~15 청크 수·길이·메타데이터 누락
"""

import argparse
import json
from collections import Counter

import pymupdf
from dotenv import load_dotenv

from agents.loader import CACHE
from config import DATA_DIR
from rag.parser import classify_sub_domains, load_corpus, parse_company_pages, spread_text

SOURCE = DATA_DIR / "raw" / "01_기업정보.pdf"


def cmd_page(n: int):
    with pymupdf.open(SOURCE) as pdf:
        print(spread_text(pdf[n - 1]))


def cmd_extract(pages: list[int], image: bool):
    new = parse_company_pages(SOURCE, only_pages=set(pages) if pages else None, with_image=image)
    old = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() and pages else []
    merged = {c["company_id"]: c for c in old} | {c["company_id"]: c for c in new}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    records = [merged[k] for k in sorted(merged)]
    CACHE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    fails = [c["company_id"] for c in records if c.get("추출오류")]
    print(f"saved: {CACHE} ({len(records)}건, 실패 {fails or '없음'})")


def cmd_subdomain():
    records = classify_sub_domains(json.loads(CACHE.read_text(encoding="utf-8")))
    CACHE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in records:
        print(f"{c['company_id']:<4} {str(c.get('기업명'))[:16]:<18} {str(c.get('sub_domain')):<13} "
              f"{c.get('sub_domain_근거', '')[:60]}")


def cmd_companies():
    records = json.loads(CACHE.read_text(encoding="utf-8"))
    must = ("기업명", "대표자명", "메인아이템", "주요구성원", "사업Point", "혁신성", "개발진척도")
    print(f"{'ID':<4} {'p':>3} {'기업명':<18} {'sub_domain':<13} {'매출(천원)':>12} {'상태':<5} "
          f"{'투자':>3} {'등록/출원':>7} {'TRL':>3}  빈 필드")
    for c in records:
        if c.get("추출오류"):
            print(f"{c['company_id']:<4} {c['source_page']:>3} 추출 실패: {c['추출오류'][:60]}")
            continue
        rev, ip = c["매출액"], c["지식재산권"]
        empty = [k for k in must if not c.get(k)]
        print(f"{c['company_id']:<4} {c['source_page']:>3} {c['기업명'][:16]:<18} {str(c['sub_domain']):<13} "
              f"{str(rev['국내']):>12} {rev['상태']:<5} {len(c['투자유치이력']):>3} "
              f"{len(ip['등록']):>3}/{len(ip['출원']):<3} {str(c['TRL']):>3}  {', '.join(empty)}")
    print(f"\n총 {len(records)}건 (설계 45건)")


def cmd_corpus():
    docs = load_corpus()
    lens = [len(d.page_content) for d in docs]
    print(f"청크 {len(docs)}개, 길이 최대 {max(lens)} / 평균 {sum(lens) // len(lens)}자")
    print("문서별:", dict(sorted(Counter(d.metadata['doc_id'] for d in docs).items())))
    keys = ("doc_id", "doc_type", "title", "publisher", "pub_year", "source_type", "url", "source_page")
    missing = Counter(k for d in docs for k in keys if d.metadata.get(k) is None)
    print("메타데이터 None:", dict(missing) or "없음")


if __name__ == "__main__":
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["page", "extract", "subdomain", "companies", "corpus"])
    p.add_argument("pages", nargs="*", type=int)
    p.add_argument("--image", action="store_true")
    a = p.parse_args()
    {"page": lambda: cmd_page(a.pages[0] if a.pages else 1),
     "extract": lambda: cmd_extract(a.pages, a.image),
     "subdomain": cmd_subdomain,
     "companies": cmd_companies,
     "corpus": cmd_corpus}[a.cmd]()
