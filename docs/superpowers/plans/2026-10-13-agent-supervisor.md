# Supervisor 패턴 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **자기 레인의 Task만 수행한다.**

**Goal:** 기업 1곳을 분석하는 구간을 고정 순서(`technology → market → competitor`)에서 **Supervisor가 State를 보고 동적으로 라우팅·재작업 지시**하는 구조로 바꾸고, 보고서 뒤에 **품질 평가 루프**를 붙인다.

**Architecture:** 외부 루프(45개사 순회)·적격성·투자 판단·순위·보고서 생성은 그대로 둔다. `eligibility(적격) → supervisor ⇄ {technology, market, competitor} → investment`로 바꾼다. Supervisor는 Hybrid다. 규칙(코드)이 필수 단계·실패 재시도·상한을 강제하고, LLM이 "근거 부족 관점을 재작업할지, 투자 판단으로 넘어갈지"를 판단한다. 보고서 뒤에 `evaluator`(룰+LLM Judge)를 붙이고 미달이면 미달 사유를 피드백으로 넣어 `report`를 다시 쓴다. 결정 로그는 State가 아니라 `outputs/logs/{trace_id}.jsonl`과 LangSmith로 보낸다.

**Tech Stack:** LangGraph 1.2 (`StateGraph`, `add_conditional_edges`, `MemorySaver`), LangChain 1.x (`init_chat_model`, `with_structured_output`), Pydantic, LangSmith, pytest, uv

**Spec:** 과제 노션 (A. Agent Pattern, B. Mandatory Items, C. State Schema, D. 보고서 품질 평가, 산출물·평가 항목), 강의 자료 `4) 생성형AI_7.AI Agent 설계 및 구축` 4장, 예시 코드 `ai-service/langgraph-v1/12-Pattern/02-Supervisor-Basic.ipynb`, `07-Supervisor-Advanced.ipynb`

**검증 상태:** 이 문서의 코드는 별도 worktree에서 전부 적용해 `uv run pytest -q` **201 passed**(+ 피드백 반영 변경은 별도 적용해 통과, 합치면 202개)를 확인했고, `app.py --only C03`로 실제 실행해 확인했다 (§ 실측 결과).

---

## 팀 배정

| 레인 | 담당 | 역할 | Task | 작업 브랜치 |
|---|---|---|---|---|
| **A** | **김현수** | 사전 준비·Supervisor·Graph·통합 | P → 1 → 2a → 2b → 7-1 | `feat/agent-a-supervisor` |
| **B** | **박인우** | State·관측성·실행 옵션·LangSmith 트레이스 | 0 → 6 → 7-2 | `feat/agent-b-state` |
| **C** | **박세웅** | 하위 에이전트 병렬·재작업 대응·전체 실행 | 3 → 7-3 → 7-4 | `feat/agent-c-workers` |
| **D** | **성재원** | 보고서 품질 평가·피드백 반영 재작성 | 4 → 5 | `feat/agent-d-evaluator` |
| **E** | **김세령** | 통합 리뷰·README·평가 보고서·제출 | 7-0 → 7-R → 7-5 → 7-6 → 7-7 | `feat/agent-e-docs` |

**브랜치 흐름:** `main`(이전 RAG 과제) → Task P에서 `rag-pjt`로 보존 → 각자 `main`에서 레인 브랜치 생성 → Task마다 레인 브랜치를 `main`에 `--no-ff` 머지 → 최종 `main` 제출.

## AI에게 일 시키는 방법 (각자 복사해서 사용)

자기 AI(Claude Code 등)를 `skala-rag` 폴더에서 열고 아래 프롬프트를 그대로 붙여 넣는다. `{레인}`, `{이름}`만 바꾼다.

```text
나는 skala-rag 팀의 {레인} 레인 담당 {이름}이다.
docs/superpowers/plans/2026-10-13-agent-supervisor.md 를 끝까지 읽고, "팀 배정" 표에서 내 레인의 Task만 번호 순서대로 수행해라.

규칙:
1. 브랜치 전략: 각자 자기 레인 브랜치("팀 배정" 표의 브랜치 열)에서 작업하고, Task가 끝날 때마다 main으로 합친다. 최종 결과는 main이다. 이전 RAG 과제는 rag-pjt 브랜치에 보존되어 있으니 rag-pjt는 건드리지 않는다. Task P가 끝나기 전(origin에 rag-pjt 브랜치와 계획 커밋이 없으면)에는 아무것도 하지 않고 "Task P 공통 시작 조건" 명령으로 기다린 뒤 내 브랜치를 만든다.
2. 각 Task의 "선행 조건" 명령을 먼저 실행한다. 조건이 아직 충족되지 않으면 그 명령의 until 루프로 기다린다 (다른 레인 Task 대신 하지 말 것).
3. 문서의 코드 블록을 그대로 쓴다. "찾기/바꾸기"는 찾기 문자열이 파일에 정확히 1번 있는지 확인하고 바꾼다. 없으면 멈추고 나에게 보고한다.
4. "소유 파일" 표에서 내 레인 파일만 수정한다.
5. 각 Task 끝에서 `uv run pytest -q` 가 전부 통과해야 커밋한다. 실패하면 고치고, 남의 파일 때문에 실패하면 멈추고 보고한다.
6. 커밋 메시지는 문서에 적힌 그대로 쓴다 (다른 레인이 이 메시지로 선행 조건을 확인한다). AI co-author 트레일러를 붙이지 않는다.
7. 커밋 후 각 Task 끝의 명령대로 내 브랜치를 push하고 main에 `--no-ff`로 합쳐 push한 뒤, 내 브랜치를 최신 main으로 맞춘다. main에서 pytest가 실패하면 main을 push하지 않는다.
8. 체크박스(- [ ])를 하나씩 진행하고, 끝나면 무엇을 했는지와 pytest 결과를 나에게 요약한다.
```

---

## 최종 아키텍처

범례: `★` 신규 · `✎` 수정 · `[A]~[E]` 담당 레인 · 표시 없음 = 그대로

```
                              START
                                │
                         load (45개사 적재) ✎[B] --only 필터
                                │
                ┌──────────► select (기업 선택 · State 리셋) ✎[A] 제어필드 리셋
                │               │
                │          eligibility (G1~G4)
                │        ┌──────┼──────────┐
                │     부적격   확인필요     적격
                │        │      │          │
                │     exclude  hold        ▼
                │        │      │   ╔══════════════════════════════════════════════╗
                │        │      │   ║  ★ SUPERVISOR [A]  Hybrid (규칙 가드 + LLM)     ║
                │        │      │   ║  next 결정 → add_conditional_edges            ║
                │        │      │   ║                                              ║
                │        │      │   ║  규칙 ① step ≥ max_steps ────► investment     ║
                │        │      │   ║  규칙 ② 기술 실패 + 재시도 소진 ► handle_error ║
                │        │      │   ║  규칙 ③ 기술·시장 미수행/실패 ─► 병렬 실행    ║
                │        │      │   ║  규칙 ④ 경쟁 미수행/실패 ──────► competitor   ║
                │        │      │   ║  LLM  ⑤ 근거 부족 관점 재작업 vs investment  ║
                │        │      │   ║  규칙 ⑥ 충분 or 상한 도달 ─────► investment   ║
                │        │      │   ╚═══╤════════╤════════╤═══════════════▲════════╝
                │        │      │       │ 병렬    │ 병렬    │                │
                │        │      │       ▼        ▼        ▼                │ 하위 에이전트는
                │        │      │  technology  market  competitor          │ supervisor와만 통신
                │        │      │    ✎[C]      ✎[C]     [C]                │ (rework_reason →
                │        │      │       └────────┴────────┴────────────────┘  질의 재작성)
                │        │      │        ★ guarded_worker [A]
                │        │      │        agent_attempts +1 · node_status SUCCESS/FAILED
                │        │      │                  │
                │        │      │             investment (코드 채점·판정)
                │        │      │                  │
                │        └──────┴──► save ◄────────┘ ◄── handle_error (보류)
                │                    │
                └──── 남음 ◄── next_index
                                     │ 소진
                                   rank (적격 중 1위)
                                     │
                       ┌────────► report ✎[D] 미달 사유 피드백 반영 재작성
                       │             │
                       │      ╔══════▼═══════════════════════════════╗
                       │      ║  ★ EVALUATOR [D]  Hybrid (1안 + 2안)  ║
                       │      ║  룰: 근거ID 추적 · 금지표현 ·          ║
                       │      ║      출처 ≥3곳 · 단일출처 ≤50%         ║
                       │      ║  LLM Judge: EvaluationResult 체크리스트 ║
                       │      ╚══════╤═══════════════════════════════╝
                       │   미달 &    │ 통과          │ 미달 & 재생성 2회 소진
                       └── 재생성<2 ─┤               ▼
                                     ▼        ★ end_with_warning [D]
                                    END ◄──────────┘
```

그래프 바깥 [B]:

```
trace_id ─┬─ State.trace_id
          ├─ outputs/logs/{trace_id}.jsonl   ★ obs.log_decision {trace_id, company_id, node, decision, reason, ts}
          ├─ MemorySaver thread_id            ★ 단계별 State 스냅샷 (재개·디버깅)
          └─ LangSmith run metadata           ★ tracing-1.png, tracing-2.png …

종료 상한 ★: 에이전트별 재작업 MAX_REWORK=1 · 기업별 max_steps=6 · 보고서 재생성 MAX_REPORT_REVISIONS=2 · recursion_limit=3000
동시성   ★: node_status·agent_attempts = merge_dict 리듀서 · max_concurrency=4 · 검색기 Lock
```

| 현재 | 변경 후 |
|---|---|
| `technology → market → competitor` 순서 고정 | Supervisor가 매 라운드 State를 보고 `next` 결정 |
| 각 에이전트가 스스로 재시도 (`route_retry`) | Supervisor가 판단해서 근거 부족 관점만 재작업 지시 (`rework_reason`) |
| 순차 실행 | 기술·시장 병렬, 재작업도 여러 관점 병렬 |
| `report → END` | `report → evaluator ⟲ → END / end_with_warning` |
| 결정 로그 없음 | trace_id + JSONL + LangSmith + MemorySaver |

---

## 과제 요구사항 체크리스트 (노션 사진 1~9 전체 대조)

| 출처 | 요구 | 구현 | Task |
|---|---|---|---|
| A | Supervisor / Orchestrator 중 택일 | Supervisor | 1 |
| A | Agent-as-Tool·Swarm 고려 안 함 | README Pattern 선정 이유에 제외 사유 기재 | 7 |
| B-Supervisor | 하위 에이전트는 Supervisor와만 통신, 직접 통신 금지 | worker → `supervisor` 엣지만 존재 | 2a |
| B-Supervisor | State(수집된 관점, 근거 충분도)에 따라 `add_conditional_edges` 분기, 순서 하드코딩 금지 | `supervisor.route` → `state["next"]` | 1, 2a |
| B-Supervisor | 근거 충분성 평가 후 보고서 진행, 스텝 수 고정 금지 | `sufficient()` + LLM 판단 → `investment` | 1 |
| B-Supervisor | 근거 부족 시 해당 하위 에이전트에 재작업 요청 | `rework_reason` → `build_query`·프롬프트 | 1, 3 |
| C | 제어 vs 페이로드 분리 | ② 흐름 제어 그룹 vs ③ 작업 산출물 그룹 | 0 |
| C | 관측성 위치 (결정·사유) | `obs.log_decision` JSONL + LangSmith, State엔 `route_reason` 1줄 | 0, 6 |
| C | 지속성 비용 | 기업 전환 시 리셋, 원문은 `.cache`, MemorySaver는 변경 채널만 저장 | 0, 2a |
| C | 상관 (trace_id) | State·로그·LangSmith metadata·thread_id 동일 키 | 0, 6 |
| C | 재개/복구 (상태·에러·재시도) | `node_status`, `agent_attempts`, `last_error`, `errors`, MemorySaver | 0, 2a, 6 |
| C | 동시 처리 (Reducer) | `merge_dict`, `merge_evidence`, `operator.add`, 검색기 Lock | 0, 3 |
| C | 종료 보장 (Step/반복 상한) | `max_steps`, `MAX_REWORK`, `MAX_REPORT_REVISIONS`, `recursion_limit` | 0, 1, 5 |
| C-Sample | `PerspectiveResult(view, findings, sources)` 구조화 산출물 | 기존 `schemas.TechnologyAnalysis` 등 + `근거ID` | 기존 |
| C-Sample | `eval_result: EvalVerdict \| None` | `eval_result` (EvaluationResult + score) | 0, 5 |
| C-Sample | `trace_id`, `step_count`, `node_status`, `last_error` | 동일 이름으로 반영 | 0 |
| C-Sample | 결정 로그 `{trace_id, node, decision, reason, ts}` 외부 적재 | `obs.log_decision` (+company_id) | 0 |
| D | 품질 평가 노드 필수, 미달 시 Loop | `evaluator` → 미달 사유를 피드백으로 `report` 재작성 | 5, 2b |
| D | Groundedness·중립성·편향 통제 | 룰 3종 + LLM Judge 3종 | 4, 5 |
| D | 평가 방식 3안(Hybrid) | 룰 AND Judge | 4, 5 |
| 산출물 1 | Branch로 기존 작업과 구분 | 이전 RAG 과제는 `rag-pjt` 브랜치에 보존, 이번 Agent 과제는 `main`에서 진행 | P |
| 산출물 1 | README 핑크 항목 (Pattern·동적 처리·SW/HW 선정 기술·State Schema 7항목) | README 템플릿 (E) | 7 |
| 산출물 1 | Contributors는 개인 수행 역할, PM·PL 제외 | README 템플릿 | 7 |
| 산출물 2 | LangSmith Tracing 캡처, 여러 장이면 `tracing-1.png`, `tracing-2.png` | B 캡처 | 7 |
| 산출물 3 | 평가 보고서: 지난 보고서와 같은 구성, 최대 10장 | `outputs/report.pdf` 쪽수 확인 | 7 |
| 제출 | `Agent_울산캠퍼스_4반_김세령+김현수+박세웅+박인우+성재원.zip` (Git Link + PNG + PDF), 반별 Slack thread | E | 7 |
| 평가 | 동적 동작 실증: Supervisor 라우팅/재작업 수 | `obs.summarize` → 실행 끝에 출력, README 기재 | 0, 6, 7 |
| 평가 | 실행 결과 재현성: 보고서 생성, 무한 루프 없이 종료, trace와 비교 | 상한 + trace_id를 README에 기재 | 7 |
| 평가 | Output 보고서: SUMMARY·REFERENCE | 기존 `report.py` 유지 | 기존 |

## 강의 자료·예시 코드 정렬

