"""D 레인 공통: 검색 질의, 구조화 분석, 근거 ID 연결. 재검색 분기는 graph가 담당한다."""

import json
import re
import hashlib
import os
import tempfile
import unicodedata
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool
from langchain.agents.structured_output import StructuredOutputValidationError
from pydantic import BaseModel, ConfigDict, Field, StrictBool

import llm
import schemas
from config import CACHE_DIR, TOP_K
from rag import retriever
from state import State, next_attempt
from tools import retrieval as retrieval_tools


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UnknownEvidenceError(ValueError):
    """모델이 이번 분석에 제공되지 않은 근거를 인용했다."""


class Maturity(schemas.Maturity, OutputModel):
    TRL: int | None = Field(ge=1, le=9, strict=True)
    근거ID: list[str] = Field(default_factory=list)


class Metric(schemas.Metric, OutputModel):
    값: str | None


class Comparison(schemas.Benchmark, OutputModel):
    업계기준: str | None


class TechnologyAnalysis(schemas.TechnologyAnalysis, OutputModel):
    제품성숙도: Maturity
    성능지표: list[Metric]
    기준대조: list[Comparison]
    근거충분: StrictBool


class MarketSize(schemas.Figure, OutputModel):
    값: str | None
    출처: str | None = None


class Growth(schemas.Growth, OutputModel):
    값: str | None
    기간: str | None


class MarketAnalysis(schemas.MarketAnalysis, OutputModel):
    시장규모: MarketSize
    성장률: Growth
    근거충분: StrictBool


class QuoteSupport(OutputModel):
    경로: str  # 예: 성능지표.0.값, 시장규모.기준연도
    근거ID: str
    원문구절: str  # 원문 그대로, 문맥·단위·표 헤더 포함


class ConditionPair(OutputModel):
    항목: str
    기업조건: str | None
    기준조건: str | None


class ComparisonAudit(OutputModel):
    지표명: str
    조건: list[ConditionPair]


class MarketAudit(OutputModel):
    항목: Literal["시장규모", "성장률"]
    범위: Literal["직접목표시장", "상위시장", "확인불가"]
    목표세그먼트: str
    자료세그먼트: str
    지역: str
    수치유형: Literal["실적", "전망", "확인불가"]
    성장유형: Literal["전년대비", "CAGR", "해당없음", "확인불가"]


class GroundedTechnology(OutputModel):
    분석: TechnologyAnalysis
    수치근거: list[QuoteSupport]
    기술비교: list[ComparisonAudit]


class GroundedMarket(OutputModel):
    분석: MarketAnalysis
    수치근거: list[QuoteSupport]
    시장검증: list[MarketAudit]


# CONTRACTS 3-9: A가 정한 sub_domain을 그대로 사용하며 임의 추론하지 않는다.
TECH_TERMS = {
    "ai_computing": "AI accelerator NPU TOPS/W INT8 throughput memory bandwidth IRDS",
    "packaging": "chiplet advanced packaging interconnect density thermal resistance IRDS",
    "power": "power semiconductor efficiency breakdown voltage on-resistance",
    "rf_sensor": "RF sensor frequency sensitivity noise connectivity IRDS",
    "memory": "PIM memory bandwidth latency energy per bit IRDS",
    "interface": "UCIe CXL interconnect GT/s bandwidth latency",
    "materials": "Beyond CMOS device materials switching energy IRDS",
    "metrology": "AI process metrology detection accuracy precision recall IRDS",
    "yield": "AI defect inspection yield enhancement detection accuracy IRDS",
}
_NUMBER = r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?"
_UNIT = r"TOPS/W|TOPS/mm2|TOPS|GT/s|GB/s|Gb/s|TB/s|Tb/s|GHz|MHz|kHz|Hz|nm|μm|µm|um|ms|ns|pJ/bit|kW|mW|W|kV|mV|V|%|percent|퍼센트|trillion|billion|million|천만|조|억|T|B"


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).replace("\u00ad", "").replace("−", "-").replace("–", "-").split())


def _numbers(text: str) -> set[Decimal]:
    return {Decimal(m.replace(",", "")) for m in re.findall(_NUMBER, _normalized(text))}


