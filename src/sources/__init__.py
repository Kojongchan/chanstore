"""데이터 소스 모듈. 소스별로 독립 — 하나가 깨져도 나머지는 동작한다 (PROJECT.md 2-3).

레지스트리(build_source)로 소스 코드 문자열 → BaseSource 인스턴스를 만든다.
API 키가 필요한 소스는 키가 없으면 SourceError 를 던져, CLI가 해당 소스만 건너뛰게 한다.
"""
from __future__ import annotations

from .base import BaseSource, SourceError
from .elevenst import ElevenStSource
from .naver import NaverSource
from .gmarket import GmarketSource
from .auction import AuctionSource

__all__ = [
    "BaseSource",
    "SourceError",
    "ElevenStSource",
    "NaverSource",
    "GmarketSource",
    "AuctionSource",
    "SOURCE_CODES",
    "build_source",
]

# 우선순위 순서(PLATFORM_PLAN.md §2): API 먼저, 크롤링은 뒤.
SOURCE_CODES: list[str] = ["11st", "naver", "gmarket", "auction"]


def build_source(code: str, **kwargs) -> BaseSource:
    """소스 코드로 인스턴스 생성. 키가 필요한데 없으면 SourceError."""
    code = code.lower().strip()
    if code == "11st":
        from ..config import get_elevenst_api_key
        key = get_elevenst_api_key()
        if not key:
            raise SourceError("11번가 API 키 미설정(ELEVENST_API_KEY)")
        return ElevenStSource(key, **_filter(kwargs, ("page_size", "delay")))
    if code == "naver":
        from ..config import get_naver_credentials
        creds = get_naver_credentials()
        if not creds:
            raise SourceError("네이버 API 자격정보 미설정(NAVER_CLIENT_ID/SECRET)")
        cid, secret = creds
        return NaverSource(cid, secret, **_filter(kwargs, ("page_size", "delay")))
    if code == "gmarket":
        return GmarketSource()
    if code == "auction":
        return AuctionSource()
    raise SourceError(f"알 수 없는 소스 코드: {code}")


def _filter(kwargs: dict, allowed: tuple[str, ...]) -> dict:
    return {k: v for k, v in kwargs.items() if k in allowed}