| 강의/예시 | 이 프로젝트 |
|---|---|
| `02-Supervisor-Basic`: `class RouteResponse(BaseModel): next: Literal[...]`, `llm.with_structured_output(RouteResponse)` | `supervisor.RouteResponse(next: list[Literal[...]], reason)` 동일 방식. 병렬 위임을 위해 리스트로 확장 |
| `get_next(state) -> state["next"]` + `add_conditional_edges("Supervisor", get_next, conditional_map)` | `supervisor.route` + `add_conditional_edges("supervisor", supervisor.route, [...])` |
| 멤버 → Supervisor 엣지 (`for member in members: add_edge(member, "Supervisor")`) | `for w in (technology, market, competitor): add_edge(w, "supervisor")` |
| `workflow.compile(checkpointer=MemorySaver())`, `configurable={"thread_id": ...}` | `build_graph(checkpointer=MemorySaver())`, `thread_id = trace_id` |
| `07-Supervisor-Advanced`: `EvaluationResult` bool 체크리스트 + `issues`, `build_criteria_from_schema()`로 프롬프트 생성, `compute_score()` | `evaluator.EvaluationResult` + `build_judge_prompt()` (필드 description → 체크리스트) + `score` |
| `build_supervisor_review_section()` — 규칙을 코드 상수에서 생성 | `supervisor.build_system_prompt()` — `MAX_REWORK`, `MIN_EVIDENCE` 상수에서 생성 |
| `MAX_RETRIES` 초과 → `END_WARNING` → `EndWithWarning` 노드 | `MAX_REPORT_REVISIONS` 초과 → `end_with_warning` 노드 |
| `07-Supervisor-Advanced` 피드백 루프 (`issues`·`retry_instruction`을 Writer에 전달), 강의 3-2 Evaluator-Optimizer | `eval_result.issues` → `report`의 LLM 입력 `품질평가피드백` |
| 강의 4-2-1 SupervisorState: `next`, `step_count`, `max_steps`, `status`, `results`, `errors` | `next`, `step_count`, `max_steps`, `node_status`(에이전트별 SUCCESS/FAILED), `errors`, `last_error` |
| 강의 4-2-1 Error-aware: `last_error {node, type, message, ts}` | `errors[]`에 `{company_id, stage, type, error, ts}`, Supervisor가 `last_error`로 요약 |
| 강의 4-2-1 "Supervisor는 한 번에 한 워커라 `operator.add`로 충분, Orchestrator는 동시 쓰기라 커스텀 리듀서 필수" | 병렬 위임을 하므로 `merge_dict` 커스텀 리듀서 적용 |
| 강의 4-4-2 Fan-out: Reducer·Checkpointer·`max_concurrency`, 부분 실패 처리 | `merge_dict`, `MemorySaver`, `max_concurrency=4`, 실패 관점만 재시도 |
| 강의 3-2 Control Strategy: Rule(재현성) vs Judge(열린 판단), Max iteration·fallback 필수 | 규칙 가드 + LLM 판단, LLM 무효 시 규칙 정책 fallback |
| 강의 3-2 Router vs Supervisor: 실행 후 Supervisor로 복귀, "충분한가"를 스스로 판단 | worker → supervisor 복귀, `sufficient()` + LLM |
| 예시 `logging.langsmith("CH12-PATTERN")` (langchain_teddynote) | 미설치 패키지라 `.env`의 `LANGSMITH_TRACING/API_KEY/PROJECT`로 동일 효과 |

**의도적 차이 (README에 적는다):**
- 강의 Supervisor는 매 스텝 LLM이 라우팅한다. 여기서는 필수 단계와 상한을 코드가 강제하고, 판단이 필요한 재작업 여부만 LLM에 맡긴다. 이유는 재현성(평가 10점)과 비용(45개사)이다.

---

## 소유 파일 (다른 레인은 수정 금지)

| 레인 | 파일 |
|---|---|
| A 김현수 | `agents/supervisor.py`(신규), `graph.py`, `tests/conftest.py`(신규), `tests/test_supervisor.py`(신규), `tests/test_graph_flow.py`(신규), `tests/test_skeleton.py` |
| B 박인우 | `state.py`, `config.py`, `obs.py`(신규), `app.py`, `agents/loader.py`, `.env.example`, `tests/test_state.py`(신규) |
| C 박세웅 | `agents/_rag_utils.py`, `agents/technology.py`, `agents/market.py`, `rag/retriever.py`, `prompts/technology.md`, `prompts/market.md`, `tests/test_rag_agents.py` |
| D 성재원 | `agents/evaluator.py`(신규), `tests/test_evaluator.py`(신규), `agents/report.py`, `prompts/report.md` |
| E 김세령 | `README.md`, 제출 zip (코드 파일은 수정하지 않고 리뷰만 한다. 문제를 찾으면 해당 레인 담당에게 알린다) |

## 의존성과 머지 순서 (총 3시간)

```
0:00  A: Task P (5분: rag-pjt 보존 + 계획 push) ─→ 전원 시작
0:05 ─┬─ B: Task 0 (15분) ─push─┬─→ B: Task 6 (코딩 즉시, push는 2a 이후)
      ├─ C: Task 3 (의존 없음) ──┼─push─┐
      ├─ D: Task 4 (의존 없음) ──┼──────┼─→ D: Task 5 (Task 0 필요) ─push─┐
      ├─ A: Task 1 테스트 작성 ──┴─→ Task 1 ─push─→ Task 2a (0·1·3 필요) ─push─→ Task 2b (5 필요) ─→ Task 7
      └─ E: 7-0 README 초안 ─→ 7-R 머지마다 리뷰 ──────────────────────────────→ 7-5·7-6·7-7
```

| Task | 담당 | 선행 커밋 (origin에 있어야 push 가능) | 커밋 메시지 (그대로 사용) |
|---|---|---|---|
| P | A (계획 파일 보유자) | 없음 | `docs: [공통] Agent 과제 Supervisor 전환 계획` (+ `rag-pjt` 브랜치 push) |
| 0 | B | P | `feat: [B] Supervisor용 State 제어 필드·종료 상한·결정 로그 추가` |
| 1 | A | 0 | `feat: [A] Hybrid Supervisor 라우팅 판단 추가` |
| 3 | C | 없음 | `feat: [C] Supervisor 재작업 사유 반영·병렬 실행 대응` |
| 4 | D | 없음 | `feat: [D] 보고서 품질 평가 룰 검사 추가` |
| 2a | A | 0, 1, 3 | `feat: [A] 고정 순서를 Supervisor 동적 라우팅으로 교체` |
| 5 | D | 0, 4 | `feat: [D] LLM Judge 품질 평가 노드와 강제 종료 추가` |
| 6 | B | 0, 2a | `feat: [B] trace_id·체크포인터·LangSmith·기업 지정 실행 추가` |
| 2b | A | 2a, 5 | `feat: [A] 보고서 품질 평가 루프 연결` |
| 7 | 전원 | 2b, 6 | (단계별 기재) |

| 시간 | A 김현수 | B 박인우 | C 박세웅 | D 성재원 | E 김세령 |
|---|---|---|---|---|---|
| 0:00–0:20 | Task 1 테스트 작성 | **Task 0 → push** | Task 3 | Task 4 | 7-0 README 초안 |
| 0:20–1:00 | Task 1 → push | Task 6 코딩 | Task 3 push | Task 5 | 7-R 리뷰 (Task 0·3·4) |
| 1:00–1:30 | Task 2a → push | Task 6 push (2a 후) | 7-3 README 재료 → E | Task 5 push | 7-R 리뷰 (Task 1·2a·5) |
| 1:30–2:00 | Task 2b → push, 7-1 | 7-2 트레이스 실행·캡처 | 7-4 전체 실행 시작 | 크로스 리뷰 | 7-R 리뷰 (Task 2b·6) |
| 2:00–2:40 | E 질문 대응 | 트레이스 PNG → E | 결과 비교 → E | E 질문 대응 | 7-5 README 완성, 7-6 보고서 확인 |
| 2:40–3:00 | 최종 확인 | 크로스 리뷰 | 크로스 리뷰 | 크로스 리뷰 | 7-7 zip 제출 |

**45개사 전체 실행이 2:40까지 끝나지 않으면** `uv run python app.py --only C03,C07,C18,C25 --pdf`(이전 실행의 적격 후보 4곳: 망고부스트코리아·아이디어스투실리콘·엑시나·디노티시아, 약 10분)로 돌린 결과로 제출한다. 적격성 판정은 캐시라 같은 후보가 남는다.

## Global Constraints

- **브랜치 규칙:** 각자 레인 브랜치(`feat/agent-a-supervisor`, `feat/agent-b-state`, `feat/agent-c-workers`, `feat/agent-d-evaluator`, `feat/agent-e-docs`)를 `main`에서 따서 작업하고, Task가 끝날 때마다 `git merge --no-ff`로 `main`에 합친다 (각 Task 마지막 명령). 다른 레인의 결과가 필요하면 내 브랜치에서 `git merge origin/main`으로 받는다. 최종 제출물은 `main`이다. 두 사람이 동시에 머지해서 `git push origin main`이 거절되면 `git pull origin main` → `uv run pytest -q` → 다시 push한다. 기존 `main`에 있던 이전 RAG 과제는 Task P에서 `rag-pjt` 브랜치로 보존했으므로 **`rag-pjt`는 절대 수정·push하지 않는다.** 작업 시작 시점의 main 코드는 이전 RAG 과제 최종본이며, 이번 계획은 그 위에 Supervisor 구조를 얹는다.
- 커밋 메시지는 위 표 그대로 (`feat: [레인] 설명`). AI co-author 트레일러 금지.
- push 전 `uv run pytest -q` 전체 통과.
- 에이전트 인터페이스 `run(state) -> dict` 유지. 반환 키는 State에 정의된 것만.
- 병렬 실행 노드(technology·market·competitor)가 쓰는 키는 서로 다르거나 리듀서가 있어야 한다.
- 상수는 `config.py`에만: `MAX_REWORK=1`, `MIN_EVIDENCE=2`, `MAX_SUPERVISOR_STEPS=6`, `MAX_REPORT_REVISIONS=2`, `MIN_PUBLISHERS=3`, `MAX_SOURCE_SHARE=0.5`, `MAX_CONCURRENCY=4`.
- 테스트에서 실제 LLM을 호출하지 않는다 (`tests/conftest.py`가 Supervisor·Judge LLM을 대체).
- 선행 조건 대기 명령 형식 (예: Task 0 대기):
  ```bash
  until git fetch -q origin && git log origin/main --format=%s | grep -qF "feat: [B] Supervisor용 State"; do echo "Task 0 대기"; sleep 60; done && git merge origin/main   # 내 브랜치에서 실행
  ```

## Review Focus

1. **병렬 노드의 같은 키 동시 쓰기** — `retrieve_count`가 남아 있으면 `InvalidUpdateError: At key 'retrieve_count': Can receive only one value per step` (실측). Task 3에서 반환 제거, Task 2a에서 필드 삭제. `test_real_d_nodes_in_graph_rework_and_reset_between_companies`가 잡는다.
2. **병렬 첫 검색에서 검색기 경합** — technology·market이 동시에 처음 검색하면 색인·bge-m3를 두 번 적재하고 torch 스레드 경합으로 멈춘다 (실측: 둘 다 FAILED 후 CPU 196%로 정지). Task 3의 `rag/retriever.py` Lock으로 막는다.
3. **worker가 매번 예외** — 재시도 1회 후 기술이면 보류, 시장·경쟁이면 미확인으로 진행. `test_failed_worker_retried_once_then_fallback`.
4. **`근거충분`이 항상 False** (README Lessons 5) — 재작업 상한 후 반드시 `investment` 도달. `test_loop_flow_with_supervisor`.
5. **보고서가 끝까지 품질 미달** — 재생성 2회 후 `end_with_warning`으로 종료, `final_report` 유지. `test_eval_loop_terminates`, `test_loop_flow_with_supervisor`.

---

### Task P [사전 준비 — 이 계획 파일을 가진 사람, 기본 A 김현수]: 이전 과제 보존 + 계획 공유

**왜:** 지금 `main`에는 이전 RAG 과제(45개사 평가, 망고부스트 79.0점) 최종본이 있다. 노션 요구("Branch로 기존 작업과 구분")에 맞게 이를 `rag-pjt` 브랜치로 옮겨 보존하고, 이번 Agent 과제는 `main`에서 진행한다. 다른 레인은 이 Task가 끝나야 시작한다.

- [ ] **Step 1: 이전 과제 보존 브랜치 생성·push**

```bash
git fetch origin
git switch main && git pull --rebase origin main
git status --short        # 추적 파일 변경이 없어야 한다 (이 계획 파일만 ?? 로 보이는 것은 정상)
git branch rag-pjt origin/main
git push origin rag-pjt
git ls-remote --heads origin rag-pjt   # 한 줄 출력되면 성공
```

- [ ] **Step 2: 계획 파일을 main에 커밋·push** (팀원 AI가 이 파일을 읽고 진행한다)

```bash
git add docs/superpowers/plans/2026-10-13-agent-supervisor.md
git commit -m "docs: [공통] Agent 과제 Supervisor 전환 계획"
git push origin main
```

- [ ] **Step 3: 팀 채널 공지** — "rag-pjt에 이전 과제 보존 완료, main에서 Agent 과제 시작. 각자 `git pull` 후 계획 파일의 AI 프롬프트로 진행"

**다른 레인의 시작 조건 (모든 Task 공통, 맨 처음 1회):**
```bash
until git fetch -q origin && git ls-remote --heads origin rag-pjt | grep -q rag-pjt && git log origin/main --format=%s | grep -qF "docs: [공통] Agent 과제 Supervisor 전환 계획"; do echo "Task P 대기"; sleep 60; done && git switch main && git pull origin main && (git switch <내 브랜치> 2>/dev/null && git merge main || git switch -c <내 브랜치>)
```
`<내 브랜치>`는 "팀 배정" 표의 작업 브랜치 (예: B는 `feat/agent-b-state`). 이후 모든 작업은 이 브랜치에서 한다. A도 Task P를 마친 뒤 이 명령으로 `feat/agent-a-supervisor`를 만든다.

---

### Task 0 [B 박인우]: State·config·관측성 계약

**선행 조건:** Task P (공통 시작 조건) 외 없음. **가장 먼저 push한다 (A·D가 기다림).**

**Files:**
- Modify: `state.py`, `config.py`
- Create: `obs.py`, `tests/test_state.py`

**Interfaces (Produces):**
- `state.merge_dict(old: dict, new: dict | None) -> dict`
- State 신규 필드: `trace_id`, `next: list[str]`, `step_count: int`, `max_steps: int`, `rework_reason: dict[str, str]`, `node_status: Annotated[dict[str, str], merge_dict]`, `agent_attempts: Annotated[dict[str, int], merge_dict]`, `last_error: dict | None`, `company_filter: list[str]`, `eval_result: dict | None`, `report_attempts: int`
- `config`: `MAX_REWORK`, `MIN_EVIDENCE`, `MAX_SUPERVISOR_STEPS`, `MAX_REPORT_REVISIONS`, `MIN_PUBLISHERS`, `MAX_SOURCE_SHARE`, `MAX_CONCURRENCY`
- `obs.LOG_DIR: Path`, `obs.log_decision(state, node, decision, reason) -> None`, `obs.summarize(trace_id) -> dict`
- **이 Task는 추가만 한다.** `retrieve_count`·`next_attempt`·`N_RETRIEVE_RETRY` 삭제는 Task 2a(A)가 한다.

- [ ] **Step 1: 테스트 작성** — `tests/test_state.py` 생성 (아래 내용 중 `test_loader_applies_company_filter`는 Task 6에서 추가하므로 지금은 넣지 않는다)

```python
import json

import obs
from state import merge_dict


def test_merge_dict_merges_and_resets():
    assert merge_dict({"technology": "SUCCESS"}, {"market": "FAILED"}) == {"technology": "SUCCESS", "market": "FAILED"}
    assert merge_dict({"technology": "SUCCESS"}, {"technology": "FAILED"}) == {"technology": "FAILED"}
    assert merge_dict({"technology": "SUCCESS"}, None) == {}


def test_log_decision_and_summarize(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path)
    state = {"trace_id": "t1", "current_company": {"company_id": "C03"}}
    obs.log_decision(state, "supervisor", ["technology", "market"], "미수행")
    for node in ("technology", "market", "technology"):
        obs.log_decision(state, node, "SUCCESS", "attempt")
    obs.log_decision(state, "evaluator", "fail", "x")
    rec = json.loads((tmp_path / "t1.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["trace_id"] == "t1" and rec["company_id"] == "C03"
    assert rec["node"] == "supervisor" and rec["decision"] == ["technology", "market"]
    assert rec["reason"] == "미수행" and "ts" in rec
    assert obs.summarize("t1") == {"supervisor_routes": 1, "agent_runs": {"technology": 2, "market": 1},
                                   "reworks": 1, "evaluations": ["fail"]}
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_state.py -q`
Expected: FAIL — `ImportError: cannot import name 'merge_dict'`, `ModuleNotFoundError: No module named 'obs'`

- [ ] **Step 3: `state.py` 수정**

찾기:
```python
Decision = Literal["투자 적격", "보류", "제외"]
```
바꾸기:
```python
def merge_dict(old: dict, new: dict | None) -> dict:
    """병렬 노드가 서로 다른 키를 동시에 써도 합쳐지도록. None이면 리셋 (기업 전환)."""
    if new is None:
        return {}
    return {**(old or {}), **new}


Decision = Literal["투자 적격", "보류", "제외"]
```

