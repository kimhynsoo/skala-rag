import hashlib
import json
from collections.abc import Mapping
from datetime import date

from pydantic import JsonValue


def company_hash(company: Mapping[str, JsonValue]) -> str:
    fields = ("company_id", "기업명", "홈페이지", "메인아이템", "업종", "기술분야", "사업Point", "혁신성", "투자유치이력")
    payload = json.dumps({key: company.get(key) for key in fields}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def cache_is_current(completed_at: str, as_of_date: str) -> bool:
    try:
        age = (date.fromisoformat(as_of_date) - date.fromisoformat(completed_at[:10])).days
    except ValueError:
        return False
    return 0 <= age <= 14
