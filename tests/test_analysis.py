"""분석 레이어 테스트 (순수 함수, 네트워크 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.schema import Product  # noqa: E402
from src.analysis import (  # noqa: E402
    price_stats, price_distribution, estimate_margin,
    detect_hot_deals, competition_strength, analyze_keyword,
)


def _p(price, seller="s", review=None, source="11st"):
    return Product(source=source, product_code=str(price) + seller,
                   keyword="k", name=f"상품{price}", price=price,
                   seller=seller, review_count=review)


def test_price_stats():
    st = price_stats([_p(1000), _p(2000), _p(3000)])
    assert st == {"count": 3, "min": 1000, "max": 3000,
                  "mean": 2000, "median": 2000, "stdev": st["stdev"]}
    assert price_stats([])["count"] == 0


def test_price_distribution_buckets():
    dist = price_distribution([_p(100), _p(200), _p(300), _p(400), _p(500)], bins=5)
    assert sum(b["count"] for b in dist) == 5
    # min==max → 단일 구간
    assert price_distribution([_p(100), _p(100)]) == [{"low": 100, "high": 100, "count": 2}]


def test_estimate_margin():
    m = estimate_margin(10000, 5000, market="11st", shipping_fee=0)
    assert m["fee"] == 1300           # 10000 * 0.13
    assert m["vat"] == 500            # (10000-5000) * 0.10
    assert m["margin"] == 3200        # 10000 - 1300 - 500 - 5000
    assert m["margin_rate"] == 0.32


def test_detect_hot_deals():
    products = [_p(1000), _p(1000), _p(1000), _p(300)]
    deals = detect_hot_deals(products, threshold=0.7)   # 중앙값 1000, cutoff 700
    assert len(deals) == 1
    assert deals[0].price == 300
    # 표본 부족 시 빈 리스트
    assert detect_hot_deals([_p(500)]) == []


def test_competition_strength():
    products = [_p(1000, "A", 10), _p(1100, "A", 5), _p(1200, "B", 2)]
    c = competition_strength(products)
    assert c["listings"] == 3
    assert c["sellers"] == 2
    assert c["seller_concentration"] == round(2 / 3, 3)  # A가 2/3
    assert c["total_reviews"] == 17
    assert c["level"] == "low"


def test_analyze_keyword_with_margin():
    products = [_p(9000), _p(10000), _p(11000)]
    rep = analyze_keyword(products, keyword="밥", sourcing_cost=5000, market="11st")
    d = rep.to_dict()
    assert d["stats"]["median"] == 10000
    assert d["margin"] is not None
    assert d["margin"]["cost"] == 5000
    # 원가 없으면 마진 None
    assert analyze_keyword(products, keyword="밥").to_dict()["margin"] is None


if __name__ == "__main__":
    test_price_stats()
    test_price_distribution_buckets()
    test_estimate_margin()
    test_detect_hot_deals()
    test_competition_strength()
    test_analyze_keyword_with_margin()
    print("test_analysis 통과 ✅")
