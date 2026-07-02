"""경쟁사 메인 썸네일 저장소 (분석 참고용).

정책(PLATFORM_PLAN.md §5, 갱신):
- 수집한 상품의 '메인 썸네일 1장'은 내려받아 로컬에 저장한다(내부 분석/비교/모니터링용).
- 단, 이 저장소(ref_images/)는 **참고용**이며, AI가 새로 만드는 '판매용 이미지'
  저장소(images/)와 물리적으로 분리한다. 참고용 이미지를 내 상세페이지에 재가공·재사용할지는
  별개의(저작권) 판단이며 이 모듈은 그 결정을 하지 않는다.

예의(§3):
- 이미지도 CDN에 대한 요청이므로 RateLimiter로 도메인별 간격을 둔다.
- 용량 상한/콘텐츠타입 검사로 엉뚱한 응답(HTML 에러페이지 등)을 걸러낸다.
- 이미 받은 파일은 다시 받지 않는다(캐시).

테스트를 위해 실제 다운로드 함수(fetch)를 주입할 수 있게 했다.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

from ..schema import Product
from ..crawl import RateLimiter

log = logging.getLogger(__name__)

# (bytes, content_type) 를 돌려주는 다운로드 함수 타입
FetchFn = Callable[[str], "Optional[tuple[bytes, str]]"]

_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _default_fetch(max_bytes: int, timeout: float) -> FetchFn:
    """httpx 기반 실제 다운로더. 용량 상한 스트리밍 + 콘텐츠타입 확인."""
    import httpx

    def fetch(url: str) -> Optional[tuple[bytes, str]]:
        try:
            with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
                if r.status_code != 200:
                    return None
                ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if not ctype.startswith("image/"):
                    return None
                chunks, total = [], 0
                for chunk in r.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        log.info("[thumb] 용량 초과(%s) — 건너뜀: %s", total, url)
                        return None
                    chunks.append(chunk)
                return b"".join(chunks), ctype
        except Exception as e:  # 네트워크/타임아웃 — 조용히 실패
            log.info("[thumb] 다운로드 실패: %s (%s)", url, e)
            return None

    return fetch


class ThumbnailStore:
    def __init__(
        self,
        base_dir: str | Path = "output/ref_images",
        *,
        rate_limiter: RateLimiter | None = None,
        fetch: FetchFn | None = None,
        max_bytes: int = 5 * 1024 * 1024,
        timeout: float = 15.0,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.rate_limiter = rate_limiter or RateLimiter()
        self._fetch = fetch or _default_fetch(max_bytes, timeout)

    def _target_path(self, product: Product, ext: str) -> Path:
        code = _SAFE.sub("_", product.product_code or "item")[:80]
        return self.base_dir / product.source / f"{code}{ext}"

    @staticmethod
    def _ext_from(url: str, ctype: str) -> str:
        if ctype in _EXT_BY_TYPE:
            return _EXT_BY_TYPE[ctype]
        tail = Path(urlsplit(url).path).suffix.lower()
        return tail if tail in (".jpg", ".jpeg", ".png", ".webp", ".gif") else ".jpg"

    def save(self, product: Product) -> Optional[str]:
        """상품의 메인 썸네일을 내려받아 저장하고 로컬 경로를 반환. 실패 시 None.

        - image_url 이 없으면 None.
        - 같은 (source, product_code) 로 이미 저장돼 있으면 재다운로드하지 않고 기존 경로 반환.
        """
        url = (product.image_url or "").strip()
        if not url:
            return None

        # 이미 저장된 파일이 있으면 그대로 사용(캐시)
        for existing in self.base_dir.glob(
            f"{product.source}/{_SAFE.sub('_', product.product_code or 'item')[:80]}.*"
        ):
            return str(existing)

        self.rate_limiter.wait(url)
        result = self._fetch(url)
        if result is None:
            return None
        data, ctype = result
        if not data:
            return None

        path = self._target_path(product, self._ext_from(url, ctype))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def save_all(self, products: list[Product]) -> int:
        """여러 상품의 썸네일을 저장하고 product.image_path 를 채운다. 저장 성공 수 반환."""
        saved = 0
        for p in products:
            local = self.save(p)
            if local:
                p.image_path = local
                saved += 1
        return saved