def _pairs(text: str) -> list[tuple[Decimal, str]]:
    aliases = {"percent": "%", "퍼센트": "%", "T": "trillion", "B": "billion", "um": "μm", "µm": "μm"}
    return [(Decimal(number.replace(",", "")), aliases.get(unit, unit))
            for number, unit in re.findall(rf"({_NUMBER})\s*({_UNIT})(?![A-Za-z])", _normalized(text))]


def _numeric_matches(value, quote: str) -> bool:
    text = str(value)
    # 임의의 단위 환산이나 계산값은 허용하지 않고 원문 표기를 우선한다.
    if not _numbers(text) or not _numbers(text) <= _numbers(quote):
        return False
    if any(pair not in _pairs(quote) for pair in _pairs(text)):
        return False
    def currencies(content):
        aliases = {"US$": "USD", "$": "USD", "€": "EUR", "₩": "KRW"}
        return {(aliases.get(currency, currency), Decimal(amount.replace(",", "")))
                for currency, amount in re.findall(rf"(USD|EUR|KRW|US\$|\$|€|₩)\s*({_NUMBER})", content)}
    if not currencies(text) <= currencies(quote):
        return False
    # 아직 지원하지 않는 단위는 숫자만으로 승인하지 않고 원문 표기를 요구한다.
    for number, unit in re.findall(rf"({_NUMBER})\s*([A-Za-zμµ][A-Za-zμµ0-9/²³^]*)", _normalized(text)):
        if not re.fullmatch(_UNIT, unit):
            if not re.search(rf"(?<![\d.]){re.escape(number)}\s*{re.escape(unit)}(?![A-Za-z0-9])", _normalized(quote)):
                return False
    return True


def _cache_path(evidence: dict) -> Path:
    identity = {k: evidence.get(k) for k in (
        "근거ID", "chunk_id", "출처명", "url", "source_page", "pub_year", "확인일",
    )}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return CACHE_DIR / "d_rag_text" / f"{digest}.txt"


def _cache_text(evidence: dict, content: str) -> None:
    path = _cache_path(evidence)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        f.write(content)
        temporary = f.name
    os.replace(temporary, path)


def evidence_text(evidence: dict) -> str:
    """공용 근거 구조는 유지하고, 확인된 전체 원문을 로컬 캐시에서 복원한다."""
    path = _cache_path(evidence)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return evidence.get("원문발췌", "")


def _published_after(evidence: dict, checked_at: str) -> bool:
    year = evidence.get("pub_year")
    if year is None:
        return False
    if isinstance(year, int) or re.fullmatch(r"\d{4}", str(year)):
        return int(year) > date.fromisoformat(checked_at).year
    return date.fromisoformat(str(year)) > date.fromisoformat(checked_at)


def build_query(state: State, stage: str) -> str:
    """고유 제품명·수치를 보존한 한영 질의. 재진입은 미확인 항목을 검색한다."""
    company = state["current_company"]
    keys = ("메인아이템", "기술분야", "혁신성") if stage == "technology" else (
        "메인아이템", "사업Point", "주요거래처",
    )
    subject = " ".join(str(company[k]) for k in keys if company.get(k))
    if stage == "technology":
        terms = TECH_TERMS.get(company.get("sub_domain"), "semiconductor technology performance IRDS")
        product = f"{company.get('메인아이템', '')} {company.get('기술분야', '')}"
        if re.search(r"(?<![A-Za-z])CXL(?![A-Za-z])", product, re.I):
            terms = "CXL data rate GT/s bandwidth GB/s x16 PAM4 Bundled Ports memory expansion cache coherent memory maintenance"
        elif re.search(r"(?<![A-Za-z])UCIe(?![A-Za-z])", product, re.I):
            terms = "UCIe data rate GT/s Advanced Package Standard Package NRZ pJ/bit shoreline bandwidth density"
        focus = f"핵심 성능지표 측정조건 검증수준 업계 로드맵 {terms}"
    else:
        tech = state.get("technology_analysis") or {}
        subject += " " + re.sub(r"\[[^\]]+\]", "", str(tech.get("핵심기술", "")))
        focus = "목표 시장 규모 성장률 수요 진입장벽 SIA WSTS KIET OECD semiconductor market size CAGR"
    previous = state.get(f"{stage}_analysis")
    if previous is not None:
        gaps = previous.get("미확인정보") or ["원문 수치 단위 기준연도 측정조건 출처"]
        # 최초 질의 전체를 반복하지 않고 미확인 항목과 제품명을 중심으로 재작성한다.
        return f"{company.get('메인아이템', '')} 추가 확인 {' '.join(gaps)} {focus}"
    return f"{subject.strip()} {focus}"


