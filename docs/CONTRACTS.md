# 협업 계약: 파일 소유권 · 데이터 구조

병렬 작업의 규칙은 두 가지다.
1. **내 레인 파일만 수정한다.** 보호 파일은 PR + 전원 합의로만 바꾼다.
2. **레인 사이를 오가는 데이터는 이 문서의 스키마를 따른다.** 스키마를 바꾸려면 이 문서를 먼저 PR로 고친다.

> 이 문서의 키 이름·ID 형식은 **초안**이다. 킥오프에서 확정하면 이 줄을 지운다.

---

## 1. 파일 소유권

### 🔒 보호 파일 — 직접 수정 금지

| 파일 | 이유 | 바꿔야 할 때 |
|---|---|---|
| `state.py` | 전 노드가 공유하는 State. 키 하나 바뀌면 전원 코드가 깨짐 | 이 문서 + `state.py` 동시 PR, 전원 리뷰 |
| `graph.py` | 흐름 제어(리셋·재검색·오류·루프·순위)가 테스트로 고정됨 | 설계 문서(Notion) 먼저 수정 → PR |
| `config.py` | 설계에서 확정한 상수 (청크, top-k, 가중치, 임계값) | 설계 문서 변경 근거와 함께 PR |
| `app.py` | 실행 진입점 | PR |
| `schemas.py` | 3장 데이터 구조의 Pydantic 모델. LLM 출력 형식과 판정 규칙(적격성·확인 불가 2점)을 강제 | 이 문서 + `schemas.py` 동시 PR, 전원 리뷰 |
| `llm.py` | LLM 호출 공통 (`get_llm`, `run_agent`, `load_prompt`) | PR |
| `tests/test_skeleton.py` | 흐름 계약 테스트. **통과 못 하면 merge 금지** | 흐름 변경 PR에서만 |
| `pyproject.toml`, `uv.lock` | 공용 환경 | **`uv add`/`uv remove`로만** 변경, 손 편집 금지 |
| `.gitignore`, `.env.example` | 공용 설정 | PR |
| `docs/CONTRACTS.md` (이 문서) | 레인 간 계약 | PR, 전원 리뷰 |

### 레인별 소유 파일 — 담당자만 수정

| 레인 | 소유 (자유 수정) | 새 파일 추가 가능 위치 |
|---|---|---|
| **A 데이터·파싱** | `rag/parser.py`, `agents/loader.py`, `data/raw/*`, `data/manifest.json`, `data/processed/*` | `data/`, `rag/parse_*.py` |
| **B 검색·임베딩** | `rag/retriever.py`, `tools/retrieval.py`, `eval/*` | `rag/index_*.py`, `eval/` |
| **C 외부 검증** | `agents/eligibility.py`, `agents/competitor.py`, `tools/web.py`, `tools/dart.py`, `prompts/eligibility.md`, `prompts/competitor.md` | `tools/` (웹서치·DART 등 외부 도구) |
| **D RAG 분석** | `agents/technology.py`, `agents/market.py`, `prompts/technology.md`, `prompts/market.md` | `agents/_rag_utils.py` |
| **E 판단·보고서** | `agents/investment.py`의 `run()`, `agents/report.py`, `prompts/investment.md`, `prompts/report.md`, `outputs/*`, `README.md` | `agents/_report_*.py` |

- `agents/investment.py`의 `total_score`·`decide`·`rank_key`는 테스트로 고정된 판정 규칙이라 **보호 대상**이다. E는 `run()`만 구현한다.
- 남의 레인 함수가 필요하면 **import해서 쓰고, 고치지 않는다.** 버그를 찾으면 담당자에게 이슈나 메시지로 알린다.
- 각 에이전트는 **자기 출력 키만 반환**한다. 예를 들어 D가 `eligibility`를 반환하면 안 된다.

### ⛔ 절대 커밋 금지

`.env`(API 키), `.venv/`, `.cache/` — `.gitignore`로 막혀 있지만 `git add -f`도 쓰지 않는다.

`data/processed/companies.json`(LLM 추출 결과)은 **커밋한다.** 재실행할 때 API 비용이 들지 않고 결과가 재현되기 때문이다.

---

## 2. 데이터 흐름

