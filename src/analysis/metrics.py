"""분석 지표 계산 — 순수 함수(네트워크·상태 없음). 입력은 list[Product].

핵심 원칙(PLATFORM_PLAN.md §1-1):
- 크롤링/수집으로 얻는 건 '판매가'. '원가(sourcing_cost)'는 소싱처에서 넣는 별도 값이다.
- 따라서 마진 계산은 sourcing_cost 가 주어졌을 때만 가능하다. 없으면 마진 항목은 None.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..schema import Product

# 마켓별 대략적인 판매수수료율(카테고리마다 다르므로 기본 추정치; 필요 시 조정).
MARKET_FEE_RATES: dict[str, float] = {
    "11st": 0.13,
    "naver": 0.06,     # 스마트스토어(네이버쇼핑 결제수수료 포함 대략)
    "gmarket": 0.12,
    "auction": 0.12,
    "_default": 0.12,
}
VAT_RATE = 0.10


def _prices(products: Sequence[Product]) -> list[int]:
    return [p.price for p in products if isinstance(p.price, int) and p.price > 0]


def price_stats(products: Sequence[Product]) -> dict:
    """가격 기초 통계. 유효 가격이 없으면 count=0."""
    prices = _prices(products)
    if not prices:
        return {"count": 0, "min": None, "max": None, "mean": None,
                "median": None, "stdev": None}
    return {
        "count": len(prices),
        "min": min(prices),
        "max": max(prices),
        "mean": round(statistics.mean(prices)),
        "median": round(statistics.median(prices)),
        "stdev": round(statistics.pstdev(prices)) if len(prices) > 1 else 0,
    }


def price_distribution(products: Sequence[Product], bins: int = 5) -> list[dict]:
    """가격 히스토그램. [{'low','high','count'} ...] (min==max면 단일 구간)."""
    prices = _prices(products)
    if not prices:
        return []
    lo, hi = min(prices), max(prices)
    if lo == hi or bins < 1:
        return [{"low": lo, "high": hi, "count": len(prices)}]
    width = (hi - lo) / bins
    buckets = [{"low": round(lo + i * width), "high": round(lo + (i + 1) * width),
                "count": 0} for i in range(bins)]
    for pr in prices:
        idx = min(int((pr - lo) / width), bins - 1)
        buckets[idx]["count"] += 1
    return buckets


def estimate_margin(
    sale_price: int,
    sourcing_cost: int,
    *,
    market: str = "_default",
    shipping_fee: int = 0,
    fee_rate: Optional[float] = None,
    vat_rate: float = VAT_RATE,
) -> dict:
    """단일 상품 마진 역산.

    마진 = 판매가 - 마켓수수료(판매가×수수료율) - 부가세(마진분) - 원가 - 배송비.
    간이 모델: 부가세는 (판매가-원가)의 vat_rate 로 근사.
    반환: {revenue, fee, vat, cost, shipping, margin, margin_rate}
    """
    rate = fee_rate if fee_rate is not None else MARKET_FEE_RATES.get(market, MARKET_FEE_RATES["_default"])
    fee = round(sale_price * rate)
    vat = round(max(0, sale_price - sourcing_cost) * vat_rate)
    margin = sale_price - fee - vat - sourcing_cost - shipping_fee
    margin_rate = round(margin / sale_price, 4) if sale_price else None
    return {
        "revenue": sale_price,
        "fee": fee,
        "vat": vat,
        "cost": sourcing_cost,
        "shipping": shipping_fee,
        "margin": margin,
        "margin_rate": margin_rate,
    }


def detect_hot_deals(products: Sequence[Product], *, threshold: float = 0.7) -> list[Product]:
    """중앙값 대비 price <= median*threshold 인 저가 상품(핫딜 후보).

    threshold=0.7 → 중앙값의 70% 이하 가격. 유효 가격 2개 미만이면 빈 리스트.
    결과는 가격 오름차순.
    """
    prices = _prices(products)
    if len(prices) < 2:
        return []
    median = statistics.median(prices)
    cutoff = median * threshold
    deals = [p for p in products
             if isinstance(p.price, int) and 0 < p.price <= cutoff]
    return sorted(deals, key=lambda p: p.price)


def competition_strength(products: Sequence[Product]) -> dict:
    """경쟁강도 지표.

    - listings: 유효 상품 수
    - sellers: 고유 판매자 수
    - seller_concentration: 최다 판매자의 점유율(0~1) — 높을수록 특정 셀러 독점
    - total_reviews: 리뷰수 합계(제공 소스 한정)
    - level: low/medium/high (상품 수 기준 러프 등급)
    """
    valid = [p for p in products if isinstance(p.price, int) and p.price > 0]
    n = len(valid)
    sellers = [p.seller for p in valid if p.seller]
    unique_sellers = set(sellers)
    concentration = 0.0
    if sellers:
        top = max(sellers.count(s) for s in unique_sellers)
        concentration = round(top / len(sellers), 3)
    total_reviews = sum(p.review_count for p in valid if isinstance(p.review_count, int))

    if n <= 10:
        level = "low"
    elif n <= 40:
        level = "medium"
    else:
        level = "high"

    return {
        "listings": n,
        "sellers": len(unique_sellers),
        "seller_concentration": concentration,
        "total_reviews": total_reviews,
        "level": level,
    }


@dataclass
class KeywordReport:
    keyword: str
    stats: dict
    distribution: list = field(default_factory=list)
    competition: dict = field(default_factory=dict)
    hot_deals: list = field(default_factory=list)
    margin: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "stats": self.stats,
            "distribution": self.distribution,
            "competition": self.competition,
            "hot_deals": [
                {"name": p.name, "price": p.price, "seller": p.seller,
                 "source": p.source, "url": p.product_url}
                for p in self.hot_deals
            ],
            "margin": self.margin,
        }


def analyze_keyword(
    products: Sequence[Product],
    *,
    keyword: str = "",
    sourcing_cost: Optional[int] = None,
    target_price: Optional[int] = None,
    market: str = "_default",
    shipping_fee: int = 0,
    hot_deal_threshold: float = 0.7,
) -> KeywordReport:
    """키워드 단위 종합 분석 리포트.

    sourcing_cost 가 주어지면 target_price(없으면 중앙값)를 판매가로 가정해 마진을 역산한다.
    이 원가는 크롤링 값이 아니라 사용자가 소싱처 기준으로 넣는 값이다.
    """
    stats = price_stats(products)
    report = KeywordReport(
        keyword=keyword,
        stats=stats,
        distribution=price_distribution(products),
        competition=competition_strength(products),
        hot_deals=detect_hot_deals(products, threshold=hot_deal_threshold),
    )
    if sourcing_cost is not None and stats["count"] > 0:
        price = target_price if target_price is not None else stats["median"]
        report.margin = estimate_margin(
            price, sourcing_cost, market=market, shipping_fee=shipping_fee
        )
    return report
