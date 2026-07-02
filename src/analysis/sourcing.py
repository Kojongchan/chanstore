"""소싱(되팔기) 분석 — 같은 상품 묶기 + 최저가 매입 + 마진 계산.

사장님 모델(리테일 아비트라지): "전 마켓을 뒤져 가장 싼 걸 사서, 더 비싼 데 되판다."
따라서 '원가'는 도매 상품표가 아니라 **우리가 수집한 전 마켓 가격 중 최저가**다.

흐름:
  수집된 상품들 → group_similar()로 같은 상품끼리 묶기(마켓 무관)
              → 클러스터별 최저가 = 매입 후보가(buy), 되팔 기준가(sell)와 마진 역산
              → 마진 높은 순으로 '소싱 기회' 정렬

주의: 리테일 아비트라지는 판매자 A/S·반품·정품소명 책임과 마켓 약관 리스크가 따른다(운영자 판단).
순수 함수라 네트워크 없이 테스트 가능.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..schema import Product
from .metrics import estimate_margin, MARKET_FEE_RATES

_SPLIT = re.compile(r"[^0-9A-Za-z가-힣]+")
# 상품명에 흔히 붙는 마케팅 잡토큰(매칭 방해) — 매칭 키에서 제외
_NOISE = {
    "정품", "무료배송", "무료", "당일발송", "오늘출발", "빠른배송", "최저가",
    "특가", "할인", "사은품", "증정", "쿠폰", "본사", "공식", "국내산",
}


def tokenize(name: str) -> list[str]:
    """상품명 → 매칭용 토큰. 소문자화, 2자 이상 또는 숫자포함 토큰만, 잡토큰 제외."""
    toks = [t for t in _SPLIT.split((name or "").lower()) if t]
    out = []
    for t in toks:
        if t in _NOISE:
            continue
        if len(t) >= 2 or any(c.isdigit() for c in t):
            out.append(t)
    return out


def token_set(name: str) -> set[str]:
    return set(tokenize(name))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def group_similar(products: Sequence[Product], *, threshold: float = 0.5) -> list[list[Product]]:
    """비슷한 상품을 클러스터로 묶는다(그리디, 입력 순서에 결정적).

    각 상품의 토큰집합을 기존 클러스터 대표(첫 멤버)와 Jaccard 비교해 최고 유사도가
    threshold 이상이면 합류, 아니면 새 클러스터. 마켓(source)이 달라도 묶인다.
    """
    reps: list[set[str]] = []
    clusters: list[list[Product]] = []
    for p in products:
        ts = token_set(p.name)
        best_i, best_sim = -1, 0.0
        for i, rep in enumerate(reps):
            sim = jaccard(ts, rep)
            if sim > best_sim:
                best_i, best_sim = i, sim
        if best_i >= 0 and best_sim >= threshold:
            clusters[best_i].append(p)
        else:
            reps.append(ts)
            clusters.append([p])
    return clusters


def _total_price(p: Product) -> Optional[int]:
    """실매입 비교용 총액 = 판매가 + 배송비(없으면 0). 가격 없으면 None."""
    if not isinstance(p.price, int) or p.price <= 0:
        return None
    return p.price + (p.shipping_fee if isinstance(p.shipping_fee, int) else 0)


@dataclass
class Opportunity:
    name: str
    buy: dict            # 최저가 매입 후보 {price,total,source,seller,url}
    sell_ref: dict       # 되팔 기준 {price,total,source,basis}
    margin: dict         # estimate_margin 결과(되팔 마켓 수수료 기준)
    spread: int          # sell_total - buy_total (단순 가격차)
    listings: int        # 클러스터 내 유효 매물 수
    sources: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "buy": self.buy, "sell_ref": self.sell_ref,
            "margin": self.margin, "spread": self.spread,
            "listings": self.listings, "sources": self.sources,
        }


def find_arbitrage(
    products: Sequence[Product],
    *,
    sell_market: str = "_default",
    target_price: Optional[int] = None,
    min_margin: int = 1,
    threshold: float = 0.5,
) -> list[Opportunity]:
    """되팔기 소싱 기회를 찾아 마진 높은 순으로 반환.

    - 같은 상품 클러스터에서 최저가 총액을 '매입가(buy)'로 잡는다.
    - 되팔 기준가(sell)는 target_price(있으면) 또는 클러스터 중앙값 총액.
    - sell_market 수수료율로 마진을 역산하고, margin >= min_margin 인 것만 남긴다.
    """
    import statistics

    opportunities: list[Opportunity] = []
    for cluster in group_similar(products, threshold=threshold):
        priced = [(p, _total_price(p)) for p in cluster]
        priced = [(p, t) for p, t in priced if t is not None]
        if not priced:
            continue
        priced.sort(key=lambda pt: pt[1])
        buy_p, buy_total = priced[0]
        totals = [t for _, t in priced]

        if target_price is not None:
            sell_total = target_price
            basis = "target"
        elif len(totals) >= 2:
            sell_total = round(statistics.median(totals))
            basis = "median"
        else:
            continue  # 매물 1개뿐이고 목표가도 없으면 되팔 기준이 없음

        if sell_total <= buy_total:
            continue  # 되팔 가격이 매입가보다 낮으면 기회 아님

        margin = estimate_margin(sell_total, buy_total, market=sell_market)
        if margin["margin"] < min_margin:
            continue

        opportunities.append(Opportunity(
            name=buy_p.name,
            buy={"price": buy_p.price, "total": buy_total, "source": buy_p.source,
                 "seller": buy_p.seller, "url": buy_p.product_url},
            sell_ref={"total": sell_total, "basis": basis, "market": sell_market},
            margin=margin,
            spread=sell_total - buy_total,
            listings=len(priced),
            sources=sorted({p.source for p, _ in priced}),
        ))

    opportunities.sort(key=lambda o: o.margin["margin"], reverse=True)
    return opportunities