찾기:
```python
    # ② 흐름 제어
    current_index: int
    route_reason: str
    retrieve_count: int
```
바꾸기:
```python
    # ② 흐름 제어 (라우팅·종료·재개에 필요한 최소치)
    trace_id: str  # 상관 키: outputs/logs/{trace_id}.jsonl·LangSmith metadata·checkpointer thread_id
    current_index: int
    route_reason: str  # 마지막 분기 사유 1줄 (전체 이력은 외부 로그)
    retrieve_count: int  # 구 구조용, Task 2a에서 삭제
    next: list[str]  # Supervisor가 고른 다음 노드 (conditional edge가 읽음)
    step_count: int  # 기업별 Supervisor 방문 수 (Supervisor만 씀)
    max_steps: int  # 종료 가드 상한 (config.MAX_SUPERVISOR_STEPS)
    rework_reason: dict[str, str]  # 에이전트별 재작업 사유 → 질의 재작성
    node_status: Annotated[dict[str, str], merge_dict]  # {"technology": "SUCCESS"|"FAILED"} 병렬 쓰기 병합
    agent_attempts: Annotated[dict[str, int], merge_dict]  # 에이전트별 실행 횟수, MAX_REWORK 상한
    last_error: dict | None  # 마지막 오류 {company_id, stage, type, error, ts} (Supervisor만 씀)
    company_filter: list[str]  # 지정 시 해당 company_id만 평가 (트레이스 캡처용)
```

찾기:
```python
    final_report: str
```
바꾸기:
```python
    final_report: str
    eval_result: dict | None  # 품질 평가 verdict (EvaluationResult + score)
    report_attempts: int  # 품질 평가 횟수, MAX_REPORT_REVISIONS 상한
```

- [ ] **Step 4: `config.py` 수정**

찾기:
```python
N_RETRIEVE_RETRY = 1
```
바꾸기:
```python
N_RETRIEVE_RETRY = 1

# Supervisor·품질 평가 (Agent 과제: 종료 보장·재작업 상한)
MAX_REWORK = 1  # 에이전트별 재작업 상한 (최대 실행 = 1 + MAX_REWORK)
MIN_EVIDENCE = 2  # 관점별 최소 근거ID 수
MAX_SUPERVISOR_STEPS = 6  # 기업별 Supervisor 방문 상한 (정상 경로 최대 5회 + 여유 1)
MAX_REPORT_REVISIONS = 2  # 품질 미달 시 보고서 재생성 상한
MIN_PUBLISHERS = 3  # 편향 통제: 본문 인용 출처 기관 최소 수
MAX_SOURCE_SHARE = 0.5  # 편향 통제: 단일 기관 인용 비중 상한
MAX_CONCURRENCY = 4  # 병렬 노드 동시 실행 상한 (외부 API rate limit)
```

- [ ] **Step 5: `obs.py` 생성**

```python
"""결정 로그는 State가 아니라 외부 JSONL로 (State 무한 증식 방지). trace_id로 State·LangSmith와 연결."""

import json
import time

from config import OUTPUT_DIR

LOG_DIR = OUTPUT_DIR / "logs"


def log_decision(state: dict, node: str, decision, reason: str) -> None:
    """{trace_id, company_id, node, decision, reason, ts}를 outputs/logs/{trace_id}.jsonl에 한 줄 추가."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    trace_id = state.get("trace_id") or "no-trace"
    rec = {
        "trace_id": trace_id,
        "company_id": (state.get("current_company") or {}).get("company_id"),
        "node": node,
        "decision": decision,
        "reason": reason,
        "ts": time.time(),
    }
    with open(LOG_DIR / f"{trace_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def summarize(trace_id: str) -> dict:
    """동적 동작 실증용 집계: Supervisor 라우팅 수, 에이전트별 실행 수, 재작업 수, 품질 평가 결과."""
    path = LOG_DIR / f"{trace_id}.jsonl"
    if not path.exists():
        return {}
    recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    runs: dict[str, int] = {}
    for r in recs:
        if r["node"] in ("technology", "market", "competitor"):
            runs[r["node"]] = runs.get(r["node"], 0) + 1
    firsts = {(r["company_id"], r["node"]) for r in recs if r["node"] in runs}
    return {
        "supervisor_routes": sum(r["node"] == "supervisor" for r in recs),
        "agent_runs": runs,
        "reworks": sum(runs.values()) - len(firsts),
        "evaluations": [r["decision"] for r in recs if r["node"] == "evaluator"],
    }
```

- [ ] **Step 6: 통과 확인**

Run: `uv run pytest -q`
Expected: 전체 PASS (추가만 했으므로 기존 175개 + 신규 2개)

- [ ] **Step 7: 커밋·push**

```bash
git add state.py config.py obs.py tests/test_state.py
git commit -m "feat: [B] Supervisor용 State 제어 필드·종료 상한·결정 로그 추가"
git push origin feat/agent-b-state                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-b-state -m "merge: [B] feat/agent-b-state → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-b-state && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 1 [A 김현수]: Hybrid Supervisor

**선행 조건:** Task 0 (테스트 작성은 먼저 해도 된다. 실행·커밋 전에 아래 대기)
```bash
until git fetch -q origin && git log origin/main --format=%s | grep -qF "feat: [B] Supervisor용 State"; do echo "Task 0 대기"; sleep 60; done && git merge origin/main   # 내 브랜치에서 실행
```

**Files:**
- Create: `agents/supervisor.py`, `tests/conftest.py`, `tests/test_supervisor.py`

**Interfaces:**
- Consumes: Task 0의 State 필드, `config.MAX_REWORK`, `MIN_EVIDENCE`, `MAX_SUPERVISOR_STEPS`, `obs.log_decision`, `llm.get_llm()`
- Produces:
  - `RouteResponse(BaseModel)`: `next: list[Literal["technology","market","competitor","investment"]]`, `reason: str`
  - `sufficient(stage, state) -> tuple[bool, str]`
  - `rework_candidates(state) -> dict[str, str]`
  - `decide_next(state) -> tuple[list[str], dict[str, str], str]` (규칙 정책)
  - `_ask_llm(state, candidates) -> RouteResponse | None` (테스트에서 monkeypatch)
  - `run(state) -> {"next", "rework_reason", "route_reason", "step_count", "last_error"}`
  - `route(state) -> list[str]`
  - 노드 이름: `"technology"`, `"market"`, `"competitor"`, `"investment"`, `"handle_error"`

**판단 규칙 (README Agents 섹션에 그대로 옮긴다):**
1. `step_count >= max_steps` → `investment` (종료 보장)
2. technology가 재시도 후에도 실패 → `handle_error` (기술력 30% + 최소 기준이라 없이 판단 불가 → 보류). 시장·경쟁 실패는 미확인으로 진행 (Fall-back)
3. technology·market 미수행 또는 실패(재시도 가능) → 함께 병렬 실행 (LLM 호출 안 함)
4. competitor 미수행 또는 실패 → 실행 (기술·시장 결과를 비교 기준으로 쓰는 데이터 의존성)
5. 세 관점이 한 번씩 끝났고 근거 부족 관점이 있으면 → **LLM이 재작업할 관점(복수 가능) 또는 `investment`를 고른다.** 선택지 밖이거나 실패하면 규칙대로 부족한 관점 전부 재작업
6. 모두 충분하거나 상한 도달 → `investment`

- [ ] **Step 1: 테스트 작성** — `tests/test_supervisor.py`

```python
import obs
from agents import supervisor
from agents.supervisor import RouteResponse, decide_next, sufficient

OK_TECH = {"근거충분": True, "근거ID": ["TEC-1", "TEC-2"]}
OK_MKT = {"근거충분": True, "근거ID": ["MKT-1", "MKT-2"]}
OK_CMP = {"경쟁제품": [{"제품": "x"}], "근거ID": ["CMP-1", "CMP-2"]}
BAD_TECH = {"근거충분": False, "근거ID": ["TEC-1"], "미확인정보": ["성능지표"]}
ONCE = {"technology": 1, "market": 1, "competitor": 1}


def test_first_round_runs_technology_and_market_in_parallel():
    nxt, rework, _ = decide_next({})
    assert nxt == ["technology", "market"] and set(rework) == {"technology", "market"}


def test_competitor_runs_after_views_even_if_insufficient():
    state = {"technology_analysis": BAD_TECH, "market_analysis": OK_MKT, "agent_attempts": {"technology": 1, "market": 1}}
    assert decide_next(state)[0] == ["competitor"]


def test_rework_candidates_with_reason():
    state = {"technology_analysis": BAD_TECH, "market_analysis": OK_MKT, "competitor_analysis": OK_CMP,
             "agent_attempts": ONCE}
    nxt, rework, _ = decide_next(state)
    assert nxt == ["technology"] and "성능지표" in rework["technology"]


def test_rework_cap_moves_to_investment():
    state = {"technology_analysis": BAD_TECH, "market_analysis": OK_MKT, "competitor_analysis": OK_CMP,
             "agent_attempts": {**ONCE, "technology": 2}}
    assert decide_next(state)[0] == ["investment"]


def test_all_sufficient_goes_to_investment():
    state = {"technology_analysis": OK_TECH, "market_analysis": OK_MKT, "competitor_analysis": OK_CMP,
             "agent_attempts": ONCE}
    assert decide_next(state)[0] == ["investment"]


def test_step_cap_forces_investment():
    assert decide_next({"step_count": 6})[0] == ["investment"]
    assert decide_next({"step_count": 2, "max_steps": 2})[0] == ["investment"]


def test_failed_worker_retried_once_then_fallback():
    once = {"node_status": {"technology": "FAILED", "market": "SUCCESS"}, "market_analysis": OK_MKT,
            "agent_attempts": {"technology": 1, "market": 1}}
    assert decide_next(once)[0] == ["technology"]
    assert decide_next({**once, "agent_attempts": {"technology": 2, "market": 1}})[0] == ["handle_error"]
    mkt_failed = {"technology_analysis": OK_TECH, "node_status": {"technology": "SUCCESS", "market": "FAILED"},
                  "agent_attempts": {"technology": 1, "market": 2}}
    assert decide_next(mkt_failed)[0] == ["competitor"]  # 시장 실패는 미확인으로 계속


def test_sufficient_requires_min_evidence():
    assert sufficient("technology", {"technology_analysis": {"근거충분": True, "근거ID": ["TEC-1"]}})[0] is False
    assert sufficient("technology", {"technology_analysis": OK_TECH})[0] is True


REWORK_STATE = {"trace_id": "t", "technology_analysis": BAD_TECH, "market_analysis": OK_MKT,
                "competitor_analysis": {"경쟁제품": [], "근거ID": []}, "agent_attempts": ONCE}


def test_llm_decides_between_rework_and_investment(monkeypatch):
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: RouteResponse(next=["investment"], reason="공개자료 부족"))
    out = supervisor.run(REWORK_STATE)
    assert out["next"] == ["investment"] and "LLM" in out["route_reason"]
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: RouteResponse(next=["technology"], reason="재검색"))
    out = supervisor.run(REWORK_STATE)
    assert out["next"] == ["technology"] and set(out["rework_reason"]) == {"technology"}


def test_invalid_llm_choice_falls_back_to_policy(monkeypatch):
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: RouteResponse(next=["market"], reason="x"))
    assert supervisor.run(REWORK_STATE)["next"] == ["technology", "competitor"]


def test_llm_not_asked_for_mandatory_steps(monkeypatch):
    monkeypatch.setattr(supervisor, "_ask_llm", lambda s, c: (_ for _ in ()).throw(AssertionError("호출 금지")))
    assert supervisor.run({"trace_id": "t"})["next"] == ["technology", "market"]


def test_run_increments_step_logs_and_routes():
    out = supervisor.run({"trace_id": "t", "step_count": 2,
                          "current_company": {"company_id": "C1"},
                          "errors": [{"company_id": "C1", "stage": "market", "error": "x"}]})
    assert out["step_count"] == 3 and out["next"] == ["technology", "market"]
    assert out["last_error"]["stage"] == "market"
    assert supervisor.route({"next": ["market"]}) == ["market"]
    assert (obs.LOG_DIR / "t.jsonl").exists()
```

`tests/conftest.py` (테스트 전체에서 실제 LLM 호출과 `outputs/logs` 쓰기를 막는다. Judge 대체는 Task 2b에서 추가):

```python
"""외부 LLM 호출을 막는다. 새 노드의 LLM 진입점은 여기서 기본값으로 대체하고, 필요한 테스트만 다시 monkeypatch한다."""

import pytest


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch, tmp_path):
    import obs
    from agents import supervisor

    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(supervisor, "_ask_llm", lambda state, candidates: None)  # → 규칙 정책
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_supervisor.py -q`
Expected: FAIL — `ImportError: cannot import name 'supervisor' from 'agents'`

- [ ] **Step 3: `agents/supervisor.py` 생성**

```python
"""Supervisor — 기업 1곳의 분석 구간을 통제한다 (Hybrid: 규칙 가드 + LLM 판단).

- 하위 에이전트(technology·market·competitor)는 서로 통신하지 않고 항상 여기로 돌아온다.
- 규칙(코드): 필수 단계·실패 재시도·상한(종료 보장)을 강제한다. 재현성이 필요한 부분.
- LLM: 모든 관점이 한 번씩 실행된 뒤 "근거 부족 관점을 재작업할지, 투자 판단으로 넘어갈지"를 판단한다.
  LLM 응답이 선택지를 벗어나거나 호출이 실패하면 규칙 정책으로 대체한다.
- 결정 사유는 State에 마지막 1줄(route_reason)만 두고 전체 이력은 obs.log_decision으로 외부에 남긴다.
"""

import json
from typing import Literal

from pydantic import BaseModel

from config import MAX_REWORK, MAX_SUPERVISOR_STEPS, MIN_EVIDENCE
from obs import log_decision
from state import State

WORKERS = ("technology", "market", "competitor")
VIEWS = ("technology", "market")  # 서로 독립 → 첫 라운드 병렬


class RouteResponse(BaseModel):
    next: list[Literal["technology", "market", "competitor", "investment"]]
    reason: str


def build_system_prompt() -> str:
    """판단 규칙을 코드 상수에서 생성 → 상수를 바꾸면 프롬프트도 함께 바뀐다."""
    return (
        "너는 AI 반도체 스타트업 투자 심사팀의 Supervisor다. 직접 분석하지 않고 하위 에이전트에게 재작업을 지시하거나 "
        "투자 판단 단계로 넘긴다.\n\n"
        "[하위 에이전트]\n"
        "- technology: 기술력 (IRDS·UCIe·CXL 기준값 대조)\n"
        "- market: 시장성 (SIA·WSTS·KIET·OECD 대조)\n"
        "- competitor: 경쟁 제품 비교 (기술·시장 결과를 기준으로 사용)\n\n"
        "[판단 규칙]\n"
        f"- 관점별 근거ID가 {MIN_EVIDENCE}개 이상이고 근거충분=True면 충분하다.\n"
        f"- 재작업은 관점별 최대 {MAX_REWORK}회다. 입력의 재작업후보는 이 상한 안에 있다.\n"
        "- 재작업으로 보완될 가능성이 있는 관점만 고른다. 원인이 기업 공개자료 부족이라 재검색해도 나아지지 않으면 "
        "재작업하지 말고 investment를 고른다.\n"
        "- 여러 관점을 동시에 재작업할 수 있다 (병렬 실행).\n"
        "- investment를 고르면 다른 항목과 함께 고르지 않는다.\n\n"
        "next에는 선택지 중에서만 고르고, reason에 한두 문장으로 근거를 쓴다."
    )


def sufficient(stage: str, state: dict) -> tuple[bool, str]:
    out = state.get(f"{stage}_analysis")
    if out is None:
        return False, "미수행"
    ids = set(out.get("근거ID") or [])
    if stage == "competitor":
        n = len(out.get("경쟁제품") or [])
        ok = n > 0 and len(ids) >= MIN_EVIDENCE
        return ok, "" if ok else f"경쟁제품 {n}개, 근거ID {len(ids)}개"
    if not out.get("근거충분"):
        gaps = ", ".join((out.get("미확인정보") or [])[:3]) or "사유 미기재"
        return False, f"근거충분=False ({gaps})"
    if len(ids) < MIN_EVIDENCE:
        return False, f"근거ID {len(ids)}개 < {MIN_EVIDENCE}"
    return True, ""


