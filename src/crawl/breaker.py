"""서킷 브레이커.

403/429/캡차 같은 '차단 신호'가 뜨면 밀어붙이지 않고 즉시 그 도메인 수집을 끊는다.
밀어붙이는 것이야말로 계정/IP 밴의 지름길이기 때문이다(PLATFORM_PLAN.md §3-1).

동작:
- 연속 실패가 threshold 회에 도달하면 회로를 open → cooldown 초 동안 모든 요청 거부.
- 차단 신호(hard trip)는 1회만으로 즉시 open.
- 성공하면 실패 카운트 리셋(half-open 성공 → closed).
"""
from __future__ import annotations

import time


class CircuitOpenError(RuntimeError):
    """회로가 열려 있어 요청이 거부됨(쿨다운 중)."""


class CircuitBreaker:
    def __init__(
        self,
        *,
        threshold: int = 3,
        cooldown: float = 300.0,
        clock=time.monotonic,
    ) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if self._clock() - self._opened_at >= self.cooldown:
            # 쿨다운 경과 → half-open (다음 요청 1회 허용)
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def check(self) -> None:
        """요청 직전 호출. 열려 있으면 CircuitOpenError."""
        if self.is_open:
            raise CircuitOpenError(
                f"서킷 열림 — 차단 신호 감지로 쿨다운 중({self.cooldown:.0f}s)"
            )

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self, *, hard: bool = False) -> None:
        """실패 기록. hard=True(403/429/캡차)면 즉시 회로를 연다."""
        self._failures += 1
        if hard or self._failures >= self.threshold:
            self._opened_at = self._clock()
