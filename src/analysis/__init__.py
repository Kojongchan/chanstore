"""분석 레이어 (3단계): 수집된 사실 데이터로 소싱·가격 판단 근거를 만든다.

- 가격분포 / 통계
- 마진 역산 (원가는 크롤링 값이 아니라 소싱처 입력값 — PLATFORM_PLAN.md §1-1)
- 핫딜 감지 (중앙값 대비 저가)
- 경쟁강도 (판매자 수·리뷰 집중도)
"""

from .metrics import (
    MARKET_FEE_RATES,
    price_stats,
    price_distribution,
    estimate_margin,
    detect_hot_deals,
    competition_strength,
    analyze_keyword,
)
from .sourcing import (
    tokenize,
    token_set,
    jaccard,
    group_similar,
    find_arbitrage,
    Opportunity,
)

__all__ = [
    "MARKET_FEE_RATES",
    "price_stats",
    "price_distribution",
    "estimate_margin",
    "detect_hot_deals",
    "competition_strength",
    "analyze_keyword",
    "tokenize",
    "token_set",
    "jaccard",
    "group_similar",
    "find_arbitrage",
    "Opportunity",
]