def _must_run(stage: str, state: dict) -> str | None:
    """반드시 실행할 사유(미수행·실패 재시도). 상한에 도달했으면 None."""
    if (state.get("agent_attempts") or {}).get(stage, 0) > MAX_REWORK:
        return None
    if (state.get("node_status") or {}).get(stage) == "FAILED":
        return "이전 실행 실패 → 재시도"
    return "미수행" if state.get(f"{stage}_analysis") is None else None


def rework_candidates(state: dict) -> dict[str, str]:
    """근거가 부족하고 재작업 상한이 남은 관점 → 사유."""
    out = {}
    for s in WORKERS:
        if (state.get("agent_attempts") or {}).get(s, 0) > MAX_REWORK:
            continue
        ok, why = sufficient(s, state)
        if not ok:
            out[s] = why
    return out


def decide_next(state: dict) -> tuple[list[str], dict[str, str], str]:
    """규칙 정책. 반환: (다음 노드들, 재작업 사유, 분기 사유). LLM 판단이 없거나 무효일 때도 이 결과를 쓴다."""
    if state.get("step_count", 0) >= state.get("max_steps", MAX_SUPERVISOR_STEPS):
        return ["investment"], {}, "step 상한 도달 → 보유 근거로 투자 판단"
    status = state.get("node_status") or {}
    attempts = state.get("agent_attempts") or {}
    if status.get("technology") == "FAILED" and attempts.get("technology", 0) > MAX_REWORK:
        return ["handle_error"], {}, "기술 분석 재시도 후에도 실패 → 기술력 없이 판단 불가, 보류"
    todo = {s: why for s in VIEWS if (why := _must_run(s, state))}
    if todo:
        return list(todo), todo, "필수 실행: " + "; ".join(f"{s}={w}" for s, w in todo.items())
    if why := _must_run("competitor", state):
        return ["competitor"], {"competitor": why}, f"기술·시장 확보 → 경쟁 비교 ({why})"
    if cands := rework_candidates(state):
        return list(cands), cands, "근거 부족 재작업: " + "; ".join(f"{s}={w}" for s, w in cands.items())
    return ["investment"], {}, "모든 관점 근거 충분 또는 재작업 상한 도달 → 투자 판단"


def _ask_llm(state: dict, candidates: dict[str, str]) -> RouteResponse | None:
    """재작업 vs 진행 판단. 실패하면 None (규칙 정책으로 대체). 테스트는 이 함수를 monkeypatch한다."""
    from llm import get_llm

    company = state.get("current_company") or {}
    user = json.dumps({
        "기업": {k: company.get(k) for k in ("company_id", "기업명", "메인아이템")},
        "재작업후보": candidates,
        "실행횟수": state.get("agent_attempts") or {},
        "미확인정보": {s: (state.get(f"{s}_analysis") or {}).get("미확인정보") for s in WORKERS},
        "선택지": [*candidates, "investment"],
    }, ensure_ascii=False, default=str)
    try:
        llm = get_llm().with_structured_output(RouteResponse, method="json_schema", strict=True)
        return llm.invoke([("system", build_system_prompt()), ("user", user)])
    except Exception:
        return None


def _valid(resp: RouteResponse | None, candidates: dict[str, str]) -> list[str] | None:
    if resp is None or not resp.next:
        return None
    chosen = set(resp.next)
    if chosen == {"investment"}:
        return ["investment"]
    if chosen <= set(candidates):
        return [s for s in WORKERS if s in chosen]
    return None


def run(state: State) -> dict:
    nxt, rework, reason = decide_next(state)
    if nxt[0] in WORKERS and set(nxt) <= set(rework_candidates(state)) and not any(
            _must_run(s, state) for s in WORKERS):
        resp = _ask_llm(state, rework)
        if chosen := _valid(resp, rework):
            nxt, reason = chosen, f"LLM 판단: {resp.reason}"
            rework = {s: w for s, w in rework.items() if s in chosen}
        else:
            reason = f"{reason} (LLM 무응답·무효 → 규칙 정책)"
    errors = state.get("errors") or []
    cid = (state.get("current_company") or {}).get("company_id")
    last = next((e for e in reversed(errors) if e.get("company_id") == cid), None)
    log_decision(state, "supervisor", nxt, reason)
    return {"next": nxt, "rework_reason": rework, "route_reason": reason,
            "step_count": state.get("step_count", 0) + 1, "last_error": last}


def route(state: State) -> list[str]:
    return state["next"]
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest -q`
Expected: 전체 PASS (`tests/test_supervisor.py` 12개 포함)

- [ ] **Step 5: 커밋·push**

```bash
git add agents/supervisor.py tests/conftest.py tests/test_supervisor.py
git commit -m "feat: [A] Hybrid Supervisor 라우팅 판단 추가"
git push origin feat/agent-a-supervisor                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-a-supervisor -m "merge: [A] feat/agent-a-supervisor → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-a-supervisor && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 3 [C 박세웅]: 하위 에이전트 병렬·재작업 대응

**선행 조건:** Task P (공통 시작 조건) 외 없음. 바로 시작한다.

**Files:**
- Modify: `agents/_rag_utils.py`, `agents/technology.py`, `agents/market.py`, `rag/retriever.py`, `prompts/technology.md`, `prompts/market.md`, `tests/test_rag_agents.py`

**Interfaces:**
- Consumes: State `rework_reason: dict[str, str]` (없으면 빈 dict로 처리 → Task 0 전에도 동작)
- Produces: worker 반환 키는 `{"<stage>_analysis", "current_evidence"}`만 (`retrieve_count` 반환 금지). `rag.retriever.hybrid_search`는 스레드 안전.

- [ ] **Step 1: 테스트 수정** — `tests/test_rag_agents.py`

찾기 (`company_state` 안):
```python
        "as_of_date": "2026-09-30", "retrieve_count": 0,
```
바꾸기:
```python
        "as_of_date": "2026-09-30",
```

찾기 (`test_three_company_contracts` 안):
```python
    assert set(tech) == {"technology_analysis", "current_evidence", "retrieve_count"}
    assert tech["retrieve_count"] == 1 and tech["technology_analysis"]["근거충분"] is True
    state = apply_update(state, tech)
    # 기술 단계 카운터와 관계없이 시장 단계 첫 진입은 1부터 시작한다.
    state["retrieve_count"] = 2
    out = market.run(state)
    assert set(out) == {"market_analysis", "current_evidence", "retrieve_count"}
    assert out["retrieve_count"] == 1 and out["market_analysis"]["근거충분"] is True
```
바꾸기:
```python
    assert set(tech) == {"technology_analysis", "current_evidence"}  # 실행 횟수는 graph.guarded_worker가 센다
    assert tech["technology_analysis"]["근거충분"] is True
    state = apply_update(state, tech)
    out = market.run(state)
    assert set(out) == {"market_analysis", "current_evidence"}
    assert out["market_analysis"]["근거충분"] is True
```

찾기 (`test_retry_rewrites_query_and_deduplicates_evidence` 안) — 이 한 줄 삭제:
```python
    assert initial["retrieve_count"] == 1 and retry["retrieve_count"] == 2
```

찾기 (함수 전체):
```python
def test_empty_search_retries_once_then_continues(monkeypatch, agent, key, next_node):
    from graph import route_retry

    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(rag, "generate_analysis", lambda *args: pytest.fail("빈 근거로 LLM 호출"))
    state = apply_update(company_state(), agent.run(company_state()))
    route = route_retry(key, key.split("_")[0], next_node)
    assert route(state) == key.split("_")[0]
    state = apply_update(state, agent.run(state))
    assert state[key]["근거충분"] is False
    assert state[key]["미확인정보"]
    assert route(state) == next_node and state["retrieve_count"] == 2
```
바꾸기:
```python
def test_empty_search_retries_once_then_continues(monkeypatch, agent, key, next_node):
    # 재작업 여부·상한은 Supervisor가 판단한다 (tests/test_supervisor.py). 여기서는 빈 검색 결과 처리만 본다.
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(rag, "generate_analysis", lambda *args: pytest.fail("빈 근거로 LLM 호출"))
    state = apply_update(company_state(), agent.run(company_state()))
    assert state[key]["근거충분"] is False
    state = apply_update(state, agent.run(state))
    assert state[key]["근거충분"] is False
    assert state[key]["미확인정보"]
```

찾기:
```python
def test_unknown_evidence_is_rejected_and_retried(monkeypatch, inline, stage):
    from graph import route_retry

```
바꾸기:
```python
def test_unknown_evidence_is_rejected_and_retried(monkeypatch, inline, stage):
```

찾기 (같은 함수 끝):
```python
    assert any("미등록 근거ID" in gap for gap in state[key]["미확인정보"])
    route = route_retry(key, stage, "next")
    assert route(state) == stage
    state = apply_update(state, agent.run(state))
    assert route(state) == "next"
```
바꾸기:
```python
    assert any("미등록 근거ID" in gap for gap in state[key]["미확인정보"])
```

함수 두 개를 **통째로 삭제**한다 (A가 Task 2a에서 `tests/test_graph_flow.py`로 옮겨 다시 작성): `test_failure_is_recorded_by_graph`, `test_real_d_nodes_in_graph_retry_and_reset_between_companies`.

파일 끝에 추가:
```python


def test_rework_reason_drives_query_rewrite():
    state = {**company_state(), "technology_analysis": {"미확인정보": ["TRL"]},
             "rework_reason": {"technology": "근거ID 1개 < 2 (성능 벤치마크)"}}
    q = rag.build_query(state, "technology")
    assert "성능 벤치마크" in q and "TRL" in q


def test_market_query_without_technology_analysis():
    q = rag.build_query(company_state(), "market")  # 병렬 첫 라운드: 기술 결과 없음
    assert "가상 엣지 NPU" in q
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_rag_agents.py -q`
Expected: FAIL — `test_rework_reason_drives_query_rewrite` (사유가 질의에 없음), `test_three_company_contracts` (`retrieve_count` 키가 아직 반환됨)

- [ ] **Step 3: `agents/_rag_utils.py` 수정**

찾기:
```python
from state import State, next_attempt
```
바꾸기:
```python
from state import State
```

찾기:
```python
    previous = state.get(f"{stage}_analysis")
    if previous is not None:
        gaps = previous.get("미확인정보") or ["원문 수치 단위 기준연도 측정조건 출처"]
        # 최초 질의 전체를 반복하지 않고 미확인 항목과 제품명을 중심으로 재작성한다.
        return f"{company.get('메인아이템', '')} 추가 확인 {' '.join(gaps)} {focus}"
```
바꾸기:
```python
    previous = state.get(f"{stage}_analysis")
    if previous is not None:
        gaps = previous.get("미확인정보") or ["원문 수치 단위 기준연도 측정조건 출처"]
        reason = (state.get("rework_reason") or {}).get(stage, "")
        # Supervisor 재작업 사유 + 미확인 항목과 제품명을 중심으로 재작성한다 (최초 질의 반복 금지).
        return f"{company.get('메인아이템', '')} 추가 확인 {reason} {' '.join(gaps)} {focus}"
```

찾기:
```python
            "이전분석": state.get(output_key),
```
바꾸기:
```python
            "이전분석": state.get(output_key),
            "재작업사유": (state.get("rework_reason") or {}).get(stage),
```

찾기:
```python
    return {output_key: _team_output(stage, analysis), "current_evidence": additions,
            "retrieve_count": next_attempt(state, output_key)}
```
바꾸기:
```python
    return {output_key: _team_output(stage, analysis), "current_evidence": additions}
```

- [ ] **Step 4: docstring 계약 수정** — `agents/technology.py`에서 아래 줄 삭제:
```python
        "retrieve_count": next_attempt(state, "technology_analysis"),
```
`agents/market.py`에서 아래 줄 삭제:
```python
        "retrieve_count": next_attempt(state, "market_analysis"),
```

- [ ] **Step 5: 프롬프트** — `prompts/technology.md`, `prompts/market.md` 끝에 각각 추가:
```markdown

## 재작업 요청 시
입력에 `재작업사유`가 있으면 Supervisor가 이전 분석의 근거 부족을 지적한 것이다. 그 사유에 해당하는 항목을 우선 검색·보완하고, 확인되지 않으면 추정하지 말고 `미확인정보`에 남긴다.
```

- [ ] **Step 6: `rag/retriever.py` 스레드 안전화** (실측: 병렬 첫 검색에서 두 노드가 동시에 색인·모델을 적재하다 실패·정지)

찾기:
```python
from functools import lru_cache
```
바꾸기:
```python
import threading
from functools import lru_cache
```

찾기:
```python
_store: Chroma | None = None
```
바꾸기:
```python
_store: Chroma | None = None
_LOCK = threading.Lock()  # 병렬 노드(technology·market)의 동시 검색 직렬화: 색인·모델 중복 적재와 torch 스레드 경합 방지
```

찾기 (`hybrid_search` docstring 끝부분):
```python
    mode는 임베딩 비교 실험(설계 3-6 비교군 1·2)용. 에이전트는 기본값 hybrid만 쓴다.
    """
```
바꾸기:
```python
    mode는 임베딩 비교 실험(설계 3-6 비교군 1·2)용. 에이전트는 기본값 hybrid만 쓴다.
    """
    with _LOCK:
        return _hybrid_search(query, doc_type, sub_domain, k, mode, doc_id)


def _hybrid_search(query: str, doc_type: str, sub_domain: str | None, k: int, mode: str,
                   doc_id: str | None) -> list[Document]:
```
(기존 `hybrid_search` 본문은 그대로 `_hybrid_search`의 본문이 된다. 들여쓰기 변경 없음.)

- [ ] **Step 7: 통과 확인**

Run: `uv run pytest -q`
Expected: 전체 PASS

- [ ] **Step 8: 커밋·push**

```bash
git add agents/_rag_utils.py agents/technology.py agents/market.py rag/retriever.py prompts/technology.md prompts/market.md tests/test_rag_agents.py
git commit -m "feat: [C] Supervisor 재작업 사유 반영·병렬 실행 대응"
git push origin feat/agent-c-workers                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-c-workers -m "merge: [C] feat/agent-c-workers → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-c-workers && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 4 [D 성재원]: 품질 평가 룰 검사 (1안)

**선행 조건:** Task P (공통 시작 조건) 외 없음. 바로 시작한다. (단 `agents/evaluator.py` 전체는 Task 5에서 `config`·`obs`를 import하므로, 이 Task는 룰 부분만 만든다)

**Files:**
- Create: `agents/evaluator.py`, `tests/test_evaluator.py`

**Interfaces (Produces):** `Criterion(passed: bool, reason: str)`, `rule_checks(report: str, evidence: list[dict]) -> dict[str, Criterion]` (키 `groundedness`, `neutrality`, `bias_control`), `BANNED`

- [ ] **Step 1: 테스트 작성** — `tests/test_evaluator.py`를 아래 내용으로 생성 (Task 5에서 뒷부분을 추가)

```python
from agents.evaluator import rule_checks

EV = [
    {"근거ID": "TEC-02-0008", "publisher": "IRDS"},
    {"근거ID": "MKT-12-0001", "publisher": "SIA"},
    {"근거ID": "DIR-C03-01", "publisher": "창업진흥원"},
    {"근거ID": "CMP-C03-01", "publisher": "IEEE"},
]
GOOD = "기술 [TEC-02-0008] 시장 [MKT-12-0001] 경쟁 [CMP-C03-01] 기업 [DIR-C03-01]"


def _report(body: str) -> str:
    return f"## SUMMARY\n{body}\n\n## REFERENCE\n- 목록"


def test_all_rules_pass():
    assert all(c.passed for c in rule_checks(_report(GOOD), EV).values())


def test_groundedness_fails_on_unknown_or_no_citation():
    assert not rule_checks(_report("근거 없음"), EV)["groundedness"].passed
    assert not rule_checks(_report("[TEC-99-9999]"), EV)["groundedness"].passed