def collect_evidence(state: State, docs: list, stage: str) -> tuple[list[dict], list[dict]]:
    """B 도구와 같은 청크 ID를 사용. 누적 리듀서에는 신규 레코드만 반환한다."""
    prefix = "TEC-" if stage == "technology" else "MKT-"
    existing = [e for e in state.get("current_evidence", []) or []
                if str(e.get("근거ID", "")).startswith(prefix)]
    by_chunk = {e["chunk_id"]: e for e in existing if e.get("chunk_id")}
    checked_at = state["as_of_date"]
    date.fromisoformat(checked_at)
    additions, context = [], []
    seen = set()
    doc_type = "tech" if stage == "technology" else "market"
    for doc in docs:
        metadata = doc.metadata
        if metadata.get("doc_type") != doc_type:
            raise ValueError(f"D 검색 결과 doc_type 불일치: {doc_type}")
        domain = state["current_company"].get("sub_domain")
        if stage == "technology" and domain and metadata.get("sub_domain") != domain:
            raise ValueError("D 기술 검색 결과 sub_domain 불일치")
        if not metadata.get("chunk_id"):
            raise ValueError("D 검색 결과에 CONTRACTS 3-2 chunk_id가 필요합니다")
        if _published_after(metadata, checked_at):
            continue
        chunk_id = metadata["chunk_id"]
        if not doc.page_content.strip() or chunk_id in seen:
            continue
        seen.add(chunk_id)
        evidence = by_chunk.get(chunk_id)
        if evidence is None:
            evidence = retrieval_tools.to_evidence([doc], checked=checked_at)[0]
            additions.append(evidence)
            by_chunk[chunk_id] = evidence
        _cache_text(evidence, doc.page_content)
        # 분석에는 300자 발췌가 아닌 이번에 검색한 전체 청크를 전달한다.
        context.append({**evidence, "검색원문": doc.page_content})
    return additions, context


def generate_analysis(stage: str, payload: dict) -> dict:
    """공용 LLM 호출과 B 검색 도구 사용. 추가 검색은 호출당 한 번으로 제한한다."""
    schema = GroundedTechnology if stage == "technology" else GroundedMarket
    searched = False

    @tool("search_tech_docs" if stage == "technology" else "search_market_docs", response_format="content_and_artifact")
    def search(query: str) -> tuple[str, list]:
        """제공된 근거가 부족할 때 영문 기술·시장 용어를 포함해 추가 검색한다. 현재 기업 분야로 검색하며, 한 분석에서 한 번만 사용한다."""
        nonlocal searched
        if searched:
            return "추가 검색 완료. 미확인정보와 근거충분=false를 기록하면 graph가 다음 재검색을 판단한다.", []
        searched = True
        if stage == "technology":
            _, docs = retrieval_tools.search_tech_docs.func(query, sub_domain=payload["기업정보"].get("sub_domain"))
        else:
            _, docs = retrieval_tools.search_market_docs.func(query)
        docs = [d for d in docs if not _published_after(d.metadata, payload["조사기준일"])]
        text = "\n\n".join(f"[{retrieval_tools.evidence_id(d)}] {d.metadata.get('title', '')}\n{d.page_content}" for d in docs)
        return text or "조사기준일에 사용할 검색 근거 없음", docs

    result, docs = llm.run_agent(llm.load_prompt(stage), json.dumps(payload, ensure_ascii=False), schema, tools=[search])
    envelope = result.model_dump()
    out = {**envelope.pop("분석"), "_검증": envelope}
    if docs:
        out["_검색문서"] = docs
    return out


