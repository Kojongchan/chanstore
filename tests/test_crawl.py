"""매너 크롤링 코어 + 크롤러 파싱 테스트 (네트워크 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import random  # noqa: E402

from src.crawl import RateLimiter, CircuitBreaker, CircuitOpenError, RespectfulFetcher  # noqa: E402
from src.sources.gmarket import GmarketSource  # noqa: E402


def test_rate_limiter_first_call_no_wait_then_gaps():
    slept = []
    fake_clock = [0.0]
    limiter = RateLimiter(
        min_delay=2.0, max_delay=2.0,
        sleep=lambda s: slept.append(s),
        clock=lambda: fake_clock[0],
        rng=random.Random(1),
    )
    # 첫 요청: 대기 없음
    assert limiter.wait("https://a.com/x") == 0.0
    # 즉시 두 번째 요청(같은 도메인): 2초 지터 강제
    assert limiter.wait("https://a.com/y") == 2.0
    # 다른 도메인 첫 요청: 대기 없음
    assert limiter.wait("https://b.com/z") == 0.0
    assert slept == [2.0]


def test_circuit_breaker_hard_trip_and_cooldown():
    t = [0.0]
    cb = CircuitBreaker(threshold=3, cooldown=100.0, clock=lambda: t[0])
    cb.check()                       # 닫힘 → 통과
    cb.record_failure(hard=True)     # 차단 신호 1회로 즉시 오픈
    assert cb.is_open
    try:
        cb.check()
        raise AssertionError("열린 회로에서 check()는 CircuitOpenError 여야 함")
    except CircuitOpenError:
        pass
    # 쿨다운 경과 → half-open(닫힘 취급)
    t[0] = 101.0
    assert not cb.is_open
    cb.check()  # 예외 없음


def test_circuit_breaker_soft_threshold():
    cb = CircuitBreaker(threshold=3, cooldown=100.0, clock=lambda: 0.0)
    cb.record_failure()
    cb.record_failure()
    assert not cb.is_open       # 2회 → 아직 닫힘
    cb.record_failure()
    assert cb.is_open           # 3회째 → 오픈


def test_looks_blocked():
    assert RespectfulFetcher.looks_blocked(403, "forbidden")
    assert RespectfulFetcher.looks_blocked(429, "")
    assert RespectfulFetcher.looks_blocked(200, "보안 문자를 입력하세요")  # 캡차
    assert RespectfulFetcher.looks_blocked(200, "captcha required")
    assert not RespectfulFetcher.looks_blocked(200, "정상 상품 목록입니다")


# 검색결과 페이지에 SEO용 JSON-LD(ItemList>Product)가 있는 경우
SAMPLE_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ItemList","itemListElement":[
  {"@type":"ListItem","item":{"@type":"Product","name":"테스트 밥 210g",
     "sku":"G123","url":"/item/G123","image":["https://img/x.jpg"],
     "offers":{"@type":"Offer","price":"12900","priceCurrency":"KRW"},
     "aggregateRating":{"@type":"AggregateRating","ratingValue":"4.7","reviewCount":"31"}}},
  {"@type":"ListItem","item":{"@type":"Product","name":"다른 밥",
     "sku":"G456","url":"/item/G456",
     "offers":{"@type":"Offer","price":"9,900"}}}
]}
</script></head><body>...</body></html>
"""


def test_crawler_parses_jsonld():
    src = GmarketSource()
    products = src.parse_listings(SAMPLE_HTML, keyword="밥")
    assert len(products) == 2
    p = products[0]
    assert p.source == "gmarket"
    assert p.product_code == "G123"
    assert p.name == "테스트 밥 210g"
    assert p.price == 12900
    assert p.product_url == "https://www.gmarket.co.kr/item/G123"
    assert p.image_url == "https://img/x.jpg"
    assert p.rating == 4.7
    assert p.review_count == 31
    assert products[1].price == 9900   # '9,900' → 9900


if __name__ == "__main__":
    test_rate_limiter_first_call_no_wait_then_gaps()
    test_circuit_breaker_hard_trip_and_cooldown()
    test_circuit_breaker_soft_threshold()
    test_looks_blocked()
    test_crawler_parses_jsonld()
    print("test_crawl 통과 ✅")
