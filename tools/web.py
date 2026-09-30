"""웹검색 도구 (C 레인 초안). 적격성 G2·G3(투자·M&A 뉴스), 경쟁 제품 스펙 확인용. 교재 10-React-Agent 패턴."""

from functools import lru_cache

from langchain_tavily import TavilySearch


@lru_cache(maxsize=1)
def web_search() -> TavilySearch:
    """Tavily 검색 도구. TAVILY_API_KEY가 필요해 import 시점이 아니라 처음 쓸 때 만든다."""
    t = TavilySearch(max_results=5, topic="general")
    t.name = "web_search"
    t.description = (
        "최신 웹 정보를 검색한다. 투자 유치 라운드·인수합병 여부는 topic='news'로, "
        "경쟁 제품의 공개 스펙은 topic='general'로 검색한다. 결과의 url을 근거로 남긴다."
    )
    return t
