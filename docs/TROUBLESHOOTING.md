# 트러블슈팅

문제를 해결하면 아래 형식(증상 → 원인 → 해결 → 하지 말 것)으로 추가한다.

### `OMP: Error #15` / 세그폴트(exit 139) / `Fatal Python error: Aborted` — torch와 faiss 동시 사용

- **증상**: 임베딩(bge-m3, torch) 후 벡터 검색(faiss)을 하면 프로세스가 죽는다. import 순서나 실행 타이밍에 따라 될 때도 있어 재현이 불안정하다.
- **원인**: `torch/lib/libomp.dylib`와 `faiss/.dylibs/libomp.dylib`가 각각 설치되어, 한 프로세스에 **OpenMP 런타임이 두 개** 올라간다 (macOS에서 흔함).
- **해결 (적용됨)**: faiss 의존성을 제거하고 dense 저장소를 **Chroma**(`langchain-chroma`)로 교체했다. Chroma는 자체 libomp를 싣지 않아 torch와 한 프로세스에서 반복 실행해도 안정적이다(3회 연속 검증). → `rag/retriever.py`
  - 중간 단계로 numpy 전수 내적도 검증했다. FAISS `IndexFlatIP`와 순위가 완전히 같았다.
- **하지 말 것**: `KMP_DUPLICATE_LIB_OK=TRUE` 환경변수 우회. OpenMP 공식 경고대로 크래시나 잘못된 결과가 날 수 있다.
- **재발 방지**: `uv add faiss-cpu`나 `langchain_community.vectorstores.FAISS`를 다시 쓰지 않는다. 교재의 FAISS 예제가 문제없던 이유는 OpenAI 임베딩을 써서 torch가 없었기 때문이다.

### `chromadb.errors.InvalidArgumentError: ... Expected a name containing 3-512 characters`

- **원인**: Chroma 컬렉션 이름은 3~512자, 영문·숫자·`._-`만 허용한다.
- **해결**: 컬렉션 이름을 `corpus`로 고정했다 (`rag/retriever.COLLECTION`).

### Chroma에 메타데이터 저장 시 오류 (값이 `None`)

- **원인**: Chroma 메타데이터 값은 str·int·float·bool만 허용하고 `None`은 넣을 수 없다. 시장 문서처럼 `sub_domain`이 없는 청크가 여기에 해당한다.
- **해결**: 저장할 때 `None` 값인 키를 빼고 넣는다. 검색 결과는 원본 청크(`_docs`)에서 돌려주므로 메타데이터가 사라지지 않는다.

### `Invalid 'tools[1].function.name': string does not match pattern '^[a-zA-Z0-9_-]+$'`

- **원인**: `create_agent(response_format=ToolStrategy(모델))`은 Pydantic **클래스명**을 OpenAI 함수명으로 쓴다. 함수명은 영문·숫자·`_-`만 허용된다 (한글 클래스명 `class 분석(BaseModel)` 불가).
- **해결**: 클래스명은 영문(`TechnologyAnalysis`), **필드명은 한글 가능**(`핵심기술`, `근거ID`). 실제 호출로 검증함. `tests/test_tools.py::test_models_are_openai_structured_output_safe`가 규칙을 강제한다.

### LLM이 검색 필터를 잘못 골라 정답 문서를 놓침

- **증상**: "메모리 확장 컨트롤러" 기업 분석에서 LLM이 `sub_domain="memory"`로 검색 → CXL 문서(`interface`)를 못 찾고 엉뚱한 근거로 판정.
- **해결**: `search_tech_docs` docstring에 분야별 포함 문서와 "애매하면 필터 없이 재검색" 지침을 추가 → 재실행 2회 모두 CXL·UCIe 문서를 찾음.

### 에이전트 실행이 10분 넘게 멈춤 (CPU 0%, OpenAI 연결 하나만 열려 있음)

- **원인**: `init_chat_model`에 타임아웃을 지정하지 않으면 OpenAI 클라이언트 기본값 **600초**를 기다린다. 응답이 멈춘 요청 하나가 45개사 루프 전체를 10분씩 붙잡는다.
- **해결**: `llm.get_llm()`에 `timeout=60, max_retries=2` 설정. 정상 요청은 단계당 15~35초라 60초면 충분하다.
- **진단법**: `ps -o %cpu -p <pid>`가 0%이고 `lsof -a -p <pid> -i TCP`에 OpenAI(Cloudflare) 연결만 있으면 응답 대기 중이다.
