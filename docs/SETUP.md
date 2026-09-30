# 초기 환경 세팅

패키지 관리는 **uv** 하나로 통일한다. `pip install`·`uv init`은 사용하지 않는다.

## 1. 처음 한 번

```bash
# uv 설치 (없으면)
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS / Linux
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

git clone https://github.com/kimhynsoo/skala-rag.git
cd skala-rag
uv sync                  # Python 3.11 자동 설치 + .venv 생성 + uv.lock 그대로 설치
cp .env.example .env     # API 키 입력 (OPENAI, TAVILY, DART)
uv run pytest -q         # 전부 통과하면 세팅 완료
```

- Python 버전은 `pyproject.toml`의 `requires-python = "==3.11.*"`로 고정되어 있다. 로컬에 3.11이 없어도 uv가 내려받는다.
- 임베딩 비교 실험(P6)을 맡은 사람만 추가로 `uv sync --group eval`.
- VS Code / Jupyter 인터프리터는 `skala-rag/.venv/bin/python` 선택.

## 2. 실행

```bash
uv run python app.py                     # 전체 파이프라인 → outputs/report.md
uv run python app.py --as-of 2026-09-30  # 조사 기준일 지정
uv run python app.py --graph             # 그래프 mermaid 출력
```

가상환경 활성화(`source .venv/bin/activate`) 없이 `uv run`을 앞에 붙이면 된다.

## 3. 두 파일의 역할

| 파일 | 역할 | 누가 수정 |
|---|---|---|
| `pyproject.toml` | 직접 쓰는 패키지와 허용 범위, Python 버전 (의도) | 사람 (`uv add`가 대신 써줌) |
| `uv.lock` | 하위 의존성까지 정확한 버전·해시 고정 (결과) | uv만. 손으로 수정 금지 |

둘 다 커밋한다. 없으면 팀원·평가자마다 다른 버전이 설치되어 "내 컴퓨터에선 되는데"가 생긴다.

## 4. 개발 중 규칙

| 상황 | 할 일 |
|---|---|
| 패키지 추가 | `uv add <pkg>` → `pyproject.toml`·`uv.lock` **같은 커밋**에 포함 |
| 패키지 제거 | `uv remove <pkg>` → 동일 |
| pull 후 두 파일이 바뀌었음 | `uv sync` |
| PR에서 `uv.lock` 충돌 | 손으로 고치지 말고 `git checkout --theirs uv.lock && uv lock` 후 커밋 |
| 커밋 전 | `uv run pytest -q` 통과 확인 |

## 5. 커밋하지 않는 것

`.env`(API 키), `.venv/`, `.cache/`(임베딩·FAISS 캐시, 재생성 가능), `.python-version` — `.gitignore`에 등록되어 있다.