```
data/raw/*.pdf ──A──▶ manifest.json ─┐
                                     ├─A──▶ 청크(Document) ──B──▶ 인덱스 ──B──▶ hybrid_search()
01_기업정보.pdf ─A──▶ 기업 레코드 ────┘                                           │
        │                                                                         │
        ▼                                                                         ▼
  current_company ──C──▶ eligibility ──D──▶ technology_analysis ──D──▶ market_analysis
                                                                                  │
                         ┌──C──▶ competitor_analysis ◀────────────────────────────┘
                         ▼
                    E: checklist · scorecard · decision ──graph──▶ evaluation_results[]
                                                                        │
                                                    graph.rank ──▶ ranking · selected_company_id
                                                                        │
                                                                   E: final_report
모든 분석 단계(A·C·D)는 근거 레코드를 current_evidence에 추가한다.
```

---

## 3. 데이터 구조

표기: `str | None`은 값이 없을 수 있음. 모든 날짜는 `"YYYY-MM-DD"`, 금액은 **천원 단위 int**.

### 3-1. manifest (A 작성 → A·B 사용) — `data/manifest.json`

```jsonc
[
  {
    "doc_id": "02",
    "file": "02_AI_컴퓨팅.pdf",
    "doc_type": "tech",                 // company | tech | market
    "sub_domain": "ai_computing",       // 3-9 매핑표 값
    "title": "IRDS 2024 More Moore",
    "publisher": "IEEE",
    "pub_year": 2024,
    "source_type": "기관 보고서",        // 기관 보고서 | 학술 논문 | 웹페이지
    "url": "https://...",
    "page_map": {"1": 5, "2": 6}        // 추출 페이지 → 원본 페이지
  }
]
```

### 3-2. 청크 (A 생성 → B 색인) — `langchain_core.documents.Document`

```python
Document(
    page_content="...700자 이내...",
    metadata={
        # manifest의 doc_id·doc_type·sub_domain·title·publisher·pub_year·source_type·url 전부 +
        "chunk_id": "02-0007",          # {doc_id}-{4자리 순번}
        "source_page": 17,              # 원본 페이지 (REFERENCE 표기용)
        "output_page": 11,              # 추출 PDF 페이지
    },
)
```

`hybrid_search()`는 위 `Document` 리스트를 반환하고, B가 `metadata["score"]`(RRF 점수)를 추가한다.

### 3-3. 기업 레코드 (A 작성 → 전원 읽기) — `candidate_companies[i]`, `current_company`

```jsonc
{
  "company_id": "C01",                  // C01~C45, 디렉토리북 수록 순
  "기업명": "OO반도체",
  "홈페이지": "https://..." ,           // 없으면 null
  "설립일": "2019-03-01",
  "대표자명": "홍길동",
  "직원수": 23,
  "업종": "시스템반도체 설계",
  "기술분야": "AI 가속기",
  "sub_domain": "ai_computing",         // D의 검색 필터용 (3-9)
  "메인아이템": "엣지 NPU",
  "주요구성원": [{"이름": "", "직책": "CEO", "학력": "", "경력": ""}],
  "매출액": {"연도": 2024, "국내": 21818, "해외": null, "상태": "공개"},   // 상태: 공개 | N/A | 비공개
  "투자유치이력": [{"일자": "2024-05-01", "단계": "Series A", "금액": 5000000, "투자자": ["..."], "확정": true}],
  "지식재산권": {"등록": [{"번호": "10-2532099", "명칭": ""}], "출원": []},
  "인증수상": ["..."],
  "주요거래처": ["..."],
  "개발진척도": "시제품",
  "TRL": 6,                             // 명시 없으면 null
  "혁신성": "...",
  "사업Point": "...",
  "source_page": 12
}
```

### 3-4. 근거 레코드 (A·C·D 작성 → E 읽기) — `current_evidence[i]`

```jsonc
{
  "근거ID": "TEC-02-0007",              // RAG: {TEC|MKT}-{chunk_id} / 그 외: {접두어}-{company_id}-{2자리}
  "출처명": "IRDS 2024 More Moore",
  "publisher": "IEEE",
  "pub_year": 2024,                     // 웹페이지는 "2026-09-30"처럼 날짜 문자열
  "source_type": "기관 보고서",
  "url": "https://...",
  "source_page": 17,                    // 웹은 null
  "확인일": "2026-09-30",
  "원문발췌": "300자 이내",
  "chunk_id": "02-0007"                 // RAG 근거만, 그 외 null
}
```

| 근거ID 접두어 | 생성 레인 | 출처 |
|---|---|---|
| `DIR` | A | 디렉토리북 기업 페이지 |
| `ELG` | C | DART·웹 (적격성) |
| `TEC` | B 도구 (`search_tech_docs`) | 기술 문서 RAG — `TEC-{chunk_id}` |
| `MKT` | B 도구 (`search_market_docs`) | 시장 문서 RAG — `MKT-{chunk_id}` |
| `CMP` | C | 경쟁사 웹검색 (RAG 재조회분은 TEC/MKT 그대로) |

