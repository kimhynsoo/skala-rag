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
N_RETRIEVE_RETRY = 1
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
TECH_MIN = 3.0

EVALUATION_CRITERIA = {
    "weights": WEIGHTS,
    "items": ITEMS,
    "unknown_score": UNKNOWN_SCORE,
    "invest_threshold": INVEST_THRESHOLD,
    "tech_min": TECH_MIN,
}
