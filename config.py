"""설계 문서(RAG-DESIGN_울산캠퍼스_4반_5조)에서 확정한 상수. 값을 바꾸면 설계 문서도 함께 갱신한다."""

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
CACHE_DIR = ROOT / ".cache"

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")

# RAG (설계 2-3, 3-5)
EMBEDDING_MODEL = "BAAI/bge-m3"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
TOP_K = 5
# Supervisor·품질 평가 (Agent 과제: 종료 보장·재작업 상한)
MAX_REWORK = 1  # 에이전트별 재작업 상한 (최대 실행 = 1 + MAX_REWORK)
MIN_EVIDENCE = 2  # 관점별 최소 근거ID 수
MAX_SUPERVISOR_STEPS = 6  # 기업별 Supervisor 방문 상한 (정상 경로 최대 5회 + 여유 1)
MAX_REPORT_REVISIONS = 2  # 품질 미달 시 보고서 재생성 상한
MIN_PUBLISHERS = 3  # 편향 통제: 본문 인용 출처 기관 최소 수
MAX_SOURCE_SHARE = 0.5  # 편향 통제: 단일 기관 인용 비중 상한
MAX_CONCURRENCY = 4  # 병렬 노드 동시 실행 상한 (외부 API rate limit)
RRF_WEIGHTS = {"dense": 0.5, "sparse": 0.5}
EXCLUDED_PAGES = {"01_기업정보": [16, 20]}  # 텍스트 0자 이미지 전용 페이지

# 스코어카드 (투자 판단 기준 4)
WEIGHTS = {"창업자": 20, "시장성": 20, "제품/기술력": 30, "경쟁 우위": 15, "실적": 15}
ITEMS = {
    "창업자": ["A1", "A2", "A3"],
    "시장성": ["B1", "B2", "B3"],
    "제품/기술력": ["C1", "C2", "C3"],
    "경쟁 우위": ["D1", "D2", "D3"],
    "실적": ["E1", "E2", "E3"],
}
UNKNOWN_SCORE = 2  # 확인 불가 항목 점수

# 최종 판정 (투자 판단 기준 5)
INVEST_THRESHOLD = 70
# 기술력 최소 기준: 기술 3항목(C1·C2·C3) 중 확인 가능한 2개가 루브릭 기본점(3점: 문제 명시·시제품 TRL 5~7) 이상이고,
# 공개 자료로 확인 불가한 항목(UNKNOWN_SCORE)이 1개까지인 경우를 허용한다 → (3 + 3 + 2) / 3 = 2.67.
# 3.0이면 확인 불가가 하나라도 있을 때 다른 항목 4점이 필요해, 성능 지표가 비공개인 비상장 스타트업에
# 사실상 "확인 불가 0개"를 요구한다 (실측: 적격성 통과 4개사 모두 C3 확인 불가). 비교는 소수 둘째 자리 반올림 기준.
TECH_MIN = round((3 * 2 + UNKNOWN_SCORE) / 3, 2)

EVALUATION_CRITERIA = {
    "weights": WEIGHTS,
    "items": ITEMS,
    "unknown_score": UNKNOWN_SCORE,
    "invest_threshold": INVEST_THRESHOLD,
    "tech_min": TECH_MIN,
}
