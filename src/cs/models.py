"""CS 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# 의도 분류 라벨
INTENTS: list[str] = ["배송", "교환반품", "환불", "상품문의", "클레임", "기타"]

# 사람이 반드시 확정해야 하는(자동발송 금지) 의도 — 금전/보상/분쟁 직결
HUMAN_REQUIRED_INTENTS: set[str] = {"환불", "교환반품", "클레임"}


@dataclass
class Inquiry:
    text: str
    channel: str = "unknown"          # smartstore/11st/gmarket/auction 등
    author: str = ""                  # 문의자(마스킹 권장)
    order_id: Optional[str] = None
    product: Optional[str] = None
    received_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class DraftReply:
    intent: str
    draft: str                        # 답변 초안 (발송 전 사람 검수 필수)
    needs_human: bool                 # True면 사람 확인 없이는 발송 불가
    reasons: list[str] = field(default_factory=list)   # needs_human 사유
    confidence: float = 0.0           # 의도분류 신뢰도(0~1)
    provider: str = "offline"         # 초안 생성 방식

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "draft": self.draft,
            "needs_human": self.needs_human,
            "reasons": self.reasons,
            "confidence": self.confidence,
            "provider": self.provider,
        }
