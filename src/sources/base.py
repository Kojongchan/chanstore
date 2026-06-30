"""소스 공통 인터페이스.

2단계 네이버, 5단계 크롤러는 이 `BaseSource` 를 상속해 `search()` 만 구현하면
main 파이프라인(정규화→저장)에 그대로 끼워진다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from ..schema import Product


class SourceError(Exception):
    """소스 수집 중 발생한 복구 불가 에러 (키 누락, 인증 실패 등)."""


class BaseSource(ABC):
    #: 소스 식별 코드. Product.source 에 기록된다.
    name: str = "base"

    @abstractmethod
    def search(self, keyword: str, *, pages: int) -> Iterator[Product]:
        """키워드로 상품을 검색해 정규화된 `Product` 를 순서대로 yield."""
        raise NotImplementedError
