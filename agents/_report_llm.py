"""E 레인 공용 LLM 호출 — 구조화 출력 한 곳으로 모아 테스트에서 교체할 수 있게 한다."""

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from config import LLM_MODEL, ROOT

T = TypeVar("T", bound=BaseModel)


def load_prompt(name: str) -> str:
    return (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def structured_call(schema: type[T], system: str, user: str) -> T:
    """temperature 0 구조화 출력. 테스트는 이 함수를 monkeypatch한다."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=LLM_MODEL, temperature=0).with_structured_output(schema)
    return llm.invoke([("system", system), ("user", user)])
