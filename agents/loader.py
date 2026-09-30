"""① 후보 적재 에이전트 — 01_기업정보.pdf를 1페이지=1기업 레코드로 구조화 추출 (청킹하지 않음)."""

from state import State


def run(state: State) -> dict:
    """
    입력: source_document
    처리: rag.parser.parse_company_pages() (bbox 컬럼 복원 → LLM 구조화 추출), 결과는 data/processed/companies.json 캐시
    출력: {"candidate_companies": [ {company_id, 기업명, 홈페이지, 설립일, ..., source_page}, ... ], "current_index": 0}
    """
    raise NotImplementedError