def _references(value) -> list[str]:
    if isinstance(value, dict):
        return [ref for key, item in value.items()
                for ref in (item if key == "근거ID" else _references(item))]
    if isinstance(value, list):
        return [ref for item in value for ref in _references(item)]
    if isinstance(value, str):
        return re.findall(r"\[((?:DIR|ELG|TEC|MKT|CMP)-[^\[\]\s]+)\]", value)
    return []


def _compare(metric: dict, reference: dict, audits: list[ComparisonAudit],
             company_quote: str, reference_quote: str) -> str:
    """단위·조건을 확인한 단일 수치만 비교한다. 환산·추정·범위값은 비교불가."""
    if metric["측정조건"] in ("", "확인 불가") or metric["검증수준"] in ("", "확인 불가"):
        return "비교불가"
    if any(re.search(r"\d\s*[-~]\s*\d", str(value)) for value in (metric["값"], reference["업계기준"])):
        return "비교불가"
    actual, baseline = _pairs(metric["값"]), _pairs(reference["업계기준"])
    if len(actual) != 1 or len(audits) != 1:
        return "비교불가"
    baseline = [pair for pair in baseline if pair[1] == actual[0][1]]
    if len(baseline) != 1:
        return "비교불가"
    unit = actual[0][1]
    if unit in ("TOPS/W", "TOPS", "TOPS/mm2"):
        required = {"정밀도", "공정", "워크로드", "측정방식"}
    elif unit == "GT/s":
        required = {"프로토콜", "신호방식"}
        if re.search(r"\bUCIe\b", company_quote + reference_quote, re.I):
            required.add("패키지")
    elif unit in ("GB/s", "Gb/s", "TB/s", "Tb/s"):
        required = {"프로토콜", "링크폭", "방향", "토폴로지"}
    elif unit == "%" and re.search(r"accuracy|precision|recall|정확도|정밀도|재현율", metric["지표명"], re.I):
        required = {"데이터셋", "정의", "임계값"}
    elif unit in ("ns", "ms"):
        required = {"워크로드", "측정방식"}
    elif unit == "pJ/bit":
        required = {"프로토콜", "신호방식"}
    else:
        return "비교불가"
    conditions = {pair.항목: pair for pair in audits[0].조건}
    if not required <= conditions.keys():
        return "비교불가"

    def condition_text(value: str) -> str:
        return re.sub(r"\s+", "", _normalized(value).casefold())

    for name, pair in conditions.items():
        if name not in required and (not pair.기업조건 or not pair.기준조건):
            continue  # 미기재된 부가 조건 때문에 확인된 핵심 조건까지 버리지 않는다.
        if not pair.기업조건 or not pair.기준조건:
            return "비교불가"
        a, b = condition_text(pair.기업조건), condition_text(pair.기준조건)
        if a in ("확인불가", "미상", "n/a") or a != b:
            return "비교불가"
        if a not in condition_text(company_quote) or b not in condition_text(reference_quote):
            return "비교불가"
        if a not in condition_text(metric["측정조건"]):
            return "비교불가"
    # 로드맵 전망이 제품 실측의 직접 기준이 되는 것을 방지한다.
    roadmap = r"scaling projection|roadmap|projected|로드맵|전망"
    if bool(re.search(roadmap, company_quote, re.I)) != bool(re.search(roadmap, reference_quote, re.I)):
        return "비교불가"
    if actual[0][0] == baseline[0][0]:
        return "동등"
    higher_is_better = unit not in ("ns", "ms", "pJ/bit")
    better = (actual[0][0] > baseline[0][0]) == higher_is_better
    return "상회" if better else "하회"


def _market_scope(audit: MarketAudit, company: dict, quote: str) -> bool:
    if audit.범위 != "직접목표시장" or audit.수치유형 == "확인불가" or not quote:
        return False
    target, source = _normalized(audit.목표세그먼트).casefold(), _normalized(audit.자료세그먼트).casefold()
    raw = _normalized(quote).casefold()
    if not target or target != source or source not in raw:
        return False
    company_text = " ".join(str(company.get(k, "")) for k in ("메인아이템", "기술분야", "사업Point")).casefold()
    marker = r"(?<![A-Za-z])(?:npu|gpu|cxl|ucie|pim|hbm)(?![A-Za-z])|엣지|\bedge\b|결함|\bdefect\b"
    specific = set(re.findall(marker, company_text, re.I))
    if specific:
        aliases = {"엣지": "edge", "결함": "defect"}
        words = {aliases.get(word, word) for word in specific}
        target_words = {aliases.get(word, word) for word in re.findall(marker, source, re.I)}
        if not words <= target_words:
            return False
        # 제품 키워드가 수요 설명에 등장해도 전체 시장 수치를 직접 시장으로 쓰지 않는다.
        if re.search(r"global semiconductor market|전체\s*반도체\s*시장|전체\s*반도체\s*산업", raw):
            return False
    elif target not in company_text:
        return False
    regions = {"글로벌": "global", "세계": "global", "한국": "korea", "국내": "국내"}
    region = _normalized(audit.지역).casefold()
    return bool(region) and (region in raw or regions.get(region, region) in raw)


