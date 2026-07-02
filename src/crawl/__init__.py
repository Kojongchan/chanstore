"""매너 크롤링 코어.

크롤링은 '봇 안 걸리고, 민폐 안 끼치고, 계정/IP 안 날리는' 것이 목적이다
(PLATFORM_PLAN.md §3). 이 패키지는 그 규칙을 코드로 강제하는 공용 부품을 제공한다:

- RateLimiter : 도메인별 랜덤 지터 딜레이 + 동시성 제한
- RobotsPolicy: robots.txt 파싱/준수
- CircuitBreaker: 403/429/캡차 감지 시 즉시 차단하고 쿨다운
- RespectfulFetcher: 위 셋을 묶은 예의바른 HTTP 클라이언트(재시도·지수백오프 포함)

크롤러(지마켓·옥션)는 이 부품들만 쓰고, 직접 httpx로 폭주 요청을 보내지 않는다.
"""

from .ratelimit import RateLimiter
from .robots import RobotsPolicy
from .breaker import CircuitBreaker, CircuitOpenError
from .fetcher import RespectfulFetcher, FetchBlocked

__all__ = [
    "RateLimiter",
    "RobotsPolicy",
    "CircuitBreaker",
    "CircuitOpenError",
    "RespectfulFetcher",
    "FetchBlocked",
]