RAG 근거ID는 검색 도구가 결과에 `[TEC-02-0007]`처럼 붙여 LLM에 보여주고, `tools.retrieval.to_evidence()`가 같은 규칙으로 근거 레코드를 만든다. 같은 청크는 몇 번 검색돼도 같은 ID라 재매핑이 필요 없다.

분석 결과 dict의 `근거ID` 리스트에는 **이 ID만** 넣는다. 보고서는 이 ID로 REFERENCE를 만든다.

### 3-5. eligibility (C) 

```jsonc
{
  "판정": "적격",                        // 적격 | 부적격 | 확인필요  ← graph가 이 값으로 분기
  "G1": {"결과": "충족", "사유": "DART 종목코드 없음", "근거ID": ["ELG-C03-01"]},   // 결과: 충족 | 미충족 | 확인불가
  "G2": {...}, "G3": {...}, "G4": {...},
  "사유": "G1~G4 모두 충족",
  "근거ID": ["ELG-C03-01", "..."]
}
```

### 3-6. technology_analysis · market_analysis (D)

```jsonc
// technology_analysis
{
  "핵심기술": "...",
  "제품성숙도": {"TRL": 6, "단계": "시제품"},
  "성능지표": [{"지표명": "TOPS/W", "값": "12", "측정조건": "INT8, 7nm", "검증수준": "자체 발표", "근거ID": ["DIR-C03-01"]}],
  "기준대조": [{"지표명": "TOPS/W", "업계기준": "...", "비교결과": "상회|동등|하회|비교불가", "근거ID": ["TEC-C03-02"]}],
  "강점": ["..."], "한계": ["..."], "미확인정보": ["..."],
  "근거ID": ["..."],
  "근거충분": true                      // ← graph가 재검색 분기에 사용 (필수)
}
// market_analysis
{
  "목표고객": ["..."],
  "시장규모": {"값": "USD 00B", "기준연도": 2025, "근거ID": ["MKT-C03-01"]},
  "성장률": {"값": "CAGR 00%", "기간": "2025-2030", "근거ID": ["..."]},
  "사업모델": "...", "글로벌확장성": "...",
  "성장요인": ["..."], "위험": ["..."], "미확인정보": ["..."],
  "근거ID": ["..."],
  "근거충분": true
}
```

재시도할 때 D는 `retrieve_count: next_attempt(state, "<출력키>")`도 함께 반환한다(`state.py` 제공).

### 3-7. competitor_analysis (C)

```jsonc
{
  "경쟁제품": [{"기업명": "", "제품": "", "핵심지표값": [{"이름": "TOPS/W", "값": "20"}], "근거ID": ["CMP-C03-01"]}],
  "비교표": [{"지표": "TOPS/W", "대상기업": "12", "경쟁사": [{"이름": "경쟁사A", "값": "20"}, {"이름": "경쟁사B", "값": "8"}]}],   // 임의 키 dict 금지 → list
  "우위": ["..."], "열위": ["..."],
  "비교조건": "공개 스펙 기준, 측정 조건 상이",
  "비교한계": "...",
  "근거ID": ["..."]
}
```

### 3-8. checklist · scorecard · decision (E)

```jsonc
// checklist — Q1~Q11
{"Q1": {"판정": "YES", "근거": "...", "근거ID": ["DIR-C03-01"]}}   // YES | PARTIAL | NO | 확인불가

// scorecard — total/averages/unknown_items는 total_score()로 계산, LLM이 직접 쓰지 않음
{
  "items": {"A1": {"점수": 4, "채점이유": "...", "근거ID": ["..."], "확인불가": false}},   // A1~E3 15개, 점수 1~5. 확인불가=true면 점수 자동 2
  "averages": {"창업자": 3.7, "시장성": 3.0, "제품/기술력": 3.3, "경쟁 우위": 2.7, "실적": 2.0},
  "total": 63.5,
  "unknown_items": ["B1", "E3"]          // 확인 불가(2점) 처리 항목 ← 순위 3순위 기준
}

// decision: "투자 적격" | "보류" | "제외"   ← decide()로 계산
// decision_details
{"판단사유": "...", "주요위험": ["..."], "추가확인사항": ["..."], "재검토조건": ["..."]}
```

### 3-9. sub_domain 매핑 (A·D 공동 확정)