def validate_analysis(stage: str, result: dict, evidence: list[dict], cid: str,
                      company: dict | None = None, as_of_date: str | None = None) -> dict:
    """구조와 인용을 검증. 필수 인용이 있을 때만 LLM의 충분 판정을 채택한다."""
    schema = TechnologyAnalysis if stage == "technology" else MarketAnalysis
    audit = result.get("_검증") or {}
    analysis = schema.model_validate({k: v for k, v in result.items() if k != "_검증"}).model_dump()
    sources = {e["근거ID"]: e for e in evidence
               if not as_of_date or not _published_after(e, as_of_date)}
    known = set(sources)
    refs = _references(analysis)
    unknown = set(refs) - known
    if unknown:
        raise UnknownEvidenceError(f"미등록 근거ID: {sorted(unknown)}")
    analysis["근거ID"] = list(dict.fromkeys(refs))
    gaps = analysis["미확인정보"]

    def need(ok: bool, message: str):
        if not ok:
            analysis["근거충분"] = False
            if message not in gaps:
                gaps.append(message)

    supports: dict[str, list[tuple[str, str]]] = {}
    for item in audit.get("수치근거", []):
        support = QuoteSupport.model_validate(item)
        if support.근거ID not in known:
            need(False, f"{support.경로} 인용 출처 확인 필요")
            continue
        quote = _normalized(support.원문구절)
        if quote and quote in _normalized(evidence_text(sources[support.근거ID])):
            supports.setdefault(support.경로, []).append((support.근거ID, quote))
        else:
            need(False, f"{support.경로} 인용 구절이 원문과 불일치")

    def numeric_supports(path: str, value, prefix: str, fallback: str | None = None) -> list[tuple[str, str]]:
        # ID 목록에 올바른 접두어가 있어도, 실제 수치가 나온 원문의 레인을 확인한다.
        candidates = supports.get(path, [])
        if fallback and not candidates:
            # 연도·기간이 수치의 인용 구절에 있으면 같은 원문의 중복 제출은 요구하지 않는다.
            candidates = supports.get(fallback, [])
        return [(ref, quote) for ref, quote in candidates
                if value is not None and ref.startswith(prefix) and _numeric_matches(value, quote)]

    def bind_supports(item: dict, matched: list[tuple[str, str]]):
        # 원문과 값이 확인될 때만 모델이 생략한 항목 내 근거 ID를 보완한다.
        item["근거ID"] = list(dict.fromkeys(item["근거ID"] + [ref for ref, _ in matched]))

    def quotes(matched: list[tuple[str, str]]) -> str:
        return " ".join(quote for _, quote in matched)

    lane = "TEC-" if stage == "technology" else "MKT-"
    company_lane = f"DIR-{cid}-"
    if stage == "technology":
        maturity = analysis["제품성숙도"]
        if maturity["TRL"] is not None:
            matched = [(ref, quote) for ref, quote in numeric_supports("제품성숙도.TRL", maturity["TRL"], company_lane)
                       if re.search(rf"\bTRL\s*[:=]?\s*{maturity['TRL']}\b", quote, re.I)]
            bind_supports(maturity, matched)
            if not matched:
                maturity["TRL"] = None
                need(False, "TRL의 명시적 기업 원문 구절 확인 필요")
        if not maturity["근거ID"]:
            # CONTRACTS 예시는 제품성숙도에 별도 ID가 없다. 상위 기업 인용을 상속한다.
            maturity["근거ID"] = [ref for ref in analysis["근거ID"] if ref.startswith(company_lane)]
        metric_supports = {}
        for i, metric in enumerate(analysis["성능지표"]):
            matched = numeric_supports(f"성능지표.{i}.값", metric["값"], company_lane)
            bind_supports(metric, matched)
            metric_supports[i] = matched
            if metric["값"] is not None and not matched:
                metric["값"] = None
                need(False, f"{metric['지표명']} 기업 수치·단위의 DIR 원문 구절 확인 필요")
        comparisons = [ComparisonAudit.model_validate(item) for item in audit.get("기술비교", [])]
        for i, comparison in enumerate(analysis["기준대조"]):
            path = f"기준대조.{i}.업계기준"
            matched = numeric_supports(path, comparison["업계기준"], lane)
            bind_supports(comparison, matched)
            if comparison["업계기준"] is not None and not matched:
                comparison["업계기준"] = None
                comparison["비교결과"] = "비교불가"
                need(False, f"{comparison['지표명']} 업계 수치·단위의 TEC 원문 구절 확인 필요")
            metrics = [m for m in analysis["성능지표"] if m["지표명"] == comparison["지표명"]]
            if not any(m["값"] is not None and m["측정조건"] not in ("", "확인 불가") for m in metrics):
                comparison["비교결과"] = "비교불가"
                need(False, f"{comparison['지표명']} 기업 수치와 측정조건 확인 필요")
            matching = [a for a in comparisons if a.지표명 == comparison["지표명"]]
            if len(metrics) == 1 and comparison["업계기준"] is not None and metrics[0]["값"] is not None:
                mi = analysis["성능지표"].index(metrics[0])
                verdict = _compare(metrics[0], comparison, matching,
                                   quotes(metric_supports[mi]), quotes(matched))
                comparison["비교결과"] = verdict
                need(verdict != "비교불가", f"{comparison['지표명']} 동일한 단위·측정조건·근거유형 확인 필요")
            else:
                comparison["비교결과"] = "비교불가"
        need(analysis["핵심기술"] not in ("", "확인 불가"), "기업 핵심기술 확인 필요")
        need(maturity["단계"] not in ("", "확인 불가") and bool(maturity["근거ID"]), "제품 개발 단계 근거 확인 필요")
        need(any(m["값"] is not None and m["근거ID"] and m["측정조건"] not in ("", "확인 불가")
                 and m["검증수준"] not in ("", "확인 불가") for m in analysis["성능지표"]),
             "기업 핵심 성능 수치 및 측정조건 확인 필요")
        need(any(c["업계기준"] is not None and c["비교결과"] != "비교불가"
                 for c in analysis["기준대조"]), "동일 조건의 업계 기준 대조 필요")
    else:
        market_audits = [MarketAudit.model_validate(item) for item in audit.get("시장검증", [])]
        market_supports = {}
        for key in ("시장규모", "성장률"):
            item = analysis[key]
            matched = numeric_supports(f"{key}.값", item["값"], lane)
            bind_supports(item, matched)
            market_supports[key] = matched
            raw = quotes(matched)
            if item["값"] is not None and not matched:
                item["값"] = None
                need(False, f"{key} 수치·단위의 MKT 원문 구절 확인 필요")
            matching = [a for a in market_audits if a.항목 == key]
            if item["값"] is not None and (len(matching) != 1 or not _market_scope(matching[0], company or {}, raw)):
                item["값"] = None
                need(False, f"{key}의 직접 목표 세그먼트·지역 확인 필요 (상위 시장은 배경 자료)")
            if item["값"] is not None and matching:
                is_forecast = bool(re.search(r"forecast|project|outlook|expected|전망|예측|예상|로드맵", raw, re.I))
                if is_forecast and (matching[0].수치유형 != "전망" or "전망" not in item["값"]):
                    item["값"] = None
                    need(False, f"{key} 전망 수치와 실적 구분 필요")
                if key == "성장률" and item["값"] is not None:
                    cagr = bool(re.search(r"CAGR|compound annual|연평균", raw, re.I))
                    claims_cagr = bool(re.search(r"CAGR|연평균", item["값"], re.I))
                    if claims_cagr != cagr or matching[0].성장유형 != ("CAGR" if cagr else "전년대비"):
                        item["값"] = None
                        need(False, "전년 대비 성장률과 CAGR 구분 필요")
            need(item["값"] is not None and bool(matched), f"{key}의 관련 시장 수치 및 RAG 근거 확인 필요")
        size, growth = analysis["시장규모"], analysis["성장률"]
        years = numeric_supports("시장규모.기준연도", size["기준연도"], lane, fallback="시장규모.값")
        bind_supports(size, years)
        if size["기준연도"] is not None and not (years and _numeric_matches(size["기준연도"], quotes(market_supports["시장규모"]))):
            size["기준연도"] = None
            size["값"] = None
            need(False, "시장규모 기준연도의 원문 구절 확인 필요")
        periods = numeric_supports("성장률.기간", growth["기간"], lane, fallback="성장률.값")
        bind_supports(growth, periods)
        if growth["기간"] is not None and not (periods and _numeric_matches(growth["기간"], quotes(market_supports["성장률"]))):
            growth["기간"] = None
            growth["값"] = None
            need(False, "성장률 기간의 원문 구절 확인 필요")
        # 출처명은 모델의 표현 대신 실제 시장규모 수치를 증명한 레코드에서 가져온다.
        titles = [sources[ref].get("출처명") for ref, _ in market_supports["시장규모"]]
        size["출처"] = " / ".join(dict.fromkeys(title for title in titles if title)) if size["값"] is not None else None
        size["출처"] = size["출처"] or None
        need(analysis["시장규모"]["기준연도"] is not None, "시장규모 기준연도 확인 필요")
        need(bool(analysis["성장률"]["기간"]), "성장률 산정 기간 확인 필요")
        need(bool(analysis["목표고객"]), "목표 고객 확인 필요")
        need(analysis["사업모델"] not in ("", "확인 불가"), "기업 사업모델 확인 필요")
        need(analysis["글로벌확장성"] not in ("", "확인 불가"), "글로벌 확장성 평가 근거 확인 필요")
    # 서술형 숫자에도 인용을 요구한다. 값과 다른 문장의 숫자를 묶어 인용하지 않는다.
    narrative = ("핵심기술", "강점", "한계") if stage == "technology" else (
        "목표고객", "사업모델", "글로벌확장성", "성장요인", "위험",
    )
    for key in narrative:
        is_list = isinstance(analysis[key], list)
        texts = analysis[key] if is_list else [analysis[key]]
        kept = []
        for text in texts:
            ids = _references(text)
            plain = re.sub(r"\[[^\]]+\]", "", text)
            if _numbers(plain) and not any(_numeric_matches(plain, evidence_text(sources[ref])) for ref in ids):
                need(False, f"{key} 서술형 수치의 원문 근거 확인 필요")
            else:
                kept.append(text)
        analysis[key] = kept if is_list else (kept[0] if kept else "확인 불가")
    analysis["근거ID"] = list(dict.fromkeys(_references(analysis)))
    need(any(ref.startswith(lane) for ref in analysis["근거ID"]), "관련 RAG 문서 근거 확보 필요")
    return analysis


