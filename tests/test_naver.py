"""네이버 쇼핑 API 파서 테스트 (네트워크·키 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sources.naver import NaverSource  # noqa: E402

SAMPLE_ITEM = {
    "title": "CJ <b>햇반</b> 즉석밥 210g 24개",
    "link": "https://smartstore.naver.com/x/products/123",
    "image": "https://shop.example/img/a.jpg",
    "lprice": "23900",
    "hprice": "0",
    "mallName": "CJ더마켓",
    "productId": "82000123456",
    "productType": "1",
    "brand": "CJ",
    "maker": "CJ제일제당",
    "category1": "식품",
    "category2": "즉석밥",
}


def test_to_product_normalizes_fields():
    src = NaverSource("id", "secret")
    p = src._to_product(SAMPLE_ITEM, keyword="햇반")
    assert p.source == "naver"
    assert p.product_code == "82000123456"
    assert p.name == "CJ 햇반 즉석밥 210g 24개"   # <b> 태그 제거됨
    assert p.price == 23900
    assert p.sale_price == 23900
    assert p.list_price is None                    # hprice 0 → None
    assert p.seller == "CJ더마켓"
    assert p.category == "식품 > 즉석밥"
    assert p.image_url == "https://shop.example/img/a.jpg"
    assert p.review_count is None                  # 이 API는 리뷰수 미제공
    assert p.extra["brand"] == "CJ"


def test_missing_credentials_raises():
    from src.sources.base import SourceError
    try:
        NaverSource("", "")
    except SourceError:
        return
    raise AssertionError("자격정보 없으면 SourceError 나야 함")


if __name__ == "__main__":
    test_to_product_normalizes_fields()
    from src.sources.base import SourceError
    try:
        NaverSource("", "")
        raise AssertionError("자격정보 없으면 SourceError 나야 함")
    except SourceError:
        pass
    print("test_naver 통과 ✅")
