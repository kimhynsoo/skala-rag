"""RAG 검색 도구 (B 레인). 기술 요약·시장성·경쟁사 에이전트가 LLM에 붙여 쓴다.

- content: LLM이 읽는 텍스트. 각 청크 앞에 근거ID([TEC-08-0001])를 붙여 그대로 인용하게 한다.
- artifact: 검색된 Document 목록. llm.run_agent()가 회수하고 to_evidence()로 근거 레코드를 만든다.
근거ID = {TEC|MKT}-{chunk_id} → 같은 청크는 몇 번 검색돼도 같은 ID (재매핑 불필요).
"""

from datetime import date

from langchain_core.documents import Document
from langchain_core.tools import tool

from rag.retriever import hybrid_search
from schemas import TechDomain

PREFIX = {"tech": "TEC", "market": "MKT"}


def evidence_id(doc: Document) -> str:
    return f"{PREFIX[doc.metadata['doc_type']]}-{doc.metadata['chunk_id']}"


def _format(docs: list[Document]) -> str:
    if not docs:
        return "검색 결과 없음. 다른 키워드(영문 포함)로 다시 검색하거나 '확인 불가'로 처리한다."
    blocks = []
    for d in docs:
        m = d.metadata
        blocks.append(f"[{evidence_id(d)}] {m.get('title', '')} ({m.get('publisher', '')}, {m.get('pub_year', '')}), "
                      f"p.{m.get('source_page', '?')}\n{d.page_content}")
    return "\n\n".join(blocks)


@tool(response_format="content_and_artifact")
def search_tech_docs(query: str, sub_domain: TechDomain | None = None) -> tuple[str, list[Document]]:
    """반도체 기술 로드맵·표준 문서(IEEE IRDS, UCIe, CXL, Power Electronics Roadmap, 영문)를 검색한다.
    기업이 주장하는 성능 지표를 업계 기준값과 대조할 때 사용한다.
    문서가 영문이므로 query에 영문 기술 용어를 함께 쓰면 정확도가 높다 (예: "칩렛 대역폭 UCIe chiplet bandwidth").
    sub_domain(선택): ai_computing=NPU·AI 가속기·로직 스케일링, packaging=칩렛·첨단 패키징, power=전력반도체,
    rf_sensor=RF·센서·통신, memory=메모리 소자(DRAM·NAND·신메모리), interface=칩 간·메모리 확장 인터페이스(UCIe·CXL·PCIe),
    materials=신소자·소재, metrology=계측·공정 모니터링, yield=수율·결함 검사.
    분야가 애매하거나 결과가 부족하면 sub_domain 없이 다시 검색한다. 결과의 [TEC-...] ID를 근거ID로 그대로 인용한다."""
    docs = hybrid_search(query, doc_type="tech", sub_domain=sub_domain)
    return _format(docs), docs


@tool(response_format="content_and_artifact")
def search_market_docs(query: str) -> tuple[str, list[Document]]:
    """반도체 시장·산업 보고서(SIA, WSTS, KIET 한국 반도체 전망, OECD 가치사슬)를 검색한다.
    시장 규모, 성장률, 수요처, 산업 구조·진입장벽을 확인할 때 사용한다.
    한국어 문서는 KIET 하나뿐이므로 영문 키워드를 함께 써야 글로벌 자료가 검색된다 (예: "AI 반도체 시장 규모 AI semiconductor market size").
    결과의 [MKT-...] ID를 근거ID로 그대로 인용한다."""
    docs = hybrid_search(query, doc_type="market")
    return _format(docs), docs


def to_evidence(docs: list[Document], checked: str | None = None) -> list[dict]:
    """검색 청크 → 근거 레코드 (CONTRACTS 3-4). 같은 근거ID는 한 번만."""
    checked = checked or date.today().isoformat()
    records: dict[str, dict] = {}
    for d in docs:
        m = d.metadata
        records.setdefault(evidence_id(d), {
            "근거ID": evidence_id(d),
            "출처명": m.get("title"),
            "publisher": m.get("publisher"),
            "pub_year": m.get("pub_year"),
            "source_type": m.get("source_type"),
            "url": m.get("url"),
            "source_page": m.get("source_page"),
            "확인일": checked,
            "원문발췌": d.page_content[:300],
            "chunk_id": m.get("chunk_id"),
        })
    return list(records.values())
