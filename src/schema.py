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
    price: Optional[int] = None     # 대표 판매가(원). 숫자화 실패 시 None
    image_url: str = ""             # 이미지 URL(원본)
    # 내려받아 저장한 메인 썸네일의 로컬 경로. **분석 참고용** 저장소(ref_images/)에만 둔다.
    # 판매용 재가공/재사용은 별개 판단(PLATFORM_PLAN.md §5) — 판매 자산은 AI 신규 생성/소싱처 제공분.
    image_path: str = ""
    product_url: str = ""           # 상품 상세 URL
    seller: str = ""                # 판매자/스토어명
    review_count: Optional[int] = None
    rating: Optional[float] = None  # 평점
    category: str = ""              # 카테고리(제공 시)

    # --- 가격 세부 (경쟁 가격 인텔리전스) ---
    list_price: Optional[int] = None    # 정상가
    sale_price: Optional[int] = None    # 할인가
    coupon_price: Optional[int] = None  # 쿠폰 적용가(제공 시)
    shipping_fee: Optional[int] = None  # 배송비(원). 무료면 0

    # --- 마진 판단용 (크롤링 값 아님. 소싱처 입력/분석 계산) ---
    # PLATFORM_PLAN.md 1-1: '원가'는 오픈마켓에 공개되지 않는다.
    # sourcing_cost 는 소싱처(도매매·온채널 등)에서 채우는 별도 입력값이며,
    # estimated_margin 은 분석 레이어가 계산한다. 수집 소스는 이 두 필드를 건드리지 않는다.
    sourcing_cost: Optional[int] = None      # 매입원가(수동/소싱처 연동)
    estimated_margin: Optional[int] = None   # 추정 마진(분석 레이어 계산값)

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
    "list_price",
    "sale_price",
    "coupon_price",
    "shipping_fee",
    "sourcing_cost",
    "estimated_margin",
    "image_url",
    "image_path",
    "product_url",
    "seller",
    "review_count",
    "rating",
    "category",
    "rank",
    "delivery",
    "collected_at",
]
