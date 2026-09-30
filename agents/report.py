"""⑦ 보고서 생성 에이전트 — State만 사용 (신규 검색 금지). SUMMARY + 1~3장 + REFERENCE, 5장 이내."""

from state import State


def run(state: State) -> dict:
    """
    입력: evaluation_results, selected_company_id, ranking, source_document, as_of_date
    처리: selected_company_id가 있으면 evaluation_results에서 그 기업 레코드를 찾아 보고서 작성,
          없으면 '후보별 평가 요약' 구성 (설계: 투자 보고서 › 4)
          ※ State의 current_company·current_evidence 등은 마지막 후보 값이므로 사용하지 않는다
          3.1에 ranking 2·3위와 미선정 사유 요약
          REFERENCE는 본문에서 실제 인용한 근거 ID만, 레코드의 current_evidence에서 source_type별 가이드 표기 형식으로 생성
    출력: {"final_report": str (markdown)}
    """
    raise NotImplementedError
