"""가격 변동 추적 — 이력 스냅샷을 비교해 하락/상승/신규를 감지 (순수 함수).

입력: fetch_history() 가 준 스냅샷 행 리스트(각 dict: source, product_code, name, price, snapshot_at).
출력: 상품별 최신 vs 직전 스냅샷 비교 결과. 하락 폭 큰 순으로 정렬.

키가 나오면 매일 collect → snapshot 이 쌓이고, 이 함수가 "어제보다 떨어진 것 / 새 경쟁자"를
뽑아 알림의 근거가 된다. 지금은 데모 데이터/수동 스냅샷으로도 동작·테스트된다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass
class PriceChange:
    source: str
    product_code: str
    name: str
    latest: int
    previous: Optional[int]     # 직전 스냅샷 가격(신규면 None)
    delta: Optional[int]        # latest - previous
    pct: Optional[float]        # delta / previous
    status: str                 # "down" | "up" | "same" | "new"
    snapshots: int

    def to_dict(self) -> dict:
        return {
            "source": self.source, "product_code": self.product_code, "name": self.name,
            "latest": self.latest, "previous": self.previous, "delta": self.delta,
            "pct": self.pct, "status": self.status, "snapshots": self.snapshots,
        }


def summarize_price_changes(rows: Sequence[dict]) -> list[PriceChange]:
    """이력 행 → 상품별 변동 요약. 하락 폭 큰 순(내림값이 앞) 정렬."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        if not isinstance(r.get("price"), int):
            continue
        groups.setdefault((r["source"], r["product_code"]), []).append(r)

    changes: list[PriceChange] = []
    for (src, code), items in groups.items():
        items.sort(key=lambda r: r["snapshot_at"])
        latest = items[-1]
        prev = items[-2] if len(items) >= 2 else None
        latest_price = latest["price"]
        prev_price = prev["price"] if prev else None

        if prev_price is None:
            status, delta, pct = "new", None, None
        else:
            delta = latest_price - prev_price
            pct = round(delta / prev_price, 4) if prev_price else None
            status = "down" if delta < 0 else "up" if delta > 0 else "same"

        changes.append(PriceChange(
            source=src, product_code=code, name=latest.get("name", ""),
            latest=latest_price, previous=prev_price, delta=delta, pct=pct,
            status=status, snapshots=len(items),
        ))

    # 하락(음수 delta)이 앞으로 오게 delta 오름차순. delta None(신규)은 뒤로.
    changes.sort(key=lambda c: (c.delta is None, c.delta if c.delta is not None else 0))
    return changes


def group_by_status(changes: Sequence[PriceChange]) -> dict[str, list[PriceChange]]:
    out: dict[str, list[PriceChange]] = {"down": [], "up": [], "same": [], "new": []}
    for c in changes:
        out[c.status].append(c)
    return out
