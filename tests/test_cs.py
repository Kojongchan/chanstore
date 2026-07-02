"""AI CS 테스트 (오프라인 규칙 경로, 네트워크·키 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ai.llm import LLMClient  # noqa: E402
from src.cs import Inquiry, KnowledgeBase, classify_intent, draft_reply  # noqa: E402

OFFLINE_LLM = LLMClient(anthropic_key="", gemini_key="")


def test_classify_rules():
    assert classify_intent("배송 언제 오나요? 송장 알려주세요", llm=OFFLINE_LLM)[0] == "배송"
    assert classify_intent("환불해주세요 결제취소요", llm=OFFLINE_LLM)[0] == "환불"
    assert classify_intent("사이즈 교환 가능한가요", llm=OFFLINE_LLM)[0] == "교환반품"
    assert classify_intent("불량이에요 파손됨 최악", llm=OFFLINE_LLM)[0] == "클레임"
    assert classify_intent("재질이 뭔가요 용량은요", llm=OFFLINE_LLM)[0] == "상품문의"


def test_draft_shipping_low_risk():
    reply = draft_reply(Inquiry(text="배송 언제쯤 도착하나요?"),
                        KnowledgeBase(), llm=OFFLINE_LLM)
    assert reply.intent == "배송"
    assert reply.provider == "offline"
    assert reply.draft                          # 정책 문구 채워짐
    assert reply.needs_human is False           # 배송 단순안내는 저위험


def test_draft_refund_requires_human():
    reply = draft_reply(Inquiry(text="환불해주세요"), KnowledgeBase(), llm=OFFLINE_LLM)
    assert reply.intent == "환불"
    assert reply.needs_human is True
    assert any("환불" in r for r in reply.reasons)


def test_draft_flags_pii():
    reply = draft_reply(
        Inquiry(text="상품 문의합니다 제 번호는 010-1234-5678 이에요"),
        KnowledgeBase(), llm=OFFLINE_LLM)
    assert reply.needs_human is True
    assert any("개인정보" in r for r in reply.reasons)


if __name__ == "__main__":
    test_classify_rules()
    test_draft_shipping_low_risk()
    test_draft_refund_requires_human()
    test_draft_flags_pii()
    print("test_cs 통과 ✅")