def test_neutrality_flags_banned_phrase():
    r = rule_checks(_report("압도적인 기술 " + GOOD), EV)
    assert not r["neutrality"].passed and "압도적" in r["neutrality"].reason


def test_bias_control_single_source():
    assert not rule_checks(_report("[TEC-02-0008] 또 [TEC-02-0008]"), EV)["bias_control"].passed


def test_bias_control_ignores_company_directory():
    body = "[DIR-C03-01] " * 10 + "[TEC-02-0008] [MKT-12-0001] [CMP-C03-01]"  # 기업 자체 소개는 편중 계산 제외
    assert rule_checks(_report(body), EV)["bias_control"].passed
```

**편향 통제 룰에서 `DIR-`(평가 대상 기업 디렉토리) 근거를 제외하는 이유 (실측):** 기업 보고서는 그 기업 소개 자료를 많이 인용할 수밖에 없다. C03 실행에서 본문 인용 46건 중 DIR이 28건이라 단일 기관 비중이 61%가 되어, 보고서를 몇 번 재생성해도 항상 미달이었다. 외부 근거만 보면 최다 기관 비중이 22%(IEEE)다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_evaluator.py -q` → FAIL `ModuleNotFoundError: No module named 'agents.evaluator'`

- [ ] **Step 3: `agents/evaluator.py` 생성 (룰 부분만)**

```python
"""⑧ 보고서 품질 평가 — Hybrid (1안 룰 검사 + 2안 LLM Judge)."""

from collections import Counter

from pydantic import BaseModel

from agents._report_render import ID_RE

MIN_PUBLISHERS = 3  # Task 5에서 config 값으로 교체
MAX_SOURCE_SHARE = 0.5  # Task 5에서 config 값으로 교체
# 중립성: 투자 판정은 코드 점수로만 내린다. 주관적 추천·우열 단정 표현 금지
BANNED = ("강력 추천", "강력히 추천", "반드시 투자", "최고의", "압도적", "독보적", "완벽한", "유일한")


class Criterion(BaseModel):
    passed: bool
    reason: str


def rule_checks(report: str, evidence: list[dict]) -> dict[str, Criterion]:
    """1안: 형식만 검사한다 (내용은 보지 않음)."""
    body = report.split("## REFERENCE")[0]
    cited = ID_RE.findall(body)
    known = {e["근거ID"]: e for e in evidence if e.get("근거ID")}
    unknown = sorted(set(cited) - set(known))
    ground = Criterion(
        passed=bool(cited) and not unknown,
        reason="인용 없음" if not cited else (f"출처 없는 근거ID {unknown}" if unknown else f"인용 {len(set(cited))}건 모두 추적 가능"),
    )
    hits = [w for w in BANNED if w in body]
    neutral = Criterion(passed=not hits, reason=f"금지 표현 {hits}" if hits else "금지 표현 없음")
    # 기업 디렉토리(DIR-)는 평가 대상 자체 소개라 출처 편중 계산에서 제외하고 외부 근거로만 판정한다
    external = [i for i in cited if i in known and not i.startswith("DIR-")]
    pubs = Counter(known[i].get("publisher") or known[i].get("출처명") or "미상" for i in external)
    share = max(pubs.values()) / sum(pubs.values()) if pubs else 1.0
    bias = Criterion(
        passed=len(pubs) >= MIN_PUBLISHERS and share <= MAX_SOURCE_SHARE,
        reason=f"외부 출처 기관 {len(pubs)}곳, 최다 비중 {share:.0%} (기준 {MIN_PUBLISHERS}곳 이상, {MAX_SOURCE_SHARE:.0%} 이하)",
    )
    return {"groundedness": ground, "neutrality": neutral, "bias_control": bias}


def _all_evidence(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in records:
        for e in r.get("current_evidence") or []:
            if e.get("근거ID"):
                seen.setdefault(e["근거ID"], e)
    return list(seen.values())


def run(state: State) -> dict:
    report = state.get("final_report") or ""
    evidence = _all_evidence(state.get("evaluation_results") or [])
    rules = rule_checks(report, evidence)
    cited = set(ID_RE.findall(report.split("## REFERENCE")[0]))
    user = json.dumps({
        "보고서": report,
        "인용근거": [{"근거ID": e["근거ID"], "원문발췌": (e.get("원문발췌") or "")[:300]}
                    for e in evidence if e["근거ID"] in cited][:40],
        "룰검사": {k: v.model_dump() for k, v in rules.items()},
    }, ensure_ascii=False)
    judge = structured_call(EvaluationResult, build_judge_prompt(), user)
    result = {k: {"passed": rules[k].passed and getattr(judge, k), "rule": rules[k].reason,
                  "judge": getattr(judge, k)} for k in CRITERIA}
    score = sum(v["passed"] for v in result.values()) / len(CRITERIA)
    passed = score == 1.0
    issues = [f"{k}: {v['rule']}" for k, v in result.items() if not v["passed"]] + judge.issues
    attempts = state.get("report_attempts", 0) + 1
    log_decision(state, "evaluator", "pass" if passed else "fail", "; ".join(issues) or "3개 항목 충족")
    return {"eval_result": {"passed": passed, "score": score, **result, "issues": issues},
            "report_attempts": attempts}


def route(state: State) -> str:
    if (state.get("eval_result") or {}).get("passed"):
        return "__end__"
    if state.get("report_attempts", 0) > MAX_REPORT_REVISIONS:
        return "end_with_warning"
    return "report"


def end_with_warning(state: State) -> dict:
    """재생성 상한 초과 시 명시적 종료. 미달 상태를 기록하고 보고서는 그대로 둔다."""
    ev = state.get("eval_result") or {}
    reason = f"재생성 상한 {MAX_REPORT_REVISIONS}회 초과, 점수 {ev.get('score', 0):.2f}, 미달: {ev.get('issues', [])}"
    log_decision(state, "end_with_warning", "stop", reason)
    return {"route_reason": f"[경고] {reason}"}
```

- [ ] **Step 4: 통과 확인** — `uv run pytest -q` 전체 PASS

- [ ] **Step 5: 커밋·push**

```bash
git add agents/evaluator.py tests/test_evaluator.py
git commit -m "feat: [D] 보고서 품질 평가 룰 검사 추가"
git push origin feat/agent-d-evaluator                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-d-evaluator -m "merge: [D] feat/agent-d-evaluator → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-d-evaluator && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 2a [A 김현수]: 그래프를 Supervisor 구조로 교체

**선행 조건:** Task 0, 1, 3
```bash
until git fetch -q origin && L=$(git log origin/main --format=%s) && echo "$L" | grep -qF "feat: [B] Supervisor용 State" && echo "$L" | grep -qF "feat: [A] Hybrid Supervisor" && echo "$L" | grep -qF "feat: [C] Supervisor 재작업"; do echo "Task 0·1·3 대기"; sleep 60; done && git merge origin/main   # 내 브랜치에서 실행
```

**Files:**
- Modify: `graph.py`, `state.py`(구 필드 삭제), `config.py`(구 상수 삭제), `tests/test_skeleton.py`
- Create: `tests/test_graph_flow.py`

`state.py`·`config.py`는 B 소유지만, 구 재검색 카운터 삭제는 C 머지 후에만 가능해서 A가 한다 (B에게 공지).

**Interfaces:**
- Consumes: `supervisor.run`, `supervisor.route` (Task 1)
- Produces: `guarded_worker(stage, fn)` — 성공 `node_status[stage]="SUCCESS"`, 실패 `"FAILED"` + `errors[{company_id, stage, type, error, ts}]`, 항상 `agent_attempts[stage] += 1`. `build_graph(checkpointer=None)`.

- [ ] **Step 1: 테스트 작성**

`tests/test_graph_flow.py` 생성:

```python
"""실제 technology·market 노드를 Supervisor 그래프에 넣은 통합 검증. 외부 API는 호출하지 않는다."""

from collections import Counter

from agents import _rag_utils as rag, technology
from graph import build_graph, guarded_worker
from tests.test_rag_agents import company_state, document, market_output, tech_output


def test_worker_failure_is_recorded_with_status_and_attempts(monkeypatch):
    def failing_search(*args, **kwargs):
        raise RuntimeError("검색기 오류")

    monkeypatch.setattr(rag.retriever, "hybrid_search", failing_search)
    update = guarded_worker("technology", technology.run)(company_state())
    assert update["errors"][0]["company_id"] == "C01" and update["errors"][0]["type"] == "RuntimeError"
    assert update["node_status"] == {"technology": "FAILED"}
    assert update["agent_attempts"] == {"technology": 1}


def test_real_d_nodes_in_graph_rework_and_reset_between_companies(monkeypatch):
    from agents import competitor, eligibility, investment, loader, report

    companies = [company_state(cid)["current_company"] for cid in ("C01", "C02")]
    calls = Counter()
    monkeypatch.setattr(loader, "run", lambda state: {"candidate_companies": companies})
    monkeypatch.setattr(eligibility, "run", lambda state: {
        "eligibility": {"판정": "적격"},
        "current_evidence": company_state(state["current_company"]["company_id"])["current_evidence"],
    })
    monkeypatch.setattr(rag.retriever, "hybrid_search", lambda query, **filters: [document(filters["doc_type"])])

    def generate(stage, payload):
        cid = payload["기업정보"]["company_id"]
        calls[(cid, stage)] += 1
        assert all(not e["근거ID"].startswith("DIR-") or f"-{cid}-" in e["근거ID"]
                   for e in payload["기존근거"] + payload["검색근거"])
        # 기술은 재작업으로 충분해지고, 시장은 상한 이후에도 부족한 상태로 투자 판단에 전달된다.
        return tech_output(cid, enough=calls[(cid, stage)] == 2) if stage == "technology" else market_output(cid, enough=False)

    monkeypatch.setattr(rag, "generate_analysis", generate)
    monkeypatch.setattr(competitor, "run", lambda state: {"competitor_analysis": {}})
    monkeypatch.setattr(investment, "run", lambda state: {"decision": "보류"})
    monkeypatch.setattr(report, "run", lambda state: {"final_report": "가상 보고서"})
    result = build_graph().invoke({"as_of_date": "2026-09-30"}, {"recursion_limit": 200})
    assert len(result["evaluation_results"]) == 2
    assert all(calls[(cid, stage)] == 2 for cid in ("C01", "C02") for stage in ("technology", "market"))
    for record in result["evaluation_results"]:
        ids = sorted(e["근거ID"] for e in record["current_evidence"])
        cid = record["company_id"]
        assert ids == sorted([f"DIR-{cid}-01", "TEC-02-0001", "MKT-13-0001"])
        assert record["technology_analysis"]["근거충분"] is True
        assert record["market_analysis"]["근거충분"] is False
    assert not result.get("errors")
```

`tests/test_skeleton.py`: `test_loop_flow_with_fake_agents` 함수를 **통째로** 아래로 교체 (마지막 3줄의 평가 관련 단언은 Task 2b에서 추가하므로 지금은 `reworks == 5`까지만):

```python
def test_loop_flow_with_supervisor(monkeypatch):
    """c1 부적격 → c2 기술 계속 실패(재시도 1회 후 보류) → c3·c4 적격.
    기술은 항상 근거 부족(재작업 1회), 시장은 충분, 경쟁은 비어 있음(재작업 1회). 총점 1위 c4."""
    import obs
    from agents import competitor, eligibility, investment, loader, market, report, technology

    calls = []
    verdicts = {"c1": "부적격", "c2": "적격", "c3": "적격", "c4": "적격"}
    cid = lambda s: s["current_company"]["company_id"]  # noqa: E731

    def tech(s):
        calls.append(("tech", cid(s)))
        if cid(s) == "c2":
            raise RuntimeError("boom")
        return {"technology_analysis": {"근거충분": False, "근거ID": []}, "current_evidence": [{"id": f"{cid(s)}-t"}]}

    def mkt(s):
        calls.append(("mkt", cid(s)))
        return {"market_analysis": {"근거충분": True, "근거ID": ["MKT-1", "MKT-2"]}}

    def cmp_(s):
        calls.append(("cmp", cid(s)))
        return {"competitor_analysis": {"경쟁제품": [], "근거ID": []}}

    monkeypatch.setattr(loader, "run", lambda s: {"candidate_companies": [{"company_id": c} for c in verdicts]})
    monkeypatch.setattr(eligibility, "run", lambda s: {"eligibility": {"판정": verdicts[cid(s)], "사유": "x"}})
    monkeypatch.setattr(technology, "run", tech)
    monkeypatch.setattr(market, "run", mkt)
    monkeypatch.setattr(competitor, "run", cmp_)
    totals = {"c3": 75, "c4": 80}
    monkeypatch.setattr(investment, "run", lambda s: {
        "decision": "투자 적격",
        "scorecard": {"total": totals[cid(s)], "averages": {"제품/기술력": 4, "실적": 3}, "unknown_items": []},
    })
    monkeypatch.setattr(report, "run", lambda s: {"final_report": "ok"})

    out = build_graph().invoke({"trace_id": "t"}, {"recursion_limit": 300})
    records = {r["company_id"]: r for r in out["evaluation_results"]}
    assert [r["decision"] for r in out["evaluation_results"]] == ["제외", "보류", "투자 적격", "투자 적격"]
    assert calls.count(("tech", "c2")) == 2  # 실패 → 재시도 1회 → handle_error
    for c in ("c3", "c4"):  # 기업 전환 시 실행 횟수 리셋 확인 (c4도 같은 횟수)
        assert calls.count(("tech", c)) == 2  # 근거 부족 → 재작업 1회
        assert calls.count(("mkt", c)) == 1  # 충분 → 재작업 없음
        assert calls.count(("cmp", c)) == 2
    assert out["ranking"] == ["c4", "c3"] and out["selected_company_id"] == "c4"
    assert records["c3"]["current_evidence"] == [{"id": "c3-t"}, {"id": "c3-t"}]
    assert out["errors"][0]["stage"] == "technology"
    assert obs.summarize("t")["reworks"] == 5  # c2 기술 재시도 1 + c3·c4 각각 (기술 1 + 경쟁 1)
```

같은 파일 `test_graph_compiles`의 집합을 교체:
```python
    assert {"load", "eligibility", "supervisor", "technology", "market", "competitor", "investment", "report"} <= set(nodes)
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_skeleton.py tests/test_graph_flow.py -q` → FAIL (`guarded_worker` 없음, supervisor 노드 없음)

- [ ] **Step 3: `graph.py` 수정**

모듈 docstring과 import 블록을 아래로 교체 (파일 첫 줄부터 `from state import State`까지):
```python
"""LangGraph 흐름 — 외부 루프(45개사) + 기업별 Supervisor 서브루프.

eligibility(적격) → supervisor ⇄ {technology, market, competitor} → investment.
하위 에이전트는 guarded_worker로 감싸 실행 횟수·상태를 기록하고 항상 supervisor로 돌아온다.
흐름 제어 노드(select, exclude, hold, handle_error, save, next_index, rank)는 이 파일에 둔다.
루프는 후보 소진 시에만 종료하고, rank가 투자 적격 기업 중 1위를 selected_company_id로 고른다.
"""

import time

from langgraph.graph import END, START, StateGraph

from agents import competitor, eligibility, investment, loader, market, report, supervisor, technology
from agents.investment import rank_key
from config import MAX_SUPERVISOR_STEPS
from obs import log_decision
from state import State
```

`_RESET`에서 찾기:
```python
    "route_reason": "",
    "retrieve_count": 0,
}
```
바꾸기:
```python
    "route_reason": "",
    "next": [],
    "step_count": 0,
    "max_steps": MAX_SUPERVISOR_STEPS,
    "rework_reason": {},
    "node_status": None,  # merge_dict 리듀서가 None을 리셋으로 처리
    "agent_attempts": None,
    "last_error": None,
}
```

`def _failed(state: State) -> bool:` 바로 위에 추가:
```python
def guarded_worker(stage: str, fn):
    """Supervisor 하위 에이전트용. 실행 횟수·상태를 여기서 일괄 기록 → worker는 자기 산출물만 반환한다."""

    def node(state: State) -> dict:
        n = (state.get("agent_attempts") or {}).get(stage, 0) + 1
        try:
            out, status = fn(state), "SUCCESS"
        except Exception as e:  # 실패해도 supervisor가 재시도/진행/보류를 정한다
            out = {"errors": [{"company_id": _company_id(state), "stage": stage, "type": type(e).__name__,
                               "error": repr(e), "ts": time.time()}]}
            status = "FAILED"
        log_decision(state, stage, status, f"attempt {n}" + (f": {out['errors'][0]['error'][:200]}" if status == "FAILED" else ""))
        return {**out, "agent_attempts": {stage: n}, "node_status": {stage: status}}

    return node


