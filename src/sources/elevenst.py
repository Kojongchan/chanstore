"""11번가 공식 오픈API(ProductSearch) 수집 모듈.

엔드포인트:
    http://openapi.11st.co.kr/openapi/OpenApiService.tmall
        ?key=[KEY]&apiCode=ProductSearch&keyword=[KEYWORD]&pageNum=N&pageSize=M

주의:
- 응답은 XML이며 인코딩이 EUC-KR/CP949 인 경우가 많다. expat(표준 파서)은
  euc-kr을 직접 해석하지 못하므로, 바이트를 직접 디코딩한 뒤 XML 선언의
  encoding 속성을 제거하고 파싱한다. (이 처리를 빠뜨리면 한글이 깨진다.)
- 이미지 URL은 '참고용'으로만 저장한다 (PROJECT.md 2-1). 다운로드/재가공 금지.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from typing import Optional

import httpx

from ..schema import Product
from .base import BaseSource, SourceError

log = logging.getLogger(__name__)

ENDPOINT = "http://openapi.11st.co.kr/openapi/OpenApiService.tmall"
API_CODE = "ProductSearch"

# XML 선언을 찾기 위한 패턴 (바이트용 / 문자열용)
_XML_DECL_RE_B = re.compile(rb"<\?xml[^>]*\?>", re.IGNORECASE)
_XML_DECL_RE_S = re.compile(r"<\?xml[^>]*\?>", re.IGNORECASE)
_ENCODING_RE = re.compile(r'encoding\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _decode_xml(raw: bytes) -> str:
    """11번가 응답 바이트를 선언된 인코딩으로 디코딩하고, 선언의 encoding 속성을 제거한다.

    표준 ElementTree(expat)는 유니코드 문자열에 encoding 선언이 남아 있으면 거부하고,
    euc-kr 같은 인코딩을 바이트 상태로는 해석하지 못한다. 그래서:
      1) 선언에서 인코딩 이름을 추출 (없으면 cp949 기본)
      2) 해당 인코딩으로 디코딩 (실패 시 cp949 → utf-8 순으로 폴백)
      3) <?xml ... ?> 선언 자체를 제거 후 str 반환
    """
    declared: Optional[str] = None
    m = _XML_DECL_RE_B.search(raw[:200])
    if m:
        enc_m = _ENCODING_RE.search(m.group(0).decode("ascii", errors="ignore"))
        if enc_m:
            declared = enc_m.group(1).strip()

    # cp949 는 euc-kr 의 상위호환이라 euc-kr 데이터도 안전하게 처리한다.
    candidates = [declared, "cp949", "euc-kr", "utf-8"]
    text: Optional[str] = None
    for enc in candidates:
        if not enc:
            continue
        norm = "cp949" if enc.lower() in ("euc-kr", "euckr", "ks_c_5601-1987") else enc
        try:
            text = raw.decode(norm)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        text = raw.decode("cp949", errors="replace")

    # 유니코드 문자열에 encoding 선언이 있으면 ET.fromstring 이 거부 → 선언 제거
    return _XML_DECL_RE_S.sub("", text, count=1).lstrip("﻿").strip()


def _text(elem: Optional[ET.Element]) -> str:
    return (elem.text or "").strip() if elem is not None else ""


def _to_int(value: str) -> Optional[int]:
    """'12,900원' 같은 문자열에서 정수만 뽑는다. 실패 시 None."""
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits) if digits else None


def _to_float(value: str) -> Optional[float]:
    try:
        return float(re.sub(r"[^\d.]", "", value)) if value else None
    except ValueError:
        return None


class ElevenStSource(BaseSource):
    name = "11st"

    def __init__(
        self,
        api_key: str,
        *,
        page_size: int = 40,
        delay: float = 0.5,
        max_retries: int = 3,
        timeout: float = 15.0,
    ) -> None:
        if not api_key:
            raise SourceError("11번가 API 키가 없습니다.")
        self.api_key = api_key
        self.page_size = page_size
        self.delay = delay          # 호출 간 딜레이 (API 예의)
        self.max_retries = max_retries
        self.timeout = timeout

    # --- 공개 진입점 ---------------------------------------------------------
    def search(self, keyword: str, *, pages: int = 1) -> Iterator[Product]:
        rank = 0
        with httpx.Client(timeout=self.timeout) as client:
            for page in range(1, pages + 1):
                raw = self._fetch_page(client, keyword, page)
                if raw is None:
                    log.warning("[11st] '%s' %d페이지 수집 실패 — 건너뜀", keyword, page)
                    continue

                products = self._parse(raw, keyword)
                if not products:
                    log.info("[11st] '%s' %d페이지 결과 없음 — 수집 종료", keyword, page)
                    break

                for p in products:
                    rank += 1
                    p.rank = rank
                    yield p

                log.info("[11st] '%s' %d페이지: %d건", keyword, page, len(products))

                if page < pages:
                    time.sleep(self.delay)

    # --- 내부 구현 -----------------------------------------------------------
    def _fetch_page(
        self, client: httpx.Client, keyword: str, page: int
    ) -> Optional[bytes]:
        """1개 페이지를 재시도와 함께 호출. 성공 시 응답 바이트, 최종 실패 시 None."""
        params = {
            "key": self.api_key,
            "apiCode": API_CODE,
            "keyword": keyword,
            "pageNum": page,
            "pageSize": self.page_size,
        }
        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = client.get(ENDPOINT, params=params)
                resp.raise_for_status()
                return resp.content
            except httpx.HTTPStatusError as e:
                log.warning(
                    "[11st] HTTP %s (page=%d, 시도 %d/%d)",
                    e.response.status_code, page, attempt, self.max_retries,
                )
            except httpx.HTTPError as e:
                log.warning(
                    "[11st] 네트워크 오류 (page=%d, 시도 %d/%d): %s",
                    page, attempt, self.max_retries, e,
                )
            if attempt < self.max_retries:
                time.sleep(backoff)
                backoff *= 2  # 지수 백오프
        return None

    def _parse(self, raw: bytes, keyword: str) -> list[Product]:
        text = _decode_xml(raw)
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            # 키 오류/쿼터 초과 등은 11번가가 에러 XML 또는 메시지를 돌려준다.
            snippet = text[:300].replace("\n", " ")
            raise SourceError(f"11번가 응답 파싱 실패: {e} / 응답 일부: {snippet}") from e

        # API 레벨 에러 메시지 감지 (예: <ErrorCode>/<message> 형태)
        err = root.find(".//ErrorCode")
        if err is not None and _text(err) not in ("", "0"):
            msg = _text(root.find(".//message")) or _text(err)
            raise SourceError(f"11번가 API 에러: {msg}")

        products: list[Product] = []
        for node in root.iter("Product"):
            products.append(self._node_to_product(node, keyword))
        return products

    def _node_to_product(self, node: ET.Element, keyword: str) -> Product:
        def g(*tags: str) -> str:
            """여러 후보 태그명 중 처음 존재하는 값을 반환 (스키마 변동 대비)."""
            for t in tags:
                v = _text(node.find(t))
                if v:
                    return v
            return ""

        return Product(
            source=self.name,
            product_code=g("ProductCode", "ProductId"),
            keyword=keyword,
            name=g("ProductName"),
            price=_to_int(g("ProductPrice", "SalePrice", "Price")),
            image_url=g("ProductImage", "ProductImage300", "ProductImage200"),
            product_url=g("DetailPageUrl", "ProductUrl"),
            seller=g("Seller", "SellerNick", "StoreName"),
            review_count=_to_int(g("ReviewCount", "BuySatisfy")),
            rating=_to_float(g("Rating", "PointBenefit")),
            category=g("CategoryName", "CategoryCode"),
            delivery=g("Delivery", "DeliveryPrice"),
            extra={"sale_price": g("SalePrice"), "minor_yn": g("minorYn")},
        )
