"""LLM 공통 호출 (🔒 보호 파일). 교재 langgraph-v1/10-Agent 패턴: init_chat_model + create_agent + ToolStrategy.

    from llm import load_prompt, run_agent
    from schemas import TechnologyAnalysis
    from tools.retrieval import search_tech_docs, to_evidence

    result, artifacts = run_agent(load_prompt("technology"), user_msg, TechnologyAnalysis, [search_tech_docs])
    analysis = result.model_dump()          # CONTRACTS 형식 dict
    evidence = to_evidence(artifacts)       # 근거 레코드
"""

from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import init_chat_model
from pydantic import BaseModel

from config import LLM_MODEL, ROOT


@lru_cache(maxsize=1)
def get_llm():
    return init_chat_model(LLM_MODEL, model_provider="openai", temperature=0)


def load_prompt(name: str) -> str:
    """prompts/<name>.md 내용."""
    return (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def run_agent(system_prompt: str, user: str, schema: type[BaseModel], tools=()) -> tuple[BaseModel, list]:
    """도구를 스스로 골라 쓰는 에이전트 실행 → (schema 인스턴스, 도구가 돌려준 artifact 목록).

    tools가 비어 있으면 도구 없이 구조화 출력만 한다 (예: 투자 판단 채점).
    artifact는 content_and_artifact 도구(tools/retrieval.py)가 반환한 검색 청크(Document)다.
    """
    agent = create_agent(get_llm(), tools=list(tools), response_format=ToolStrategy(schema), system_prompt=system_prompt)
    out = agent.invoke({"messages": [{"role": "user", "content": user}]})
    artifacts = []
    for m in out["messages"]:
        a = getattr(m, "artifact", None)
        if a:
            artifacts.extend(a if isinstance(a, list) else [a])
    return out["structured_response"], artifacts
