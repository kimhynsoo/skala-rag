# AI Startup Investment Evaluation Agent
본 프로젝트는 **AI 반도체(Semiconductor)** 스타트업에 대한 투자 가능성을 자동으로 평가하는 에이전트를 설계하고 구현한 실습 프로젝트입니다.

## Overview
- Objective : 초격차 스타트업 1000+ 디렉토리북 시스템반도체 45개사를 대상으로 기술력·시장성·경쟁 우위·실적·창업자 관점의 투자 적합성 분석
- Method : LangGraph Multi-Agent, Agentic RAG (하이브리드 검색 + 근거 부족 시 질의 재작성·재검색)
- Tools : Tavily 웹서치, DART OpenAPI

## Features
- 다단 펼침면 PDF의 bbox 기반 컬럼 복원 → 기업당 1레코드 구조화 추출
- bge-m3 dense + sparse 하이브리드 검색 (RRF) — 한국어 질의 ↔ 영문 문서 교차언어 + 수치·식별자 정확일치
- 자격 요건(G1~G4) → 체크리스트 11문항 → 스코어카드 100점, 총점·판정은 코드로 고정
- 모든 수치에 근거 ID 연결, REFERENCE 자동 생성

## Tech Stack
- Framework : LangGraph
- LLM/Generator : TBD
- LLM/Judge : TBD
- Retrieval : FAISS + bge-m3 sparse (RRF) - Hit Rate@5 TBD, MRR@5 TBD
- Embedding : BAAI/bge-m3

## Agents
- 후보 적재 : 디렉토리북 45개사 구조화 추출
- 적격성 검증 : 비상장·Series C 이하·Exit 이전·AI 관련 (웹 + 규칙 + LLM)
- 기술 요약 [RAG] : IRDS·UCIe·CXL 로드맵 대비 기술 지표 평가
- 시장성 평가 [RAG] : SIA·WSTS·KIET·OECD 자료 기반 시장 규모·성장성
- 경쟁사 비교 : 기존 인덱스 재조회 + 웹서치
- 투자 판단 : 체크리스트·스코어카드 채점, 코드 집계 → 투자/보류/제외
- 보고서 생성 : SUMMARY + 3장 + REFERENCE (5장 이내)

## Architecture
```bash
uv run python app.py --graph   # mermaid 출력
```
(그래프 이미지)

## Directory Structure
```
├── data/raw/          # 문서 풀 (01~15 PDF, 169p)
├── agents/            # 에이전트별 모듈 (run(state) -> dict)
├── rag/               # 파싱·청킹(parser), bge-m3 하이브리드 검색(retriever)
├── prompts/           # 프롬프트 템플릿
├── outputs/           # 평가 결과·보고서
├── tests/             # 스켈레톤·흐름 테스트
├── docs/              # 환경 세팅·협업 계약·개발 계획
├── config.py          # 설계 확정 상수 (청킹·가중치·임계값)
├── state.py           # Graph State
├── graph.py           # 노드·엣지·라우터
└── app.py             # 실행 스크립트
```

## Usage
환경 세팅은 [docs/SETUP.md](docs/SETUP.md), 협업 규칙·데이터 구조는 [docs/CONTRACTS.md](docs/CONTRACTS.md), 개발 계획은 [docs/DEV_PLAN.md](docs/DEV_PLAN.md) 참고.
```bash
uv sync
cp .env.example .env   # API 키 입력
uv run python app.py --as-of 2026-09-30
uv run pytest -q
```

## Contributors
- 김세령 :
- 김현수 :
- 박세웅 :
- 박인우 :
- 성재원 :