| sub_domain | 기술 문서 | 해당 기업 기술분야 예시 |
|---|---|---|
| `ai_computing` | 02 | NPU, AI 가속기, 데이터센터 칩 |
| `packaging` | 03 | 칩렛, 첨단 패키징 |
| `power` | 04 | 전력반도체 (G4 탈락 가능성 높음) |
| `rf_sensor` | 05 | RF, 센서 |
| `memory` | 06 | PIM, 메모리 컨트롤러 |
| `interface` | 07, 08 | UCIe, CXL, 인터커넥트 IP |
| `materials` | 09 | 신소자, 소재 |
| `metrology` | 10 | 계측, AI 기반 공정 모니터링 |
| `yield` | 11 | 수율, 결함 검사 |

시장 문서(12~15)는 `sub_domain` 없이 `doc_type="market"`만 사용한다.

### 3-10. graph가 만드는 구조 — 수정 금지, 읽기만

```jsonc
// evaluation_results[i] — graph.save
{
  "company_id": "C03",
  "current_company": {...}, "eligibility": {...}, "checklist": {...},
  "technology_analysis": {...}, "market_analysis": {...}, "competitor_analysis": {...},
  "scorecard": {...}, "decision": "투자 적격", "decision_details": {...},
  "route_reason": "", "current_evidence": [...]   // 이 기업의 근거만
}
// errors[i] — graph.guarded
{"company_id": "C05", "stage": "technology", "error": "RuntimeError(...)"}
// ranking: ["C12", "C03"]   selected_company_id: "C12" | None — graph.rank
```

보고서(E)는 State의 `current_*` 필드가 아니라 **`evaluation_results`에서 `selected_company_id` 레코드를 찾아** 사용한다.

---

## 4. LLM·도구 사용 패턴 (교재 10-Agent 방식)

모든 LLM 에이전트는 `llm.run_agent()` 하나로 호출한다. `create_agent` + `ToolStrategy(Pydantic 모델)` 조합이라 **LLM이 도구를 스스로 골라 쓰고, 마지막 출력은 스키마 형식으로 강제**된다.

```python
from llm import load_prompt, run_agent
from schemas import TechnologyAnalysis
from state import next_attempt
from tools.retrieval import search_tech_docs, to_evidence

def run(state):
    c = state["current_company"]
    result, artifacts = run_agent(load_prompt("technology"), f"기업: {c['기업명']} / 메인아이템: {c['메인아이템']} ...",
                                  TechnologyAnalysis, tools=[search_tech_docs])
    return {"technology_analysis": result.model_dump(),
            "current_evidence": to_evidence(artifacts),
            "retrieve_count": next_attempt(state, "technology_analysis")}
```

| 에이전트 | 출력 스키마 | 도구 |
|---|---|---|
| ① 후보 적재 (A) | `CompanyRecord` | 없음 (페이지 텍스트를 직접 입력) |
| ② 적격성 (C) | `Eligibility` — `판정`은 자동 계산 | `dart_listing_status`, `web_search()` |
| ③ 기술 요약 (D) | `TechnologyAnalysis` | `search_tech_docs` |
| ④ 시장성 (D) | `MarketAnalysis` | `search_market_docs` |
| ⑤ 경쟁사 (C) | `CompetitorAnalysis` | `search_tech_docs`, `search_market_docs`, `web_search()` |
| ⑥ 투자 판단 (E) | `InvestmentJudgement` → `scorecard.scores()`를 `total_score()`에 | 없음 |

- **클래스명은 영문**(OpenAI 함수명 규칙), **필드명은 한글 계약 키**. 새 모델을 추가해도 `tests/test_tools.py`가 규칙 위반을 잡는다.
- `web_search()`는 함수 호출로 도구를 만든다 (TAVILY_API_KEY가 없어도 import는 되도록).
- 실측 교훈: 도구 설명(docstring)이 곧 LLM의 사용 설명서다. `sub_domain` 의미를 적기 전에는 LLM이 필터를 잘못 골라 정답 문서를 놓쳤다.

## 5. 가짜 데이터로 먼저 개발하기

선행 레인을 기다리지 않도록 각 레인은 위 스키마대로 **가짜 입력 fixture**를 만들어 개발한다.
- D: 가짜 `hybrid_search` 결과(`Document` 5개)로 프롬프트를 먼저 다듬는다
- E: 가짜 `evaluation_results` 3건(투자 적격 2, 보류 1)으로 보고서 템플릿을 먼저 만든다
- 흐름 전체: `tests/test_skeleton.py::test_loop_flow_with_fake_agents`에 가짜 에이전트를 끼우는 예시가 있다
