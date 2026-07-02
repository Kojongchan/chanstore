"""과장·허위광고 문구 필터 (표시광고법 리스크 차단 — PLATFORM_PLAN.md §6).

AI가 만든 상세페이지 카피/CS 문구에서 '최고·1위·100% 효과·완치' 같은
근거 없는 절대·과장 표현을 잡아낸다. 자동 삭제가 아니라 '검출→표시(마스킹 제안)'가 기본:
사람이 최종 판단하도록 위반 목록을 함께 돌려준다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (정규식 패턴, 사유) — 한국어 오픈마켓 상세페이지에서 문제되는 대표 표현들.
BANNED_PHRASES: list[tuple[str, str]] = [
    (r"최고(의|급)?", "최상급 표현(객관적 근거 필요)"),
    (r"최강", "최상급 표현"),
    (r"업계\s*1위", "순위 주장(근거·출처 필요)"),
    (r"국내\s*1위", "순위 주장(근거·출처 필요)"),
    (r"판매량?\s*1위", "판매순위 주장(근거·출처 필요)"),
    (r"100\s*%\s*(효과|만족|보장|정품)", "절대적 효과·보장 표현"),
    (r"완벽(한|하게)?", "절대적 표현"),
    (r"완치", "의학적 효능 표현(의약품 오인 우려)"),
    (r"부작용\s*(전혀\s*)?없", "안전성 절대표현"),
    (r"세계\s*최초", "최초 주장(근거 필요)"),
    (r"무조건", "절대적 표현"),
    (r"평생\s*보장", "과장 보증"),
    (r"(비교불가|타의\s*추종)", "비교 우위 과장"),
]

_COMPILED = [(re.compile(p), reason) for p, reason in BANNED_PHRASES]


@dataclass
class Violation:
    phrase: str
    reason: str
    span: tuple[int, int]


def scan_ad_text(text: str) -> list[Violation]:
    """텍스트에서 과장·허위광고 위반 후보를 찾아 반환(정렬: 등장 순서)."""
    if not text:
        return []
    found: list[Violation] = []
    for pattern, reason in _COMPILED:
        for m in pattern.finditer(text):
            found.append(Violation(phrase=m.group(0), reason=reason, span=m.span()))
    found.sort(key=lambda v: v.span[0])
    return found


def sanitize_ad_text(text: str, *, mask: str = "〔검토필요〕") -> tuple[str, list[Violation]]:
    """위반 표현을 mask 로 치환한 텍스트와 위반 목록을 함께 반환.

    실제 발송/게시 전 사람이 확인하도록, 삭제가 아니라 '검토필요' 표식으로 바꾼다.
    """
    violations = scan_ad_text(text)
    if not violations:
        return text, []
    # 뒤에서부터 치환해야 span 인덱스가 어긋나지 않는다.
    out = text
    for v in sorted(violations, key=lambda v: v.span[0], reverse=True):
        s, e = v.span
        out = out[:s] + mask + out[e:]
    return out, violations
