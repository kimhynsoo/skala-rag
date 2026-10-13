"""외부 LLM 호출을 막는다. 새 노드의 LLM 진입점은 여기서 기본값으로 대체하고, 필요한 테스트만 다시 monkeypatch한다."""

import pytest


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch, tmp_path):
    import obs
    from agents import supervisor

    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(supervisor, "_ask_llm", lambda state, candidates: None)  # → 규칙 정책
