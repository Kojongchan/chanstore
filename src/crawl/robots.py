"""robots.txt 준수.

명시적으로 수집이 금지된 경로는 긁지 않는다(PLATFORM_PLAN.md §3-1).
표준 라이브러리 urllib.robotparser 를 감싸, robots.txt 를 못 가져오면
'보수적으로 허용'(대부분의 오픈마켓 상품페이지는 허용) 하되 그 사실을 로깅한다.

주의: robots.txt 자체를 가져올 때는 RateLimiter/CircuitBreaker를 거치지 않는 단발 요청이며,
실패해도 파이프라인을 죽이지 않는다.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


class RobotsPolicy:
    def __init__(self, user_agent: str = DEFAULT_UA, *, timeout: float = 10.0) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}

    def _load(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base in self._cache:
            return self._cache[base]

        parser: RobotFileParser | None = None
        robots_url = f"{base}/robots.txt"
        try:
            resp = httpx.get(
                robots_url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                parser = RobotFileParser()
                parser.parse(resp.text.splitlines())
            else:
                log.info("[robots] %s → HTTP %s, 보수적 허용", robots_url, resp.status_code)
        except httpx.HTTPError as e:
            log.info("[robots] %s 조회 실패(%s), 보수적 허용", robots_url, e)

        self._cache[base] = parser
        return parser

    def allowed(self, url: str) -> bool:
        """해당 URL 수집이 robots.txt 상 허용되는가. robots.txt 없으면 True."""
        parser = self._load(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)
