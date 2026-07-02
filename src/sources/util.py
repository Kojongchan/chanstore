"""소스 공통 파싱 유틸 (숫자화·태그제거). 소스 비종속."""
from __future__ import annotations

import re
from typing import Optional

_TAG_RE = re.compile(r"<[^>]+>")


def to_int(value) -> Optional[int]:
    """'12,900원' / '12900' → 12900. 실패 시 None."""
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def to_float(value) -> Optional[float]:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def strip_tags(text: str) -> str:
    """네이버 API 등이 상품명에 넣는 <b> 태그 제거 + 공백 정리."""
    if not text:
        return ""
    return _TAG_RE.sub("", text).replace("&amp;", "&").strip()
