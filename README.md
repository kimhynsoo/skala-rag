# Subject
본 프로젝트는 AI 반도체 스타트업을 하드웨어(AI 칩 설계)·소프트웨어(AI 기반 반도체 설계·공정) 두 진영에서 선정하여, 창업자·시장성·제품/기술력·경쟁 우위·실적 관점에서 투자 가능성을 평가하는 **Supervisor** 패턴 기반으로 설계/개발한 프로젝트임.

> **결과** — 45개사 평가 → **투자 적격 2곳**: 1위 망고부스트코리아(DPU) 79.0점, 2위 디노티시아 72.0점 · 제출 trace `24e889d7ecf2`
>
> 이전 RAG 과제(고정 순서 파이프라인)는 [`rag-pjt`](https://github.com/kimhynsoo/skala-rag/tree/rag-pjt) 브랜치에 보존


## Overview
- Objective : 한 기업을 기술·시장·경쟁 관점에서 근거 기반으로 평가하고, 근거가 부족한 관점은 다시 조사해 투자 적격 여부를 판정
- Pattern : **Supervisor** — 평가 품질은 "근거가 충분한가"를 판단하고 부족한 관점을 다시 조사하는 데 달려 있고, 종료 조건·fallback을 한 곳에서 통제해야 하므로 선정
  - Orchestrator-Workers : 실행 전 1회 계획이라, 중간에 드러난 근거 부족을 되돌릴 수 없음
  - Agent-as-Tool · Swarm : 과제 범위에서 제외 (정적 흐름에선 도구 호출과 차이가 없고, Swarm은 재현성 보장이 어려움)
- 동적 처리 : 고정 순서와 다른 점
  - **순서** — 기존엔 `technology → market → competitor`가 엣지로 고정. 지금은 Supervisor가 매 라운드 State(수집된 관점·근거 충분도·실패·실행 횟수)를 보고 다음 노드(`next`)를 정함
  - **병렬** — 서로 독립인 기술·시장 분석은 동시에 실행
  - **재작업** — 세 관점이 모이면 근거가 부족한 관점만 골라 다시 조사시킴. 망고부스트코리아에서는 한 라운드는 "시장 규모·성장률 부족"으로 시장만, 다음 라운드는 "성능 수치 미확인"으로 기술만 재작업
  - **Hybrid 판단** — 필수 단계·재시도·상한은 코드 규칙이 강제하고(재현성), "재작업할지 투자 판단으로 넘어갈지"만 LLM이 판단
  - **실측** — 제출 실행에서 Supervisor 라우팅 17회, 에이전트 실행 technology 8 · market 8 · competitor 4회 중 재작업 8회. 기업마다 횟수가 다름


## Selected Technologies
- SW : AI 기반 반도체 설계·공정 SW — 디렉토리북 45개사 중 3곳(C01 디에스 후공정 불량 검출, C30 서클 주문형 반도체 디자인, C34 싸이프 소자 모델링). 모두 평가했으며 C01·C30 보류, C34 제외
- HW : AI 반도체 칩(NPU·DPU·AI 가속기) — IRDS·UCIe·CXL 기준값으로 성능을 정량 비교할 수 있고, 나머지 42개사가 해당


## Features
- PDF 자료 기반 정보 추출 : 디렉토리북 45개사 + 기술 로드맵·시장 보고서 15개 PDF(169쪽)
- Supervisor 동적 라우팅 : 관점별 근거 충분도 판단 → 부족한 관점만 병렬 재작업
- 확증 편향 방지 전략 : 투자 판정은 LLM이 아니라 코드 점수로만 내림. 보고서는 외부 출처 기관 3곳 이상·단일 기관 비중 50% 이하를 룰로 검사(평가 대상 기업의 자체 소개 자료는 계산에서 제외)하고, LLM Judge가 불리한 근거(미확인·열위·리스크) 누락을 검사
- 보고서 품질 평가 : Hybrid(룰 + LLM Judge)로 Groundedness·중립성·편향 통제를 판정. 미달 사유를 피드백으로 넣어 최대 2회 재작성, 그래도 미달이면 경고 후 종료
  - 제출 실행 : 1차 보고서가 중립성 미달("국내에서 **유일하게** DPU를 개발") → 피드백 반영 재작성 → 2차 통과(score 1.0, 인용 11건 모두 추적 가능, 외부 출처 7곳·최다 비중 30%)


## Tech Stack
- Framework : LangGraph, LangChain, Python 3.11
- LLM/Generator : gpt-4.1-mini
- LLM/Judge : gpt-4.1-mini (Supervisor 재작업 판단, 보고서 품질 평가)
- Retrieval : Chroma + bge-m3 dense/sparse RRF — Hit Rate@5 0.944, MRR@5 0.917 ([비교 실험](eval/results.md))
- Embedding : BAAI/bge-m3
- Observability : LangSmith + JSONL 결정 로그


## Agents
- Supervisor : 기업 1곳의 분석 구간을 통제. 하위 에이전트는 항상 Supervisor로 돌아오며 서로 직접 통신하지 않음
  1. step 상한 도달 → 투자 판단 (종료 보장)
  2. 기술 분석이 재시도 후에도 실패 → 보류 (기술력 없이 판단 불가). 시장·경쟁 실패는 미확인으로 진행
  3. 기술·시장 미수행·실패 → 병렬 실행
  4. 경쟁 미수행·실패 → 실행 (기술·시장 결과를 비교 기준으로 사용)
  5. 근거 부족 관점 존재 → LLM이 재작업 대상(복수 가능) 또는 투자 판단 선택. 응답이 무효면 규칙대로 전부 재작업
  6. 모두 충분하거나 재작업 상한 → 투자 판단
- 기술 요약 [RAG] : 기업 기술을 IRDS·UCIe·CXL 기준값과 대조. 재작업 시 Supervisor가 준 사유로 질의 재작성
- 시장성 평가 [RAG] : 시장 주장을 SIA·WSTS·KIET·OECD 자료와 대조
- 경쟁사 비교 : RAG + Tavily로 경쟁 제품 지표 비교
- 투자 판단 : 체크리스트 11문항 + 스코어카드 15항목을 LLM이 3회 채점 → 코드가 집계·판정
  - 기준 : 총점 70점 이상 + 기술력 평균 2.67 이상
  - 2.67 근거 : 기술 3항목 중 확인 가능한 2개가 기본점(3점) 이상이고 공개 자료로 확인 불가한 항목(2점 처리)이 1개까지인 경우를 허용 → (3+3+2)/3. 이전 과제의 3.0은 성능 지표가 비공개인 비상장 스타트업에 사실상 "확인 불가 0개"를 요구해, 적격성을 통과한 4곳이 모두 탈락했음
- 보고서 생성 : SUMMARY·REFERENCE 포함 투자 보고서(State만 사용, 신규 검색 없음)
- 품질 평가 : 룰 + LLM Judge → 통과 시 종료, 미달 시 피드백 재작성, 상한 초과 시 경고 종료


## State Schema
- 제어 vs 페이로드 분리 : 흐름 제어 필드(`next`, `step_count`, `max_steps`, `rework_reason`, `node_status`, `agent_attempts`, `last_error`)와 작업 산출물(`*_analysis`, `current_evidence`, `scorecard`)을 그룹으로 분리. 산출물은 Pydantic 스키마로 구조화하고 모든 수치에 `근거ID`를 붙임
- 관측성 위치 : 결정과 사유는 State가 아니라 외부 로그 `outputs/logs/{trace_id}.jsonl`(`trace_id, company_id, node, decision, reason, ts`)과 LangSmith에 기록. State에는 마지막 사유 1줄(`route_reason`)만
- 지속성 비용 : 기업이 바뀌면 작업 산출물과 제어 필드를 리셋. 검색 원문 전문은 `.cache/`에, State에는 발췌만 저장. 체크포인터(MemorySaver)는 바뀐 필드만 새 버전으로 저장
- 상관 : `trace_id` 하나를 State·JSONL 로그·LangSmith metadata·체크포인터 `thread_id`에 같이 사용
- 재개/복구 : 에이전트별 `node_status`(SUCCESS/FAILED)·`agent_attempts`(실행 횟수)·`last_error`로 무엇을 다시 실행할지 판단. MemorySaver 스냅샷과 외부 조사 캐시로 재실행 비용 절감
- 동시 처리 : 병렬 노드가 함께 쓰는 필드는 리듀서로 병합(`node_status`·`agent_attempts` → `merge_dict`, `current_evidence` → `merge_evidence`, `errors` → `operator.add`). 검색기는 Lock으로 직렬화, 동시 실행 최대 4개
- 종료 보장 : 에이전트별 재작업 1회, 기업별 Supervisor 6스텝, 보고서 재작성 2회 후 `end_with_warning`, `recursion_limit=3000`


## Architecture
실선은 고정 엣지, 점선은 State를 보고 정하는 조건부 엣지. `technology`·`market`·`competitor`는 모두 `supervisor`로만 돌아온다.

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	load(load)
	select(select)
	eligibility(eligibility)
	supervisor(supervisor)
	technology(technology)
	market(market)
	competitor(competitor)
	investment(investment)
	exclude(exclude)
	hold(hold)
	handle_error(handle_error)
	save(save)
	next_index(next_index)
	rank(rank)
	report(report)
	evaluator(evaluator)
	end_with_warning(end_with_warning)
	__end__([<p>__end__</p>]):::last
	__start__ --> load;
	competitor --> supervisor;
	eligibility -.-> exclude;
	eligibility -.-> handle_error;
	eligibility -.-> hold;
	eligibility -.-> supervisor;
	evaluator -.-> __end__;
	evaluator -.-> end_with_warning;
	evaluator -.-> report;
	exclude --> save;
	handle_error --> save;
	hold --> save;
	investment -.-> handle_error;
	investment -.-> save;
	load -.-> rank;
	load -.-> select;
	market --> supervisor;
	next_index -.-> rank;
	next_index -.-> select;
	rank --> report;
	report --> evaluator;
	save --> next_index;
	select --> eligibility;
	supervisor -.-> competitor;
	supervisor -.-> handle_error;
	supervisor -.-> investment;
	supervisor -.-> market;
	supervisor -.-> technology;
	technology --> supervisor;
	end_with_warning --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```


## Directory Structure
```text
├── data/            # 문서 풀: 원천 PDF 15개, manifest, 기업 레코드
├── agents/          # supervisor(조정 계층) · technology · market · competitor(하위 에이전트) · investment · report · evaluator
├── rag/             # PDF 파싱·청킹, bge-m3 하이브리드 검색
├── tools/           # 검색 도구, DART·Tavily 외부 조사
├── prompts/         # 역할별 프롬프트
├── eval/            # 임베딩 비교 실험 (골든셋 18문항)
├── outputs/         # report.pdf · report.md · evaluation_results.json · logs/{trace_id}.jsonl
├── tests/           # 단위·그래프 통합 테스트 (204개)
├── state.py · graph.py · obs.py · config.py
├── app.py           # 실행 스크립트
└── README.md
```


## Usage
준비물: [uv](https://docs.astral.sh/uv/), Google Chrome(PDF 변환), OpenAI·Tavily API 키

```bash
git clone https://github.com/kimhynsoo/skala-rag.git && cd skala-rag
uv sync && cp .env.example .env                   # OPENAI_API_KEY, TAVILY_API_KEY, LANGSMITH_* 입력
uv run python app.py --as-of 2026-10-13 --pdf     # 제출 실행 재현: 45개사 평가 + outputs/report.pdf
uv run python app.py --as-of 2026-10-13 --only C03  # 지정 기업만 (트레이스 확인용)
uv run python app.py --graph                      # 그래프 mermaid 출력
uv run pytest -q                                  # 테스트
```
- `--as-of 2026-10-13` : 적격성 판정의 외부 조사 결과(`data/processed/external_eligibility_results.json`, 2026-09-30 수집)는 기준일로부터 14일만 유효하다. 기준일 없이 2026-10-15 이후에 실행하면 모든 기업이 "확인 필요"로 보류된다. 최신 기준으로 다시 하려면 `uv run python -m tools.run_tavily_eligibility`로 외부 조사부터 갱신한다
- 첫 실행은 임베딩 모델(bge-m3) 다운로드와 검색 색인 생성으로 수 분이 더 걸린다
- 실행하면 `trace_id`가 출력되고, 끝에 라우팅·재작업 수 요약(`dynamic summary`)이 나온다. LLM 채점 변동으로 점수가 조금씩 다를 수 있으며, 제출 결과는 trace `24e889d7ecf2`(LangSmith 프로젝트 `skala-rag`, `tracing-*.png`)로 고정되어 있으므로 재실행 결과는 커밋하지 않는다


## Results
| 단계 | 기업 수 | 내용 |
|---|---|---|
| 적격성 (비상장·Series C 이하·Exit 전·AI 관련) | 45 | 적격 4 · 부적격 27(제외) · 확인 필요 14(보류) |
| 스코어카드 채점 | 4 | 망고부스트코리아 79.0 · 디노티시아 72.0 · 엑시나 62.7 · 아이디어스투실리콘 57.0 |
| **투자 적격** | **2** | 망고부스트코리아, 디노티시아. 나머지 2곳은 총점 70점 미만으로 보류 |

- 투자 보고서 : [`outputs/report.pdf`](outputs/report.pdf) (망고부스트코리아, 5쪽, SUMMARY·REFERENCE 포함)
- 전체 결과 : [`outputs/evaluation_results.json`](outputs/evaluation_results.json) · 결정 로그 : [`outputs/logs/24e889d7ecf2.jsonl`](outputs/logs/24e889d7ecf2.jsonl)


## Lessons Learned
1. **병렬화는 숨은 공유 자원을 드러낸다** — 기술·시장을 병렬로 돌리자 단일 값 필드 동시 쓰기 오류와, 검색기 첫 적재 경합(임베딩 모델 이중 적재로 정지)이 생겼다. 필드 제거·리듀서·Lock으로 해결
2. **피드백 없는 재생성은 같은 실수를 반복한다** — 같은 입력으로 보고서를 다시 쓰면 같은 금지 표현이 나왔다. 미달 사유를 피드백으로 넣은 뒤에야 통과
3. **편향 룰은 무엇을 셀지가 중요하다** — 기업 자체 소개 자료까지 출처로 세면 단일 출처 비중이 항상 50%를 넘었다. 외부 출처만 세도록 수정
4. **LLM 채점은 실행마다 흔들린다** — 기술력 기준이 3.0이던 직전 실행(trace `3806cd1fda1d`)에서 망고부스트코리아는 75.0점·보류였고 제출 실행에서는 79.0점이다. 판정은 코드로 고정해도 입력 점수 변동은 남으므로, 3회 채점 중앙값과 제출 trace 고정으로 관리


## Contributors
- 김세령 : 통합 리뷰(계획 대비 구현 검수), README·제출물 작성, 평가 보고서 검수
- 김현수 : Supervisor 설계·구현(Hybrid 라우팅), 그래프 재구성, 통합 테스트, 전체 실행·투자 기준 조정
- 박인우 : State Schema 설계, 관측성(trace_id·결정 로그·LangSmith), 체크포인터·실행 옵션
- 박세웅 : 하위 에이전트 병렬·재작업 대응, 질의 재작성, 검색기 동시성 처리
- 성재원 : 보고서 품질 평가(룰 + LLM Judge), 피드백 반영 재작성 루프·강제 종료
