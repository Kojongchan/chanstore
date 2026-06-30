"""공통 데이터 스키마.

모든 소스(11번가·네이버·크롤러)는 자신의 응답을 이 `Product` 형태로 정규화한다.
2단계(네이버), 5단계(크롤러)에서 그대로 재사용하기 위해 소스 비종속적으로 정의한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(slots=True)
class Product:
    """정규화된 단일 상품 레코드 (사실 데이터만 보관)."""

    # --- 출처 식별 ---
    source: str                     # 소스 코드: "11st", "naver", ...
    product_code: str               # 소스 내 상품 고유 ID
    keyword: str                    # 어떤 검색어로 수집됐는지

    # --- 핵심 사실 데이터 ---
    name: str = ""                  # 상품명
    price: Optional[int] = None     # 판매가(원). 숫자화 실패 시 None
    image_url: str = ""             # 이미지 URL (참고용 표시까지만. 재사용 금지 — PROJECT.md 2-1)
    product_url: str = ""           # 상품 상세 URL
    seller: str = ""                # 판매자/스토어명
    review_count: Optional[int] = None
    rating: Optional[float] = None  # 평점
    category: str = ""              # 카테고리(제공 시)

    # --- 순위/메타 ---
    rank: Optional[int] = None      # 수집 시점의 노출 순번
    delivery: str = ""              # 배송 정보(제공 시)
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extra: dict[str, Any] = field(default_factory=dict)  # 소스별 부가 필드

    @property
    def dedup_key(self) -> str:
        """중복 판정 키. (소스, 상품코드) 조합으로 유일."""
        return f"{self.source}:{self.product_code}"

    def to_row(self) -> dict[str, Any]:
        """엑셀/DB 저장용 평탄화 dict. `extra`는 제외(컬럼 외 부가정보)."""
        row = asdict(self)
        row.pop("extra", None)
        return row


# 엑셀 헤더 / DB 컬럼 순서의 단일 출처
COLUMNS: list[str] = [
    "source",
    "product_code",
    "keyword",
    "name",
    "price",
    "image_url",
    "product_url",
    "seller",
    "review_count",
    "rating",
    "category",
    "rank",
    "delivery",
    "collected_at",
]
