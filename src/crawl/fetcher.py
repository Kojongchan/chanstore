"""예의바른 HTTP 페처.

RateLimiter + RobotsPolicy + CircuitBreaker 를 하나로 묶어, 크롤러가
"URL 하나 달라"고만 하면 나머지(속도·robots·차단감지·재시도)를 자동 처리한다.

정책(PLATFORM_PLAN.md §3):
- 정상 브라우저 UA/Accept-Language 고정(세션 단위). 매 요청 UA 무작위화는 오히려 봇 시그널.
- 세션(쿠키) 재사용.
- 403/429 또는 캡차 페이지 감지 시 hard trip → 서킷 오픈, 즉시 중단.
- 5xx/네트워크 오류는 지수 백오프로 제한 재시도.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

import httpx

from .breaker import CircuitBreaker, CircuitOpenError
from .ratelimit import RateLimiter
from .robots import RobotsPolicy, DEFAULT_UA

log = logging.getLogger(__name__)

# 캡차/차단 페이지에서 흔히 보이는 표식(대소문자 무시)
_BLOCK_MARKERS = re.compile(
    r"(captcha|자동입력\s*방지|보안\s*문자|abnormal\s+traffic|비정상적인\s*접근|"
    r"access\s+denied|가 차단|접근이\s*차단)",
    re.IGNORECASE,
)


class FetchBlocked(RuntimeError):
    """차단 신호(403/429/캡차) 감지 — 밀어붙이지 않고 중단."""


class RespectfulFetcher:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_UA,
        rate_limiter: RateLimiter | None = None,
        robots: RobotsPolicy | None = None,
        breaker: CircuitBreaker | None = None,
        respect_robots: bool = True,
        max_retries: int = 2,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.rate_limiter = rate_limiter or RateLimiter()
        self.robots = robots or RobotsPolicy(user_agent)
        self.breaker = breaker or CircuitBreaker()
        self.respect_robots = respect_robots
        self.max_retries = max_retries
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

    # --- 컨텍스트 매니저 ---
    def __enter__(self) -> "RespectfulFetcher":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    # --- 차단 판정(테스트에서 직접 검증 가능하도록 분리) ---
    @staticmethod
    def looks_blocked(status_code: int, body: str) -> bool:
        if status_code in (403, 429, 503):
            return True
        # 200 이어도 본문이 캡차/차단 페이지면 차단으로 취급
        return bool(_BLOCK_MARKERS.search(body[:4000]))

    def get(self, url: str) -> Optional[str]:
        """HTML 본문을 반환. robots 금지면 None, 차단 감지면 FetchBlocked."""
        if self.respect_robots and not self.robots.allowed(url):
            log.info("[fetch] robots 금지 — 건너뜀: %s", url)
            return None

        self.breaker.check()  # 열려 있으면 CircuitOpenError

        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            self.rate_limiter.wait(url)
            try:
                resp = self.client.get(url)
                body = resp.text
                if self.looks_blocked(resp.status_code, body):
                    self.breaker.record_failure(hard=True)  # 즉시 회로 오픈
                    raise FetchBlocked(
                        f"차단 신호(HTTP {resp.status_code}) — {url} 수집 중단"
                    )
                if resp.status_code >= 500:
                    self.breaker.record_failure()
                    log.warning("[fetch] HTTP %s (시도 %d/%d)",
                                resp.status_code, attempt, self.max_retries)
                elif resp.status_code >= 400:
                    # 4xx(차단 제외)는 재시도 의미 없음 → 실패로 종료
                    self.breaker.record_failure()
                    log.warning("[fetch] HTTP %s — 재시도 안 함: %s", resp.status_code, url)
                    return None
                else:
                    self.breaker.record_success()
                    return body
            except httpx.HTTPError as e:
                self.breaker.record_failure()
                log.warning("[fetch] 네트워크 오류 (시도 %d/%d): %s",
                            attempt, self.max_retries, e)
            if attempt < self.max_retries:
                time.sleep(backoff)
                backoff *= 2
        return None