def _failed(state: State) -> bool:
    errors = state.get("errors") or []
    return bool(errors) and errors[-1]["company_id"] == _company_id(state)


# ---------- 흐름 제어 노드 ----------

def select(state: State) -> dict:
    company = state["candidate_companies"][state.get("current_index", 0)]
    return {"current_company": company, **_RESET}


def exclude(state: State) -> dict:
    reason = state["eligibility"].get("사유", "")
    return {"decision": "제외", "decision_details": {"판단사유": reason}, "route_reason": f"자격 요건 미충족: {reason}"}


def hold(state: State) -> dict:
    reason = state["eligibility"].get("사유", "")
    return {"decision": "보류", "decision_details": {"추가확인사항": reason}, "route_reason": f"자격 요건 확인 필요: {reason}"}


def handle_error(state: State) -> dict:
    stage = state["errors"][-1]["stage"]
    return {"decision": "보류", "decision_details": {"판단사유": f"{stage} 단계 오류"}, "route_reason": f"오류: {stage}"}


def save(state: State) -> dict:
    """기업별 결과를 누적. 투자 적격이어도 루프는 계속된다 (선정은 rank에서)."""
    keys = ("current_company", "eligibility", "checklist", "technology_analysis", "market_analysis",
            "competitor_analysis", "scorecard", "decision", "decision_details", "route_reason", "current_evidence")
    return {"evaluation_results": [{"company_id": _company_id(state), **{k: state.get(k) for k in keys}}]}


def next_index(state: State) -> dict:
    return {"current_index": state.get("current_index", 0) + 1}


def rank(state: State) -> dict:
    """최종 선정: 전체 후보 평가 후 투자 적격 기업 순위 산정, 1위를 보고서 대상으로."""
    passed = [r for r in state.get("evaluation_results", []) if r["decision"] == "투자 적격"]
    ids = [r["company_id"] for r in sorted(passed, key=rank_key)]
    return {"ranking": ids, "selected_company_id": ids[0] if ids else None}


# ---------- 라우터 ----------

def route_exists(state: State) -> str:
    return "select" if state.get("current_index", 0) < len(state["candidate_companies"]) else "rank"


def route_eligibility(state: State) -> str:
    if _failed(state):
        return "handle_error"
    return {"적격": "supervisor", "부적격": "exclude"}.get(state["eligibility"]["판정"], "hold")


def route_ok(next_node: str):
    return lambda state: "handle_error" if _failed(state) else next_node


def build_graph(checkpointer=None):
    g = StateGraph(State)
    g.add_node("load", loader.run)
    g.add_node("select", select)
    g.add_node("eligibility", guarded("eligibility", eligibility.run))
    g.add_node("supervisor", supervisor.run)
    g.add_node("technology", guarded_worker("technology", technology.run))
    g.add_node("market", guarded_worker("market", market.run))
    g.add_node("competitor", guarded_worker("competitor", competitor.run))
    g.add_node("investment", guarded("investment", investment.run))
    g.add_node("exclude", exclude)
    g.add_node("hold", hold)
    g.add_node("handle_error", handle_error)
    g.add_node("save", save)
    g.add_node("next_index", next_index)
    g.add_node("rank", rank)
    g.add_node("report", report.run)
    g.add_node("evaluator", evaluator.run)
    g.add_node("end_with_warning", evaluator.end_with_warning)

    g.add_edge(START, "load")
    g.add_conditional_edges("load", route_exists, ["select", "rank"])
    g.add_edge("select", "eligibility")
    g.add_conditional_edges("eligibility", route_eligibility, ["supervisor", "exclude", "hold", "handle_error"])
    g.add_conditional_edges("supervisor", supervisor.route,
                            ["technology", "market", "competitor", "investment", "handle_error"])
    for w in ("technology", "market", "competitor"):
        g.add_edge(w, "supervisor")  # 하위 에이전트는 supervisor와만 통신
    g.add_conditional_edges("investment", route_ok("save"), ["save", "handle_error"])
    for n in ("exclude", "hold", "handle_error"):
        g.add_edge(n, "save")
    g.add_edge("save", "next_index")
    g.add_conditional_edges("next_index", route_exists, ["select", "rank"])
    g.add_edge("rank", "report")
    g.add_edge("report", "evaluator")
    g.add_conditional_edges("evaluator", evaluator.route, {"__end__": END, "report": "report",
                                                           "end_with_warning": "end_with_warning"})
    g.add_edge("end_with_warning", END)
    return g.compile(checkpointer=checkpointer)


```

`route_eligibility`에서 찾기 `{"적격": "technology", "부적격": "exclude"}` → 바꾸기 `{"적격": "supervisor", "부적격": "exclude"}`

`def route_retry(...)` 함수 전체를 삭제한다 (`def route_ok`는 유지).

`build_graph`에서 찾기:
```python
def build_graph():
```
바꾸기:
```python
def build_graph(checkpointer=None):
```

찾기:
```python
    g.add_node("technology", guarded("technology", technology.run))
    g.add_node("market", guarded("market", market.run))
    g.add_node("competitor", guarded("competitor", competitor.run))
```
바꾸기:
```python
    g.add_node("supervisor", supervisor.run)
    g.add_node("technology", guarded_worker("technology", technology.run))
    g.add_node("market", guarded_worker("market", market.run))
    g.add_node("competitor", guarded_worker("competitor", competitor.run))
```

찾기:
```python
    g.add_conditional_edges("eligibility", route_eligibility, ["technology", "exclude", "hold", "handle_error"])
    g.add_conditional_edges("technology", route_retry("technology_analysis", "technology", "market"),
                            ["technology", "market", "handle_error"])
    g.add_conditional_edges("market", route_retry("market_analysis", "market", "competitor"),
                            ["market", "competitor", "handle_error"])
    g.add_conditional_edges("competitor", route_ok("investment"), ["investment", "handle_error"])
```
바꾸기:
```python
    g.add_conditional_edges("eligibility", route_eligibility, ["supervisor", "exclude", "hold", "handle_error"])
    g.add_conditional_edges("supervisor", supervisor.route,
                            ["technology", "market", "competitor", "investment", "handle_error"])
    for w in ("technology", "market", "competitor"):
        g.add_edge(w, "supervisor")  # 하위 에이전트는 supervisor와만 통신
```

찾기:
```python
    return g.compile()
```
바꾸기:
```python
    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 구 재검색 카운터 삭제**

`state.py`에서 아래 줄 삭제:
```python
    retrieve_count: int  # 구 구조용, Task 2a에서 삭제
```
`state.py` 맨 아래 `def next_attempt(...)` 함수 전체 삭제.

`config.py`에서 아래 줄과 그 다음 빈 줄 삭제:
```python
N_RETRIEVE_RETRY = 1
```

확인: `grep -rn "retrieve_count\|next_attempt\|N_RETRIEVE_RETRY\|route_retry" --include='*.py' .` 결과가 비어 있어야 한다 (`.venv` 제외).

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest -q` → 전체 PASS
Run: `uv run python app.py --graph | grep supervisor` → `supervisor -.-> technology`, `technology --> supervisor` 등 출력

- [ ] **Step 6: 커밋·push**

```bash
git add graph.py state.py config.py tests/test_skeleton.py tests/test_graph_flow.py
git commit -m "feat: [A] 고정 순서를 Supervisor 동적 라우팅으로 교체"
git push origin feat/agent-a-supervisor                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-a-supervisor -m "merge: [A] feat/agent-a-supervisor → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-a-supervisor && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 5 [D 성재원]: LLM Judge + 평가 노드 + 강제 종료

**선행 조건:** Task 0, Task 4 (본인)
```bash
until git fetch -q origin && git log origin/main --format=%s | grep -qF "feat: [B] Supervisor용 State"; do echo "Task 0 대기"; sleep 60; done && git merge origin/main   # 내 브랜치에서 실행
```

**Files:**
- Modify: `agents/evaluator.py` (최종 형태로 교체), `tests/test_evaluator.py` (최종 형태로 교체), `agents/report.py`, `prompts/report.md`

**Interfaces (Produces):**
- `EvaluationResult(BaseModel)`: `groundedness: bool`, `neutrality: bool`, `bias_control: bool`, `issues: list[str]` (필드 description = 평가 기준)
- `build_judge_prompt() -> str`
- `run(state) -> {"eval_result": {"passed", "score", "groundedness": {"passed","rule","judge"}, "neutrality": {...}, "bias_control": {...}, "issues"}, "report_attempts": int}`
- `route(state) -> "__end__" | "report" | "end_with_warning"`
- `end_with_warning(state) -> {"route_reason": "[경고] ..."}`
- `report._feedback(state) -> list[str] | None` — 미달이면 `eval_result.issues`를 report LLM 입력 `품질평가피드백`으로 전달 (첫 생성·통과면 None)
- LLM 호출은 `agents._report_llm.structured_call`을 모듈에 import해서 쓴다 (테스트는 `evaluator.structured_call`을 monkeypatch).

- [ ] **Step 1: 테스트 교체** — `tests/test_evaluator.py`를 아래 최종 내용으로 덮어쓴다

```python
from agents import evaluator
from agents.evaluator import EvaluationResult, rule_checks

EV = [
    {"근거ID": "TEC-02-0008", "publisher": "IRDS"},
    {"근거ID": "MKT-12-0001", "publisher": "SIA"},
    {"근거ID": "DIR-C03-01", "publisher": "창업진흥원"},
    {"근거ID": "CMP-C03-01", "publisher": "IEEE"},
]
GOOD = "기술 [TEC-02-0008] 시장 [MKT-12-0001] 경쟁 [CMP-C03-01] 기업 [DIR-C03-01]"


def _report(body: str) -> str:
    return f"## SUMMARY\n{body}\n\n## REFERENCE\n- 목록"


def test_all_rules_pass():
    assert all(c.passed for c in rule_checks(_report(GOOD), EV).values())


def test_groundedness_fails_on_unknown_or_no_citation():
    assert not rule_checks(_report("근거 없음"), EV)["groundedness"].passed
    assert not rule_checks(_report("[TEC-99-9999]"), EV)["groundedness"].passed


def test_neutrality_flags_banned_phrase():
    r = rule_checks(_report("압도적인 기술 " + GOOD), EV)
    assert not r["neutrality"].passed and "압도적" in r["neutrality"].reason


def test_bias_control_single_source():
    assert not rule_checks(_report("[TEC-02-0008] 또 [TEC-02-0008]"), EV)["bias_control"].passed


def test_bias_control_ignores_company_directory():
    body = "[DIR-C03-01] " * 10 + "[TEC-02-0008] [MKT-12-0001] [CMP-C03-01]"  # 기업 자체 소개는 편중 계산 제외
    assert rule_checks(_report(body), EV)["bias_control"].passed


def test_judge_prompt_built_from_schema():
    p = evaluator.build_judge_prompt()
    assert "1. groundedness" in p and "3. bias_control" in p and "issues" not in p.split("[평가 기준]")[1]


def _judge(ok: bool):
    return EvaluationResult(groundedness=ok, neutrality=True, bias_control=True,
                            issues=[] if ok else ["SUMMARY 2문장 수치 원문 없음"])


def _state(body: str):
    return {"final_report": _report(body), "report_attempts": 0,
            "evaluation_results": [{"company_id": "C03", "current_evidence": EV}]}


def test_run_passes_when_rules_and_judge_pass(monkeypatch):
    monkeypatch.setattr(evaluator, "structured_call", lambda *a: _judge(True))
    out = evaluator.run(_state(GOOD))
    assert out["eval_result"]["passed"] and out["eval_result"]["score"] == 1.0 and out["report_attempts"] == 1


def test_run_fails_when_judge_fails(monkeypatch):
    monkeypatch.setattr(evaluator, "structured_call", lambda *a: _judge(False))
    out = evaluator.run(_state(GOOD))
    assert not out["eval_result"]["passed"] and any("SUMMARY" in i for i in out["eval_result"]["issues"])
    assert out["eval_result"]["groundedness"]["rule"].startswith("인용 4건")


def test_eval_loop_terminates():
    assert evaluator.route({"eval_result": {"passed": True}, "report_attempts": 1}) == "__end__"
    assert evaluator.route({"eval_result": {"passed": False}, "report_attempts": 1}) == "report"
    assert evaluator.route({"eval_result": {"passed": False}, "report_attempts": 3}) == "end_with_warning"
    out = evaluator.end_with_warning({"eval_result": {"score": 0.67, "issues": ["x"]}})
    assert out["route_reason"].startswith("[경고]")
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_evaluator.py -q` → FAIL (`EvaluationResult` 없음)

- [ ] **Step 3: `agents/evaluator.py`를 아래 최종 내용으로 덮어쓴다**

