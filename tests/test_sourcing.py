"""소싱(되팔기) 분석 테스트 — 매칭·최저가 매입·마진 (네트워크 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.schema import Product  # noqa: E402
from src.analysis import tokenize, jaccard, token_set, group_similar, find_arbitrage  # noqa: E402


def _p(name, price, source="11st", shipping=0, seller="s", url=""):
    return Product(source=source, product_code=f"{source}-{price}-{name[:4]}",
                   keyword="k", name=name, price=price, shipping_fee=shipping,
                   seller=seller, product_url=url)


def test_tokenize_drops_noise_and_short():
    toks = tokenize("CJ 햇반 210g 24개 [무료배송] 정품")
    assert "무료배송" not in toks and "정품" not in toks
    assert "210g" in toks and "24개" in toks and "햇반" in toks


def test_jaccard():
    a, b = token_set("햇반 210g 24개"), token_set("햇반 210g 12개")
    assert 0 < jaccard(a, b) < 1
    assert jaccard(set(), a) == 0.0


def test_group_similar_clusters_across_markets():
    products = [
        _p("CJ 햇반 210g 24개입", 23900, "11st"),
        _p("CJ 햇반 210g 24개 무료배송", 22500, "naver"),   # 같은 상품(다른 마켓)
        _p("오뚜기 맛있는밥 210g 12개", 12900, "gmarket"),   # 다른 상품
    ]
    clusters = group_similar(products, threshold=0.5)
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 2]                     # 햇반 2개 + 오뚜기 1개


def test_find_arbitrage_picks_cheapest_and_positive_margin():
    products = [
        _p("CJ 햇반 210g 24개", 30000, "gmarket", seller="비쌈"),
        _p("CJ 햇반 210g 24개", 20000, "naver", seller="최저가몰", url="http://buy/x"),
        _p("CJ 햇반 210g 24개", 25000, "11st"),
    ]
    opps = find_arbitrage(products, sell_market="11st", threshold=0.5)
    assert len(opps) == 1
    o = opps[0]
    assert o.buy["total"] == 20000           # 최저가를 매입가로
    assert o.buy["source"] == "naver"
    assert o.sell_ref["total"] == 25000      # 중앙값을 되팔 기준으로
    assert o.margin["cost"] == 20000
    assert o.spread == 5000
    assert o.listings == 3


def test_find_arbitrage_skips_when_no_upside():
    # 모든 매물 동일가 → 되팔 기준(중앙값)==매입가 → 기회 없음
    products = [_p("동일상품 A", 10000, "11st"), _p("동일상품 A", 10000, "naver")]
    assert find_arbitrage(products, sell_market="11st") == []


def test_find_arbitrage_target_price_override():
    products = [_p("단일상품 B", 10000, "naver")]   # 매물 1개
    # 목표가 없으면 기준 없음 → 빈 결과
    assert find_arbitrage(products) == []
    # 목표가 주면 계산됨
    opps = find_arbitrage(products, sell_market="naver", target_price=20000)
    assert len(opps) == 1 and opps[0].buy["total"] == 10000


if __name__ == "__main__":
    test_tokenize_drops_noise_and_short()
    test_jaccard()
    test_group_similar_clusters_across_markets()
    test_find_arbitrage_picks_cheapest_and_positive_margin()
    test_find_arbitrage_skips_when_no_upside()
    test_find_arbitrage_target_price_override()
    print("test_sourcing 통과 ✅")