def _empty_analysis(stage: str) -> dict:
    common = {"미확인정보": ["관련 RAG 문서 근거 확보 필요"], "근거ID": [], "근거충분": False}
    if stage == "technology":
        return {**common, "핵심기술": "확인 불가", "제품성숙도": {"TRL": None, "단계": "확인 불가", "근거ID": []},
                "성능지표": [], "기준대조": [], "강점": [], "한계": ["검색 근거 없음"]}
    return {**common, "목표고객": [], "시장규모": {"값": None, "출처": None, "기준연도": None, "근거ID": []},
            "성장률": {"값": None, "기간": None, "근거ID": []}, "사업모델": "확인 불가",
            "글로벌확장성": "확인 불가", "성장요인": [], "위험": ["검색 근거 없음"]}


def _directory_evidence(state: State) -> list[dict]:
    """A가 보존한 원문을 A의 근거 생성 함수로 연결한다. 기업 JSON을 원문으로 꾸미지 않는다."""
    company = state["current_company"]
    raw = company.get("원문")
    if not isinstance(raw, str) or not raw.strip():
        return []
    prefix = f"DIR-{company['company_id']}-"
    existing = [e for e in state.get("current_evidence", []) or []
                if e.get("근거ID", "").startswith(prefix)]
    for evidence in existing:
        if evidence.get("source_page") == company.get("source_page") and evidence.get("원문발췌", "") in raw:
            _cache_text(evidence, raw)
            return []
    from rag.parser import directory_evidence

    serials = [int(e["근거ID"][len(prefix):]) for e in existing]
    evidence = directory_evidence(company, max(serials, default=0) + 1, raw, state["as_of_date"])
    if _published_after(evidence, state["as_of_date"]):
        return []
    _cache_text(evidence, raw)
    return [evidence]


