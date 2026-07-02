"""AI CS 레이어 (6단계): 문의 → 의도분류 → 지식베이스 기반 답변초안.

핵심 원칙(PLATFORM_PLAN.md §7):
- Human-in-the-loop 기본. AI는 '초안'까지만 만들고, 발송·환불/교환/보상 확정은 사람이 한다.
- 재고·배송일 등은 실제 데이터에서만 인용(할루시네이션 차단) → 초안은 '확인 후 안내' 톤.
- 개인정보는 최소 취급/마스킹.
"""

from .models import Inquiry, DraftReply, INTENTS
from .knowledge import KnowledgeBase, DEFAULT_POLICY
from .classify import classify_intent
from .draft import draft_reply

__all__ = [
    "Inquiry", "DraftReply", "INTENTS",
    "KnowledgeBase", "DEFAULT_POLICY",
    "classify_intent", "draft_reply",
]
