"""지마켓 크롤러 (후순위, 공식 API 없음).

공식 검색 API가 없어 크롤링하지만, 봇탐지가 중~높음이라 매너 크롤링 규칙(§3)을
RespectfulFetcher 로 강제한다. 셀렉터는 사이트 개편 시 조정이 필요하며,
그래서 JSON-LD 우선 파싱으로 구조 변경에 최대한 버틴다.

⚠️ 이미지·상세는 참고용까지만(PLATFORM_PLAN.md §5). 판매용 재사용 금지.
"""
from __future__ import annotations

from urllib.parse import quote

from .crawler_base import CrawlerSource, CardSelectors


class GmarketSource(CrawlerSource):
    name = "gmarket"
    base_url = "https://www.gmarket.co.kr"
    # JSON-LD가 없을 때만 쓰는 폴백 셀렉터(개편 시 조정 대상)
    selectors = CardSelectors(
        card="div.box__component-itemcard, div.box__item-container",
        name="span.text__item, a.link__item",
        price="strong.text__value, span.text__value",
        link="a.link__item",
        image="img",
    )

    def search_url(self, keyword: str, page: int) -> str:
        return f"{self.base_url}/n/search?keyword={quote(keyword)}&p={page}"