def _team_output(stage: str, analysis: dict) -> dict:
    """내부의 null은 공용 스키마의 '확인 불가'로 내보낸다. 수치·연도는 추정하지 않는다."""
    data = json.loads(json.dumps(analysis, ensure_ascii=False))
    if stage == "technology":
        for item in data["성능지표"]:
            item["값"] = item["값"] if item["값"] is not None else "확인 불가"
        for item in data["기준대조"]:
            item["업계기준"] = item["업계기준"] if item["업계기준"] is not None else "확인 불가"
        schema = schemas.TechnologyAnalysis
    else:
        for key, field in (("시장규모", "값"), ("성장률", "값"), ("성장률", "기간")):
            data[key][field] = data[key][field] if data[key][field] is not None else "확인 불가"
        schema = schemas.MarketAnalysis
    schema.model_validate(data)
    return data


def run_analysis(state: State, stage: Literal["technology", "market"]) -> dict:
    company = state.get("current_company")
    if not company or not company.get("company_id"):
        raise ValueError("D 분석에는 company_id가 있는 current_company가 필요합니다")
    domain = company.get("sub_domain") if stage == "technology" else None
    if domain is not None and domain not in TECH_TERMS:
        raise ValueError(f"CONTRACTS 3-9에 없는 sub_domain: {domain}")
    output_key = f"{stage}_analysis"
    query = build_query(state, stage)
    docs = retriever.hybrid_search(query, doc_type="tech" if stage == "technology" else "market",
                                   sub_domain=domain, k=TOP_K)
    directory = _directory_evidence(state)
    additions, retrieved = collect_evidence(state, docs, stage)
    additions = directory + additions
    cid = company["company_id"]
    # 이번 기업의 근거만 전달한다. 재검색에는 이전 라운드의 원문 발췌도 보존한다.
    prefixes = (f"DIR-{cid}-", "TEC-", "MKT-")
    existing = [e for e in state.get("current_evidence", []) or []
                if str(e.get("근거ID", "")).startswith(prefixes)
                and not _published_after(e, state["as_of_date"])]
    available = existing + additions
    lane_prefix = "TEC-" if stage == "technology" else "MKT-"
    if any(e["근거ID"].startswith(lane_prefix) for e in available):
        payload = {
            "조사기준일": state["as_of_date"], "기업정보": company, "검색질의": query,
            "이전분석": state.get(output_key),
            "기술분석": state.get("technology_analysis") if stage == "market" else None,
            "기존근거": [{**e, "검색원문": evidence_text(e)} for e in existing + directory], "검색근거": retrieved,
        }
        try:
            result = generate_analysis(stage, payload)
        except StructuredOutputValidationError:
            result = _empty_analysis(stage)
            result["미확인정보"].append("구조화 출력 검증 재시도 후 실패: 모델 분석 폐기, 원문 추가 확인 필요")
        extra_docs = result.pop("_검색문서", [])
        if extra_docs:
            extra, _ = collect_evidence({**state, "current_evidence": available}, extra_docs, stage)
            additions += extra
            available += extra
    else:
        result = _empty_analysis(stage)
    try:
        analysis = validate_analysis(stage, result, available, cid, company, state["as_of_date"])
    except UnknownEvidenceError as exc:
        analysis = _empty_analysis(stage)
        analysis["미확인정보"].append(f"{exc}; 해당 모델 분석을 폐기함")
    return {output_key: _team_output(stage, analysis), "current_evidence": additions,
            "retrieve_count": next_attempt(state, output_key)}
