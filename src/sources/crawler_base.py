"""크롤링 소스 공통 베이스 (지마켓·옥션 등 공식 API가 없는 마켓).

설계:
- 모든 요청은 RespectfulFetcher 를 통해서만 나간다(속도·robots·차단감지 자동).
- 파싱은 2단계 전략으로 '깨져도 최대한 건지기':
    1) schema.org JSON-LD(<script type="application/ld+json">)의 Product 를 우선 추출.
       마켓들이 SEO용으로 심어두는 경우가 많고, HTML 구조 변경에 강하다.
    2) 없으면 마켓별 CSS 셀렉터(하위 클래스가 지정)로 카드 단위 추출.
- FetchBlocked / CircuitOpenError 가 나면 그 마켓 수집만 '조용히 중단'하고 예외를 삼킨다.
  (한 소스가 죽어도 나머지 파이프라인은 계속 — PROJECT.md 2-3)

파싱 로직 self.parse_listings() 는 네트워크 없이 단위테스트할 수 있게 순수 함수로 뒀다.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from ..schema import Product
from ..crawl import RespectfulFetcher, FetchBlocked, CircuitOpenError
from .base import BaseSource
from .util import to_int, to_float, strip_tags

log = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup  # type: ignore
    _HAS_BS4 = True
except ImportError:  # bs4 미설치 시 JSON-LD 경로만 동작
    BeautifulSoup = None  # type: ignore
    _HAS_BS4 = False


@dataclass
class CardSelectors:
    """마켓별 검색결과 카드 CSS 셀렉터 (JSON-LD 폴백용)."""
    card: str
    name: str
    price: str
    link: str
    image: str = ""


class CrawlerSource(BaseSource):
    #: 하위 클래스가 지정
    base_url: str = ""
    selectors: Optional[CardSelectors] = None

    def __init__(self, *, fetcher: RespectfulFetcher | None = None) -> None:
        self._fetcher = fetcher
        self._owns_fetcher = fetcher is None

    # --- 하위 클래스가 구현 ---
    def search_url(self, keyword: str, page: int) -> str:
        raise NotImplementedError

    # --- 진입점 ---
    def search(self, keyword: str, *, pages: int = 1) -> Iterator[Product]:
        fetcher = self._fetcher or RespectfulFetcher()
        rank = 0
        try:
            for page in range(1, pages + 1):
                url = self.search_url(keyword, page)
                try:
                    html = fetcher.get(url)
                except FetchBlocked as e:
                    log.warning("[%s] 차단 감지 — 수집 중단: %s", self.name, e)
                    break
                except CircuitOpenError as e:
                    log.warning("[%s] 서킷 오픈 — 수집 중단: %s", self.name, e)
                    break

                if not html:
                    log.info("[%s] '%s' %d페이지 본문 없음 — 건너뜀", self.name, keyword, page)
                    continue

                products = self.parse_listings(html, keyword)
                if not products:
                    log.info("[%s] '%s' %d페이지 파싱 결과 없음 — 종료", self.name, keyword, page)
                    break

                for p in products:
                    rank += 1
                    p.rank = rank
                    yield p
                log.info("[%s] '%s' %d페이지: %d건", self.name, keyword, page, len(products))
        finally:
            if self._owns_fetcher:
                fetcher.close()

    # --- 파싱 (순수 함수, 테스트 대상) ---
    def parse_listings(self, html: str, keyword: str) -> list[Product]:
        products = self._parse_jsonld(html, keyword)
        if products:
            return products
        return self._parse_cards(html, keyword)

    def _parse_jsonld(self, html: str, keyword: str) -> list[Product]:
        products: list[Product] = []
        for blob in _iter_jsonld_blocks(html):
            for node in _iter_product_nodes(blob):
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = to_int(offers.get("price")) if isinstance(offers, dict) else None
                url = node.get("url") or (offers.get("url") if isinstance(offers, dict) else "")
                url = urljoin(self.base_url, url or "")
                code = str(node.get("sku") or node.get("productID") or url)
                image = node.get("image")
                if isinstance(image, list):
                    image = image[0] if image else ""
                products.append(Product(
                    source=self.name,
                    product_code=code,
                    keyword=keyword,
                    name=strip_tags(str(node.get("name", ""))),
                    price=price,
                    sale_price=price,
                    image_url=str(image or ""),
                    product_url=url,
                    seller=str((node.get("brand") or {}).get("name", "")
                               if isinstance(node.get("brand"), dict) else node.get("brand") or ""),
                    rating=_extract_rating(node),
                    review_count=_extract_review_count(node),
                ))
        return products

    def _parse_cards(self, html: str, keyword: str) -> list[Product]:
        if not (_HAS_BS4 and self.selectors):
            if not _HAS_BS4:
                log.info("[%s] bs4 미설치 + JSON-LD 없음 → 카드 파싱 생략", self.name)
            return []
        sel = self.selectors
        soup = BeautifulSoup(html, "html.parser")
        products: list[Product] = []
        for i, card in enumerate(soup.select(sel.card), start=1):
            name_el = card.select_one(sel.name)
            link_el = card.select_one(sel.link)
            price_el = card.select_one(sel.price)
            if not (name_el and link_el):
                continue
            href = link_el.get("href", "")
            url = urljoin(self.base_url, href)
            img_el = card.select_one(sel.image) if sel.image else None
            image = (img_el.get("src") or img_el.get("data-original") or "") if img_el else ""
            price = to_int(price_el.get_text()) if price_el else None
            products.append(Product(
                source=self.name,
                product_code=url or f"{self.name}:{keyword}:{i}",
                keyword=keyword,
                name=strip_tags(name_el.get_text()),
                price=price,
                sale_price=price,
                image_url=image,
                product_url=url,
            ))
        return products


# --- JSON-LD 헬퍼 (모듈 함수, 순수) ---
def _iter_jsonld_blocks(html: str):
    """<script type="application/ld+json"> 블록들을 파싱해 yield. bs4 없이도 동작."""
    marker = 'application/ld+json'
    idx = 0
    lowered = html.lower()
    while True:
        pos = lowered.find(marker, idx)
        if pos == -1:
            break
        start = html.find(">", pos)
        end = lowered.find("</script>", start)
        if start == -1 or end == -1:
            break
        raw = html[start + 1:end].strip()
        idx = end + 1
        try:
            yield json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue


def _iter_product_nodes(blob):
    """JSON-LD blob 에서 @type=Product 노드들을 재귀적으로 찾아 yield."""
    if isinstance(blob, list):
        for item in blob:
            yield from _iter_product_nodes(item)
        return
    if not isinstance(blob, dict):
        return
    graph = blob.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            yield from _iter_product_nodes(item)
    items = blob.get("itemListElement")
    if isinstance(items, list):
        for el in items:
            node = el.get("item") if isinstance(el, dict) else None
            if node:
                yield from _iter_product_nodes(node)
    t = blob.get("@type")
    types = t if isinstance(t, list) else [t]
    if any(str(x).lower() == "product" for x in types):
        yield blob


def _extract_rating(node: dict):
    agg = node.get("aggregateRating")
    if isinstance(agg, dict):
        return to_float(agg.get("ratingValue"))
    return None


def _extract_review_count(node: dict):
    agg = node.get("aggregateRating")
    if isinstance(agg, dict):
        return to_int(agg.get("reviewCount") or agg.get("ratingCount"))
    return None
