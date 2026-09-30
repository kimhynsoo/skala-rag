"""문서 로딩 (설계 2-2 문서군별 차등 처리)."""

from pathlib import Path

from langchain_core.documents import Document


def parse_company_pages(pdf_path: Path) -> list[dict]:
    """01_기업정보: pymupdf 블록 bbox로 컬럼 복원 → 페이지당 1기업 레코드 (16·20쪽 제외)."""
    raise NotImplementedError


def load_corpus(data_dir: Path) -> list[Document]:
    """02~15: 700자/100자 청킹. metadata = doc_id, doc_type, sub_domain, title, publisher, pub_year, source_type, url, source_page, output_page."""
    raise NotImplementedError
