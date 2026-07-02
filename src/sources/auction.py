"""옥션 크롤러 (후순위, 공식 API 없음).

지마켓과 같은 ESM 계열이라 구조·주의사항이 유사하다. 매너 크롤링 규칙(§3)을
RespectfulFetcher 로 강제하고, JSON-LD 우선 파싱으로 개편에 버틴다.

⚠️ 이미지·상세는 참고용까지만(PLATFORM_PLAN.md §5). 판매용 재사용 금지.
"""
from __future__ import annotations

from urllib.parse import quote

from .crawler_base import CrawlerSource, CardSelectors


class AuctionSource(CrawlerSource):
    name = "auction"
    base_url = "https://www.auction.co.kr"
    selectors = CardSelectors(
        card="div.section--itemcard, li.item",
        name="span.text--title, a.link--itemcard",
        price="strong.text--price_seller, span.price",
        link="a.link--itemcard, a.link--item",
        image="img",
    )

    def search_url(self, keyword: str, page: int) -> str:
        return f"{self.base_url}/n/search?keyword={quote(keyword)}&page={page}"
