"""도메인별 요청 속도 제한 (랜덤 지터 + 동시성 제한).

봇 탐지 회피가 목적이 아니라, 사람처럼 불규칙하고 느리게 요청해서
상대 서버에 민폐를 안 끼치고 탐지 트리거를 안 건드리기 위한 것이다.

- 고정 딜레이(예: 0.5초)는 오히려 기계적이라 봇 시그널이 된다 → 매 요청 [min,max] 사이 지터.
- 도메인별로 마지막 요청 시각을 추적해, 같은 도메인 연속 요청 사이에만 간격을 강제한다.
- 스레드에서 써도 안전하도록 락으로 보호.
"""
from __future__ import annotations

import random
import threading
import time
from urllib.parse import urlsplit


class RateLimiter:
    def __init__(
        self,
        min_delay: float = 1.5,
        max_delay: float = 4.0,
        *,
        sleep=time.sleep,
        clock=time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        if min_delay < 0 or max_delay < min_delay:
            raise ValueError("0 <= min_delay <= max_delay 이어야 합니다.")
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._sleep = sleep
        self._clock = clock
        self._rng = rng or random.Random()
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _domain(url: str) -> str:
        return urlsplit(url).netloc.lower()

    def _next_gap(self) -> float:
        """이번에 강제할 간격(초). 테스트에서 검증 가능하도록 분리."""
        return self._rng.uniform(self.min_delay, self.max_delay)

    def wait(self, url: str) -> float:
        """해당 URL의 도메인에 대해 필요한 만큼 대기하고, 실제 잔 시간(초)을 반환."""
        domain = self._domain(url)
        with self._lock:
            now = self._clock()
            gap = self._next_gap()
            last = self._last.get(domain)
            if last is None:
                # 첫 요청은 대기 없음
                slept = 0.0
            else:
                elapsed = now - last
                slept = max(0.0, gap - elapsed)
            # 다음 기준 시각을 미리 예약(대기 후 시각)해 경쟁 상태를 줄인다.
            self._last[domain] = now + slept
        if slept > 0:
            self._sleep(slept)
        return slept