```python
"""⑧ 보고서 품질 평가 — Hybrid (1안 룰 검사 + 2안 LLM Judge).

세 항목(Groundedness·중립성·편향 통제)은 룰과 Judge가 모두 통과해야 통과다.
미달이면 issues를 피드백으로 report에 넘겨 다시 쓰게 하고, 상한을 넘으면 end_with_warning으로 종료한다.
"""

import json
from collections import Counter

from pydantic import BaseModel, Field

from agents._report_llm import structured_call
from agents._report_render import ID_RE
from config import MAX_REPORT_REVISIONS, MAX_SOURCE_SHARE, MIN_PUBLISHERS
from obs import log_decision
from state import State

CRITERIA = ("groundedness", "neutrality", "bias_control")
# 중립성: 투자 판정은 코드 점수로만 내린다. 주관적 추천·우열 단정 표현 금지
BANNED = ("강력 추천", "강력히 추천", "반드시 투자", "최고의", "압도적", "독보적", "완벽한", "유일한")


class Criterion(BaseModel):
    passed: bool
    reason: str


class EvaluationResult(BaseModel):
    """LLM Judge 체크리스트. description이 곧 평가 기준이다 (build_judge_prompt가 읽음)."""

    groundedness: bool = Field(description="보고서의 수치·사실 주장이 인용근거의 원문발췌로 뒷받침된다. 원문에 없는 수치가 하나라도 있으면 False")
    neutrality: bool = Field(description="점수 근거 없이 특정 기업·기술을 추천하거나 경쟁 제품보다 낫다고 단정하지 않고, 강점과 리스크를 함께 서술한다")
    bias_control: bool = Field(description="불리한 근거(미확인 항목·열위·리스크)를 누락하지 않고, 한 출처에 결론을 의존하지 않는다")
    issues: list[str] = Field(description="미달 항목별로 어느 문장/섹션이 왜 미달인지. 모두 통과면 빈 리스트")


def build_judge_prompt() -> str:
    """EvaluationResult의 bool 필드 description으로 체크리스트를 만든다 → 기준 변경은 스키마만 수정."""
    lines = [f"{i}. {name}: {f.description}"
             for i, (name, f) in enumerate(EvaluationResult.model_fields.items(), 1) if f.annotation is bool]
    return ("너는 AI 반도체 스타트업 투자 평가 보고서의 품질 검수자다. 룰검사는 형식 검사이므로 너는 내용을 본다.\n"
            "아래 기준을 각각 True/False로 판정하고, False인 항목은 issues에 구체적으로 쓴다.\n\n"
            "[평가 기준]\n" + "\n".join(lines))


def rule_checks(report: str, evidence: list[dict]) -> dict[str, Criterion]:
    """1안: 형식만 검사한다 (내용은 보지 않음)."""
    body = report.split("## REFERENCE")[0]
    cited = ID_RE.findall(body)
    known = {e["근거ID"]: e for e in evidence if e.get("근거ID")}
    unknown = sorted(set(cited) - set(known))
    ground = Criterion(
        passed=bool(cited) and not unknown,
        reason="인용 없음" if not cited else (f"출처 없는 근거ID {unknown}" if unknown else f"인용 {len(set(cited))}건 모두 추적 가능"),
    )
    hits = [w for w in BANNED if w in body]
    neutral = Criterion(passed=not hits, reason=f"금지 표현 {hits}" if hits else "금지 표현 없음")
    # 기업 디렉토리(DIR-)는 평가 대상 자체 소개라 출처 편중 계산에서 제외하고 외부 근거로만 판정한다
    external = [i for i in cited if i in known and not i.startswith("DIR-")]
    pubs = Counter(known[i].get("publisher") or known[i].get("출처명") or "미상" for i in external)
    share = max(pubs.values()) / sum(pubs.values()) if pubs else 1.0
    bias = Criterion(
        passed=len(pubs) >= MIN_PUBLISHERS and share <= MAX_SOURCE_SHARE,
        reason=f"외부 출처 기관 {len(pubs)}곳, 최다 비중 {share:.0%} (기준 {MIN_PUBLISHERS}곳 이상, {MAX_SOURCE_SHARE:.0%} 이하)",
    )
    return {"groundedness": ground, "neutrality": neutral, "bias_control": bias}


def _all_evidence(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in records:
        for e in r.get("current_evidence") or []:
            if e.get("근거ID"):
                seen.setdefault(e["근거ID"], e)
    return list(seen.values())


def run(state: State) -> dict:
    report = state.get("final_report") or ""
    evidence = _all_evidence(state.get("evaluation_results") or [])
    rules = rule_checks(report, evidence)
    cited = set(ID_RE.findall(report.split("## REFERENCE")[0]))
    user = json.dumps({
        "보고서": report,
        "인용근거": [{"근거ID": e["근거ID"], "원문발췌": (e.get("원문발췌") or "")[:300]}
                    for e in evidence if e["근거ID"] in cited][:40],
        "룰검사": {k: v.model_dump() for k, v in rules.items()},
    }, ensure_ascii=False)
    judge = structured_call(EvaluationResult, build_judge_prompt(), user)
    result = {k: {"passed": rules[k].passed and getattr(judge, k), "rule": rules[k].reason,
                  "judge": getattr(judge, k)} for k in CRITERIA}
    score = sum(v["passed"] for v in result.values()) / len(CRITERIA)
    passed = score == 1.0
    issues = [f"{k}: {v['rule']}" for k, v in result.items() if not v["passed"]] + judge.issues
    attempts = state.get("report_attempts", 0) + 1
    log_decision(state, "evaluator", "pass" if passed else "fail", "; ".join(issues) or "3개 항목 충족")
    return {"eval_result": {"passed": passed, "score": score, **result, "issues": issues},
            "report_attempts": attempts}


def route(state: State) -> str:
    if (state.get("eval_result") or {}).get("passed"):
        return "__end__"
    if state.get("report_attempts", 0) > MAX_REPORT_REVISIONS:
        return "end_with_warning"
    return "report"


def end_with_warning(state: State) -> dict:
    """재생성 상한 초과 시 명시적 종료. 미달 상태를 기록하고 보고서는 그대로 둔다."""
    ev = state.get("eval_result") or {}
    reason = f"재생성 상한 {MAX_REPORT_REVISIONS}회 초과, 점수 {ev.get('score', 0):.2f}, 미달: {ev.get('issues', [])}"
    log_decision(state, "end_with_warning", "stop", reason)
    return {"route_reason": f"[경고] {reason}"}
```

- [ ] **Step 4: 피드백 반영 재작성 — `agents/report.py`** (노션 D·강의 Evaluator-Optimizer: 미달 사유를 Generator에 전달)

찾기:
```python
def _or_unknown(text: str) -> str:
```
바꾸기:
```python
def _feedback(state: State) -> list[str] | None:
    """직전 품질 평가 미달 사유 (evaluator → report 재생성 루프). 첫 생성이거나 통과면 None."""
    ev = state.get("eval_result") or {}
    return None if ev.get("passed", True) else ev.get("issues")


def _or_unknown(text: str) -> str:
```

찾기 (`_selected_report`의 payload 첫 줄):
```python
        "기업": company, "적격성": rec.get("eligibility"), "기술분석": rec.get("technology_analysis"),
```
바꾸기:
```python
        "품질평가피드백": _feedback(state),
        "기업": company, "적격성": rec.get("eligibility"), "기술분석": rec.get("technology_analysis"),
```

찾기 (`_no_selection_report`):
```python
    user = json.dumps({"mode": "no_selection", **payload,
```
바꾸기:
```python
    user = json.dumps({"mode": "no_selection", **payload, "품질평가피드백": _feedback(state),
```

`prompts/report.md` 끝에 추가:
```markdown

## 품질평가피드백
입력의 `품질평가피드백`이 null이 아니면 이전 보고서가 품질 평가(Groundedness·중립성·편향 통제)에서 미달한 것이다. 지적된 문장·표현을 우선 고친다. 근거로 뒷받침되지 않는 주장은 삭제하거나 "미확인"으로 쓰고, 추천·우열 단정 표현(예: 완벽한, 압도적, 독보적)은 쓰지 않는다. 기업 주장을 옮길 때는 "기업 자체 발표"임을 밝힌다.
```

`tests/test_evaluator.py` 끝에 추가:
```python


def test_report_receives_feedback_on_regeneration(monkeypatch, tmp_path):
    import json

    from agents import report
    from tests.test_report import _state as report_state

    seen = []
    monkeypatch.setattr(report, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(report, "export_pdf", lambda *a, **k: None)
    monkeypatch.setattr(report, "load_prompt", lambda n: "p")

    def fake(schema, system, user):
        seen.append(json.loads(user).get("품질평가피드백"))
        return report.ReportProse(summary="요약 [DIR-C07-01]", risks="- 위험 [DIR-C07-01]")

    monkeypatch.setattr(report, "structured_call", fake)
    report.run(report_state())  # 첫 생성
    report.run(report_state(eval_result={"passed": False, "issues": ["neutrality: 금지 표현 ['완벽한']"]}))
    report.run(report_state(eval_result={"passed": True, "issues": []}))
    assert seen == [None, ["neutrality: 금지 표현 ['완벽한']"], None]
```

실측: 기존 C03 결과로 보고서를 만들면 "완벽한 상호운용성"이 들어간다. 룰 메시지 한 줄(`neutrality: 금지 표현 ['완벽한']`)만 넣으면 그대로 남았고, evaluator가 실제로 만드는 형태(룰 사유 + Judge의 구체적 지적 문장)를 넣으면 사라졌다. 그래서 `evaluator.run`의 `issues`는 룰 사유와 Judge issues를 모두 담는다.

- [ ] **Step 5: 통과 확인** — `uv run pytest -q` 전체 PASS (`test_evaluator.py` 10개)

- [ ] **Step 6: 커밋·push**

```bash
git add agents/evaluator.py tests/test_evaluator.py agents/report.py prompts/report.md
git commit -m "feat: [D] LLM Judge 품질 평가 노드와 강제 종료 추가"
git push origin feat/agent-d-evaluator                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-d-evaluator -m "merge: [D] feat/agent-d-evaluator → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-d-evaluator && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 6 [B 박인우]: trace_id·체크포인터·LangSmith·`--only`

**선행 조건:** 코딩은 Task 0 직후 시작. **push는 Task 2a 이후** (`build_graph(checkpointer=...)` 필요)
```bash
until git fetch -q origin && git log origin/main --format=%s | grep -qF "feat: [A] 고정 순서를 Supervisor"; do echo "Task 2a 대기"; sleep 60; done && git merge origin/main   # 내 브랜치에서 실행
```

**Files:**
- Modify: `app.py`, `agents/loader.py`, `.env.example`, `tests/test_state.py`

**Interfaces (Produces):** `uv run python app.py [--only C03,C11] [--pdf]`. 실행 시작에 `trace_id` 출력, 끝에 `dynamic summary: {...}` 출력. `outputs/evaluation_results.json`에 `trace_id`, `eval_result`, `report_attempts` 포함.

- [ ] **Step 1: 테스트 추가** — `tests/test_state.py` 끝에 추가

```python


def test_loader_applies_company_filter(monkeypatch):
    from agents import loader
    monkeypatch.setattr(loader, "load_companies", lambda *a, **k: [{"company_id": c} for c in ("C01", "C03", "C11")])
    out = loader.run({"company_filter": ["C03", "C11"]})
    assert [c["company_id"] for c in out["candidate_companies"]] == ["C03", "C11"]
    assert len(loader.run({})["candidate_companies"]) == 3
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_state.py -q` → FAIL (필터 미적용, 3개 반환)

- [ ] **Step 3: `agents/loader.py`**

찾기:
```python
    입력: source_document
```
바꾸기:
```python
    입력: source_document, company_filter(선택: 지정한 company_id만 평가)
```

찾기:
```python
    companies = [c for c in load_companies(source) if not c.get("추출오류")]
    return {"candidate_companies": companies, "current_index": 0}
```
바꾸기:
```python
    companies = [c for c in load_companies(source) if not c.get("추출오류")]
    if only := set(state.get("company_filter") or []):
        companies = [c for c in companies if c["company_id"] in only]
    return {"candidate_companies": companies, "current_index": 0}
```

- [ ] **Step 4: `app.py`를 아래 최종 내용으로 덮어쓴다**

```python
"""실행: uv run python app.py [--as-of YYYY-MM-DD] [--only C03,C11] [--pdf] | --graph (mermaid 출력)"""

