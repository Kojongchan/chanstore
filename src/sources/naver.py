"""네이버 쇼핑 검색 오픈API 수집 모듈 (2단계, ★2순위).

엔드포인트:
    GET https://openapi.naver.com/v1/search/shop.json?query=..&display=..&start=..
    헤더: X-Naver-Client-Id / X-Naver-Client-Secret

왜 이게 '스마트스토어 시세'인가 (PLATFORM_PLAN.md §1-3):
- 네이버 커머스 API(스마트스토어)는 '내 스토어' 전용이라 경쟁 스토어 조사에 못 쓴다.
- 쇼핑 검색 API 응답의 mallName 이 판매 몰(스마트스토어 포함)이라, 이걸로 우회 수집한다.

제약:
- 이 API는 최저가(lprice)/정가(hprice)만 주고 리뷰수·평점은 주지 않는다 → 해당 필드 None.
- start+display 는 1000 이하만 허용된다(초과 시 API가 에러).
- 이미지 URL은 참고용까지만 저장(PROJECT.md 2-1).
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any, Optional

import httpx

from ..schema import Product
from .base import BaseSource, SourceError
from .util import strip_tags, to_int

log = logging.getLogger(__name__)

ENDPOINT = "https://openapi.naver.com/v1/search/shop.json"
MAX_START = 1000  # start+display <= 1000


class NaverSource(BaseSource):
    name = "naver"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        page_size: int = 40,
        delay: float = 0.5,
        max_retries: int = 3,
        timeout: float = 15.0,
    ) -> None:
        if not client_id or not client_secret:
            raise SourceError("네이버 API 자격정보(client id/secret)가 없습니다.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.page_size = min(page_size, 100)  # API 최대 100
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout

    def search(self, keyword: str, *, pages: int = 1) -> Iterator[Product]:
        rank = 0
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        with httpx.Client(timeout=self.timeout, headers=headers) as client:
            for page in range(1, pages + 1):
                start = 1 + (page - 1) * self.page_size
                if start > MAX_START:
                    log.info("[naver] start=%d > %d — 페이지네이션 상한 도달", start, MAX_START)
                    break

                data = self._fetch_page(client, keyword, start)
                if data is None:
                    log.warning("[naver] '%s' start=%d 수집 실패 — 건너뜀", keyword, start)
                    continue

                items = data.get("items") or []
                if not items:
                    log.info("[naver] '%s' start=%d 결과 없음 — 종료", keyword, start)
                    break

                for item in items:
                    rank += 1
                    p = self._to_product(item, keyword)
                    p.rank = rank
                    yield p

                log.info("[naver] '%s' start=%d: %d건", keyword, start, len(items))
                if page < pages:
                    time.sleep(self.delay)

    def _fetch_page(
        self, client: httpx.Client, keyword: str, start: int
    ) -> Optional[dict[str, Any]]:
        params = {"query": keyword, "display": self.page_size, "start": start, "sort": "sim"}
        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = client.get(ENDPOINT, params=params)
                if resp.status_code == 401:
                    raise SourceError("네이버 API 인증 실패(401) — client id/secret 확인")
                if resp.status_code == 429:
                    log.warning("[naver] 429 rate limit (시도 %d/%d)", attempt, self.max_retries)
                else:
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as e:
                log.warning("[naver] HTTP %s (시도 %d/%d)",
                            e.response.status_code, attempt, self.max_retries)
            except httpx.HTTPError as e:
                log.warning("[naver] 네트워크 오류 (시도 %d/%d): %s", attempt, self.max_retries, e)
            if attempt < self.max_retries:
                time.sleep(backoff)
                backoff *= 2
        return None

    def _to_product(self, item: dict[str, Any], keyword: str) -> Product:
        lprice = to_int(item.get("lprice"))
        hprice = to_int(item.get("hprice"))
        cats = [item.get(f"category{i}") for i in range(1, 5)]
        category = " > ".join(c for c in cats if c)
        return Product(
            source=self.name,
            product_code=str(item.get("productId") or ""),
            keyword=keyword,
            name=strip_tags(item.get("title", "")),
            price=lprice,               # 대표가 = 최저가
            sale_price=lprice,
            list_price=hprice or None,  # 0/빈값이면 None
            image_url=item.get("image", ""),
            product_url=item.get("link", ""),
            seller=item.get("mallName", ""),
            category=category,
            extra={
                "brand": item.get("brand", ""),
                "maker": item.get("maker", ""),
                "productType": item.get("productType", ""),
            },
        )
