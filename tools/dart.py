"""DART 상장 여부 조회 도구 (C 레인 초안). 적격성 G1(비상장) 판정용.

OpenDART 공시대상 회사 목록(corpCode.xml, 약 10만 건)을 한 번 내려받아 .cache/dart/에 두고,
기업명으로 찾아 종목코드(stock_code) 유무로 상장 여부를 판단한다. DART_API_KEY 필요.
"""

import io
import os
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

from config import CACHE_DIR

CORP_XML = CACHE_DIR / "dart" / "CORPCODE.xml"
URL = "https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}"


def _norm(name: str) -> str:
    return name.replace("(주)", "").replace("주식회사", "").replace(" ", "").strip()


def _download() -> Path:
    if not CORP_XML.exists():
        data = urllib.request.urlopen(URL.format(key=os.environ["DART_API_KEY"]), timeout=60).read()
        CORP_XML.parent.mkdir(parents=True, exist_ok=True)
        CORP_XML.write_bytes(zipfile.ZipFile(io.BytesIO(data)).read("CORPCODE.xml"))
    return CORP_XML


@lru_cache(maxsize=2)
def _corp_index(xml_path: Path) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for el in ET.parse(xml_path).getroot().iter("list"):
        name = el.findtext("corp_name") or ""
        index.setdefault(_norm(name), []).append({
            "corp_code": el.findtext("corp_code"),
            "corp_name": name,
            "stock_code": (el.findtext("stock_code") or "").strip(),
        })
    return index


def find_corps(name: str, xml_path: Path | None = None) -> list[dict]:
    """기업명(법인 표기·공백 무시)과 정확히 일치하는 DART 등록 회사."""
    return _corp_index(xml_path or _download()).get(_norm(name), [])


@tool
def dart_listing_status(company_name: str) -> str:
    """DART 공시대상 회사 목록에서 기업명을 찾아 상장 여부(종목코드 유무)를 확인한다. G1(비상장) 판정에 사용한다."""
    hits = find_corps(company_name)
    if not hits:
        return f"'{company_name}': DART 공시대상 목록에 정확한 법인 일치 없음 → 상장 여부 확인불가"
    return "\n".join(
        f"{h['corp_name']} (corp_code {h['corp_code']}): "
        + (f"종목코드 {h['stock_code']} → 상장사" if h["stock_code"] else "종목코드 없음 → 비상장")
        for h in hits
    )