import argparse
import json
import uuid
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from config import DATA_DIR, EVALUATION_CRITERIA, MAX_CONCURRENCY, OUTPUT_DIR  # noqa: E402
from graph import build_graph  # noqa: E402
from obs import summarize  # noqa: E402
from agents._report_pdf import export_pdf, report_meta  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--graph", action="store_true", help="그래프 mermaid만 출력")
    p.add_argument("--pdf", action="store_true", help="5쪽 이내 PDF도 생성")
    p.add_argument("--only", default="", help="쉼표로 구분한 company_id만 평가 (예: C03,C11)")
    args = p.parse_args()

    app = build_graph(checkpointer=MemorySaver())  # 단계별 State 스냅샷 → 실패 지점 확인·재개
    if args.graph:
        print(app.get_graph().draw_mermaid())
        return

    trace_id = uuid.uuid4().hex[:12]
    print(f"trace_id: {trace_id}  (결정 로그: outputs/logs/{trace_id}.jsonl)", flush=True)
    config = {
        "recursion_limit": 3000,  # 45개사 × (Supervisor 왕복 포함) 노드 수
        "max_concurrency": MAX_CONCURRENCY,  # 병렬 노드 동시 실행 상한
        "configurable": {"thread_id": trace_id},  # checkpointer 키 = 상관 키
        "run_name": f"skala-agent-{trace_id}",
        "metadata": {"trace_id": trace_id},  # LangSmith에서 trace_id로 검색
        "tags": ["supervisor"],
    }
    result = {}
    for mode, update in app.stream(
        {
            "source_document": str(DATA_DIR / "raw" / "01_기업정보.pdf"),
            "as_of_date": args.as_of,
            "evaluation_criteria": EVALUATION_CRITERIA,
            "trace_id": trace_id,
            "company_filter": [c.strip() for c in args.only.split(",") if c.strip()],
        },
        config,
        stream_mode=["updates", "values"],
    ):
        if mode == "values":
            result = update
        else:
            for stage, values in update.items():
                company = (values or {}).get("current_company") or {}
                label = f" {company['company_id']} {company['기업명']}" if company else ""
                print(f"[{stage}]{label}", flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "report.md"
    out.write_text(result["final_report"], encoding="utf-8")
    print(f"saved: {out}")
    (OUTPUT_DIR / "evaluation_results.json").write_text(
        json.dumps({key: result.get(key) for key in ("trace_id", "as_of_date", "ranking", "selected_company_id",
                                                 "eval_result", "report_attempts", "evaluation_results", "errors")},
                   ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print("dynamic summary:", json.dumps(summarize(trace_id), ensure_ascii=False))
    if args.pdf:
        pdf = OUTPUT_DIR / "report.pdf"
        export_pdf(result["final_report"], report_meta(result), pdf)
        print(f"saved: {pdf}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: `.env.example` 끝에 추가** (각자 `.env`에도 실제 키를 넣는다)

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=skala-agent-supervisor
```

- [ ] **Step 6: 통과 확인** — `uv run pytest -q` 전체 PASS, `uv run python app.py --graph` 정상 출력

- [ ] **Step 7: 커밋·push**

```bash
git add app.py agents/loader.py .env.example tests/test_state.py
git commit -m "feat: [B] trace_id·체크포인터·LangSmith·기업 지정 실행 추가"
git push origin feat/agent-b-state                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-b-state -m "merge: [B] feat/agent-b-state → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-b-state && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 2b [A 김현수]: 품질 평가 루프 연결

**선행 조건:** Task 2a(본인), Task 5
```bash
until git fetch -q origin && git log origin/main --format=%s | grep -qF "feat: [D] LLM Judge"; do echo "Task 5 대기"; sleep 60; done && git merge origin/main   # 내 브랜치에서 실행
```

**Files:** Modify `graph.py`, `tests/conftest.py`, `tests/test_skeleton.py`

- [ ] **Step 1: 테스트 수정**

`tests/conftest.py`를 아래 최종 내용으로 덮어쓴다:

```python
"""외부 LLM 호출을 막는다. 새 노드의 LLM 진입점은 여기서 기본값으로 대체하고, 필요한 테스트만 다시 monkeypatch한다."""

import pytest


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch, tmp_path):
    import obs
    from agents import evaluator, supervisor
    from agents.evaluator import EvaluationResult

    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(supervisor, "_ask_llm", lambda state, candidates: None)  # → 규칙 정책
    monkeypatch.setattr(evaluator, "structured_call", lambda *a: EvaluationResult(  # Judge 통과 (룰 검사는 실제 수행)
        groundedness=True, neutrality=True, bias_control=True, issues=[]))
```

`tests/test_skeleton.py`의 `test_graph_compiles` 집합에 `"evaluator", "end_with_warning"`을 추가:
```python
    assert {"load", "eligibility", "supervisor", "technology", "market", "competitor", "investment", "report", "evaluator", "end_with_warning"} <= set(nodes)
```

`test_loop_flow_with_supervisor`의 마지막 줄 `assert obs.summarize("t")["reworks"] == 5 ...` **위에** 추가:
```python
    assert out["report_attempts"] == 3  # "ok"는 인용이 없어 룰 미달 → 재생성 2회 후 end_with_warning
    assert out["route_reason"].startswith("[경고]")
```

Run: `uv run pytest tests/test_skeleton.py -q` → FAIL (evaluator 노드 없음)

- [ ] **Step 2: `graph.py` 연결**

찾기:
```python
from agents import competitor, eligibility, investment, loader, market, report, supervisor, technology
```
바꾸기:
```python
from agents import competitor, eligibility, evaluator, investment, loader, market, report, supervisor, technology
```

찾기:
```python
    g.add_node("report", report.run)
```
바꾸기:
```python
    g.add_node("report", report.run)
    g.add_node("evaluator", evaluator.run)
    g.add_node("end_with_warning", evaluator.end_with_warning)
```

찾기:
```python
    g.add_edge("report", END)
```
바꾸기:
```python
    g.add_edge("report", "evaluator")
    g.add_conditional_edges("evaluator", evaluator.route, {"__end__": END, "report": "report",
                                                           "end_with_warning": "end_with_warning"})
    g.add_edge("end_with_warning", END)
```

- [ ] **Step 3: 통과 확인** — `uv run pytest -q` → 전체 PASS (예상 202 passed). `uv run python app.py --graph > outputs/graph.mmd` (README Architecture용)

- [ ] **Step 4: 커밋·push**

```bash
git add graph.py tests/conftest.py tests/test_skeleton.py
git commit -m "feat: [A] 보고서 품질 평가 루프 연결"
git push origin feat/agent-a-supervisor                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-a-supervisor -m "merge: [A] feat/agent-a-supervisor → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-a-supervisor && git merge main          # 내 브랜치를 최신 main으로
```

---

### Task 7 [전원]: 실행·트레이스·README·제출

**선행 조건:** Task 2b, Task 6
```bash
until git fetch -q origin && L=$(git log origin/main --format=%s) && echo "$L" | grep -qF "feat: [A] 보고서 품질 평가 루프" && echo "$L" | grep -qF "feat: [B] trace_id"; do echo "Task 2b·6 대기"; sleep 60; done && git merge origin/main   # 내 브랜치에서 실행
```

- [ ] **7-0 [E] README 초안 (Task P 직후부터)** — 아래 7-5 템플릿을 `README.draft.md`로 저장하고(커밋하지 않음), 실행 결과가 필요 없는 부분(Subject·Overview·Features·Tech Stack·Agents·State Schema·Directory·Usage·Contributors)을 이 문서 내용으로 먼저 다듬는다. `{}` 자리만 남긴다.

- [ ] **7-R [E] 머지마다 리뷰 (코드 수정 금지)** — 각 커밋이 origin에 올라오면 실행:
  ```bash
  git fetch origin && git switch --detach origin/main && uv run pytest -q && git log -3 --stat; git switch feat/agent-e-docs
  ```
  확인 항목: ① 커밋 메시지가 의존성 표와 일치 ② 바뀐 파일이 해당 레인 소유 파일뿐 ③ 이 문서의 해당 Task 코드와 다른 부분이 있는지 (`git show <커밋>`) ④ pytest 전체 통과. 문제가 있으면 해당 레인 담당에게 알리고 팀 채널에 남긴다.

- [ ] **7-1 [A] 통합 확인** — `uv run pytest -q` 전체 PASS를 팀 채널에 공지하고, `uv run python app.py --graph` 출력을 E에게 전달.

- [ ] **7-2 [B] 트레이스용 실행·캡처**
  1. `.env`에 `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=skala-agent-supervisor` 확인
  2. Run: `uv run python app.py --only C03` (적격 후보 1곳, 실측 약 3분)
  3. 출력된 `trace_id`로 LangSmith 프로젝트에서 run 검색 (`metadata.trace_id`)
  4. 다음이 보이게 캡처해 `tracing-1.png`, `tracing-2.png` … 로 저장: ① supervisor → technology·market **병렬** ② supervisor 재방문과 **재작업** 노드 ③ competitor ④ investment ⑤ report → evaluator (→ report 재생성 또는 END)
  5. 캡처 파일과 `trace_id`, 마지막 줄의 `dynamic summary`를 E에게 전달

- [ ] **7-3 [C] README 재료**
  - Selected Technologies: `data/processed/companies.json`에서 `공정|EDA|설계 자동화|검사|수율` 키워드 기업 수를 센다 (`uv run python -c "import json,re;c=json.load(open('data/processed/companies.json'));print(sum(bool(re.search('공정|EDA|설계 자동화|검사|수율',json.dumps(x,ensure_ascii=False))) for x in c))"`). 결과로 SW 줄을 확정해 E에게 전달
  - Tech Stack: 기존 README 값(gpt-4.1-mini, Chroma + bge-m3 dense/sparse RRF, Hit Rate@5 0.944, MRR@5 0.917, BAAI/bge-m3) 유지 + LangSmith

- [ ] **7-4 [C] 전체 실행**
  - Run: `uv run python app.py --pdf 2>&1 | tee outputs/run-full.log` (45개사)
  - 끝나면 `outputs/report.pdf`, `outputs/evaluation_results.json`, 마지막 줄 `dynamic summary`, `trace_id`를 E에게 전달
  - 1위·점수가 이전 결과(망고부스트코리아 79.0점)와 다르면 원인을 한 줄로 정리해 E에게 전달
  - 2:40까지 안 끝나면 중단하고 `uv run python app.py --only C03,C07,C18,C25 --pdf` 실행

- [ ] **7-5 [E] README.md 완성** — 7-0 초안의 `{}`를 7-2·7-3·7-4·7-6 결과로 채워 기존 README를 교체한다. Architecture는 A가 만든 `uv run python app.py --graph` 출력을 쓴다. 기존 README의 Results·Lessons Learned 중 여전히 맞는 내용은 아래쪽에 유지해도 된다.

````markdown
# Subject
본 프로젝트는 AI 반도체 스타트업을 하드웨어(AI 칩 설계)·소프트웨어(AI 기반 반도체 설계·공정) 두 진영에서 선정하여, 창업자·시장성·제품/기술력·경쟁 우위·실적 관점에서 투자 가능성을 평가하는 **Supervisor** 패턴 기반으로 설계/개발한 프로젝트임.

## Overview
- Objective : 하나의 기업을 기술·시장·경쟁 복수 관점에서 근거 기반으로 비교 평가하고 투자 적격 여부를 판정
- Pattern : Supervisor — 근거 충분성 판단과 관점별 재작업이 평가 품질의 핵심이고, 종료 조건·fallback을 중앙에서 통제해야 하므로 선정. Orchestrator-Workers는 실행 전 1회 계획이라 중간 근거 부족을 되돌릴 수 없고, Agent-as-Tool은 정적 흐름에서 도구 호출과 차이가 없으며, Swarm은 재현성 보장이 어려워 제외
- 동적 처리 : 기존에는 `technology → market → competitor` 순서와 재검색 횟수가 엣지로 고정됐다. 지금은 Supervisor가 매 라운드 State(수집된 관점·근거 충분도·실패·실행 횟수)를 보고 `next`를 정한다. 기술·시장은 병렬로 실행하고, 세 관점이 모인 뒤 근거가 부족한 관점만 골라 재작업을 지시한다(LLM 판단 + 규칙 가드). 실행 횟수는 기업마다 다르다 (실측: {dynamic summary})

## Selected Technologies
- SW : AI 기반 반도체 설계·공정 SW — {7-3 결과: 디렉토리북 해당 기업 수와 평가 포함 여부}
- HW : AI 반도체 칩 (NPU·DPU·AI 가속기) — IRDS·UCIe·CXL 기준값으로 성능을 정량 비교할 수 있고, 디렉토리북 시스템반도체 분야 45개사 대부분이 해당

## Features
- PDF 자료 기반 정보 추출 (디렉토리북 45개사 + 기술 로드맵·시장 보고서 15개 PDF 169쪽)
- Supervisor 동적 라우팅: 관점별 근거 충분도 판단 → 부족한 관점만 재작업 (병렬)
- 확증 편향 방지 전략 : 보고서 인용 외부 출처 기관 3곳 이상·단일 기관 비중 50% 이하 룰 검사(평가 대상 기업 소개 자료는 계산 제외), LLM Judge가 불리한 근거(미확인·열위·리스크) 누락 검사, 투자 판정은 LLM이 아니라 코드 점수로만
- 보고서 품질 평가 : Hybrid(룰 + LLM Judge)로 Groundedness·중립성·편향 통제 판정, 미달 사유를 피드백으로 넣어 최대 2회 재작성 후 경고 종료

## Tech Stack
- Framework : LangGraph, LangChain, Python
- LLM/Generator : gpt-4.1-mini
- LLM/Judge : gpt-4.1-mini (Supervisor 재작업 판단, 품질 평가 Judge)
- Retrieval : Chroma + bge-m3 dense/sparse RRF — Hit Rate@5 0.944, MRR@5 0.917
- Embedding : BAAI/bge-m3
- Observability : LangSmith, JSONL 결정 로그

## Agents
- Supervisor : 기업별 분석 구간 통제. 규칙 ① step 상한 → 투자 판단 ② 기술 재시도 후 실패 → 보류 ③ 기술·시장 미수행/실패 → 병렬 실행 ④ 경쟁 미수행/실패 → 실행 ⑤ 근거 부족 관점 → LLM이 재작업 대상 또는 투자 판단 선택 ⑥ 충분·상한 → 투자 판단
- 기술 요약 [RAG] : IRDS·UCIe·CXL 기준값 대조, 재작업 사유로 질의 재작성
- 시장성 평가 [RAG] : SIA·WSTS·KIET·OECD 대조
- 경쟁사 비교 : RAG + Tavily, 기술·시장 결과를 비교 기준으로 사용
- 투자 판단 : 체크리스트 11문항 + 스코어카드 15항목, LLM 3회 채점 → 코드 집계·판정
- 보고서 생성 / 품질 평가 : SUMMARY·REFERENCE 포함 보고서 → 룰 + LLM Judge

## State Schema
- 제어 vs 페이로드 분리 : ② 흐름 제어(`next`, `step_count`, `max_steps`, `rework_reason`, `node_status`, `agent_attempts`, `last_error`)와 ③ 작업 산출물(`*_analysis`, `current_evidence`, `scorecard`)을 그룹으로 분리. 산출물은 Pydantic 스키마로 구조화(`근거ID` 포함)
- 관측성 위치 : 결정과 사유 전체는 `outputs/logs/{trace_id}.jsonl`(`{trace_id, company_id, node, decision, reason, ts}`)과 LangSmith로 분리. State에는 마지막 사유 1줄(`route_reason`)만
- 지속성 비용 : 기업 전환 시 ③과 제어 필드 리셋, 원문 전문은 `.cache/`에 두고 State는 발췌만. MemorySaver는 변경된 채널만 새 버전으로 저장
- 상관 : `trace_id` 하나를 State·JSONL 로그·LangSmith metadata·checkpointer `thread_id`에 동일하게 사용
- 재개/복구 : `node_status`(SUCCESS/FAILED), `agent_attempts`(재시도 횟수), `last_error`·`errors`(`{company_id, stage, type, error, ts}`)로 무엇을 재시도할지 판단. MemorySaver 스냅샷, 외부 조사 캐시
- 동시 처리 : 병렬 노드가 쓰는 `node_status`·`agent_attempts`는 `merge_dict`, `current_evidence`는 `merge_evidence`, `errors`·`evaluation_results`는 `operator.add`. 단일 값 키(`retrieve_count`) 제거, 검색기 Lock, `max_concurrency=4`
- 종료 보장 : 에이전트별 재작업 1회, 기업별 Supervisor 6스텝, 보고서 재생성 2회 후 `end_with_warning`, `recursion_limit=3000`

## Architecture
```mermaid
{outputs/graph.mmd 내용}
```

## Directory Structure
```text
├── data/            # 원천 PDF 15개, manifest, 기업 레코드
├── agents/          # supervisor(조정 계층) · technology · market · competitor(하위 에이전트) · investment · report · evaluator
├── rag/             # PDF 파싱·청킹, bge-m3 하이브리드 검색
├── tools/           # 검색 도구, DART·Tavily 외부 조사
├── prompts/         # 역할별 프롬프트
├── outputs/         # report.md · report.pdf · evaluation_results.json · logs/{trace_id}.jsonl
├── tests/           # 단위·그래프 통합 테스트
├── state.py · graph.py · obs.py · config.py
├── app.py           # 실행 스크립트
└── README.md
```

## Usage
```bash
uv sync && cp .env.example .env   # OPENAI_API_KEY, TAVILY_API_KEY, LANGSMITH_* 입력
uv run python app.py --pdf          # 45개사 전체
uv run python app.py --only C03     # 지정 기업만 (트레이스 캡처용)
uv run python app.py --graph        # 그래프 mermaid 출력
```
제출 trace : `{trace_id}` (LangSmith 프로젝트 skala-agent-supervisor, `tracing-*.png`)

## Contributors
- 김세령 : 통합 리뷰(계획 대비 구현 검수), README·제출물 작성, 평가 보고서 검수
- 김현수 : Supervisor 설계·구현(Hybrid 라우팅), 그래프 재구성, 통합 테스트
- 박인우 : State Schema 설계, 관측성(trace_id·결정 로그·LangSmith), 체크포인터·실행 옵션, 트레이스 캡처
- 박세웅 : 하위 에이전트 병렬·재작업 대응, 질의 재작성, 검색기 동시성 처리, 전체 실행·결과 분석
- 성재원 : 보고서 품질 평가(룰 + LLM Judge), 피드백 반영 재작성 루프·강제 종료
````

커밋·머지 (`feat/agent-e-docs`에서):
```bash
git add README.md && git commit -m "docs: [E] Supervisor 패턴 README 작성"
git push origin feat/agent-e-docs                      # 내 브랜치 백업
git switch main && git pull origin main
git merge --no-ff feat/agent-e-docs -m "merge: [E] feat/agent-e-docs → main"   # 충돌 시 해결 후 커밋, 남의 파일이면 담당에게 확인
uv run pytest -q && git push origin main     # 실패하면 push하지 말고 고친다
git switch feat/agent-e-docs && git merge main          # 내 브랜치를 최신 main으로
```

- [ ] **7-6 [E] 평가 보고서 확인** — 7-4의 `outputs/report.pdf` (C에게 받음)
  - `pdfinfo outputs/report.pdf | grep Pages` → **10 이하**
  - SUMMARY와 REFERENCE 목차가 있는지 확인
  - `outputs/evaluation_results.json`의 `eval_result`(통과 여부·점수·issues·`report_attempts`)를 README Features에 한 줄로 적는다

- [ ] **7-7 [E] 제출**
  - zip 구성: `github_link.txt`(Agent 과제: `https://github.com/kimhynsoo/skala-rag` (main), 이전 RAG 과제: `https://github.com/kimhynsoo/skala-rag/tree/rag-pjt`), `tracing-1.png`… , `report.pdf`
  - 파일명: `Agent_울산캠퍼스_4반_김세령+김현수+박세웅+박인우+성재원.zip`
  - 반별 Slack thread에 업로드

---

## 실측 결과 (검증 worktree, 2026-10-13)

`uv run python app.py --only C03` (망고부스트코리아, LangSmith 끔), 기업 1곳 약 3분.

**1차 실행 (검색기 Lock 없음):** technology·market 첫 병렬 실행이 둘 다 `FAILED`, 재시도에서 CPU 196%로 10분 넘게 정지 → Task 3 Step 6의 Lock 추가.

**2차 실행 (Lock 추가):**

```
supervisor ['technology', 'market']  필수 실행: technology=미수행; market=미수행
technology SUCCESS attempt 1          ┐ 병렬
market     SUCCESS attempt 1          ┘
supervisor ['competitor']             기술·시장 확보 → 경쟁 비교 (미수행)
competitor SUCCESS attempt 1
supervisor ['technology', 'market']   LLM 판단: 기술과 시장 관점 모두 근거가 충분하지 않아 재작업으로 보완 가능성이 높기 때문
technology SUCCESS attempt 2          ┐ 병렬 재작업
market     SUCCESS attempt 2          ┘
supervisor ['investment']             모든 관점 근거 충분 또는 재작업 상한 도달 → 투자 판단
→ C03 투자 적격 78.0점 (기존 순차 구조 79.0점)
evaluator fail × 3 → end_with_warning (bias_control: 출처 기관 10곳, 최다 비중 61%)
dynamic summary: {"supervisor_routes": 4, "agent_runs": {"technology": 2, "market": 2, "competitor": 1}, "reworks": 2, "evaluations": ["fail", "fail", "fail"]}
```

→ 편향 통제 룰이 기업 자체 소개(DIR, 46건 중 28건)까지 세고 있어 항상 미달 → Task 4에서 DIR 제외.

**3차 실행 (DIR 제외):** Supervisor 경로는 2차와 동일. 품질 평가는 `bias_control` 통과, `neutrality`가 3회 모두 미달 (보고서의 "완벽한 상호운용성" 표현) → `end_with_warning`으로 정상 종료.

→ 피드백 없이 같은 입력으로 재생성하면 같은 표현이 반복된다. 그래서 Task 5 Step 4에 피드백 반영 재작성을 넣었다.

**피드백 반영 확인 (실제 LLM):** 기존 C03 결과로 보고서 생성 → "완벽한" 포함. 룰 사유 + Judge 지적 문장을 `품질평가피드백`으로 넣고 재생성 → 금지 표현 0건. 단위 테스트: 원본 코드 + 이 변경만 적용 시 176 passed.
