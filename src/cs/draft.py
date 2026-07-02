"""답변 초안 생성 (human-in-the-loop).

절대 규칙(PLATFORM_PLAN.md §7):
- AI는 '초안'만. 발송은 사람. 특히 환불/교환/클레임·금액 확정은 needs_human=True 로 막는다.
- 지식베이스(KnowledgeBase) 정책만 근거로 삼고, 재고/배송일/금액을 지어내지 않는다.
- 개인정보(전화·이메일·주민번호·카드번호 유사)가 문의에 포함되면 사람 확인 플래그.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ..ai.llm import LLMClient
from ..ai.compliance import scan_ad_text
from .classify import classify_intent
from .knowledge import KnowledgeBase
from .models import Inquiry, DraftReply, HUMAN_REQUIRED_INTENTS

log = logging.getLogger(__name__)

# 개인정보 패턴(문의 본문에서 감지 → 사람 확인/마스킹)
_PII_PATTERNS = [
    (re.compile(r"\b\d{2,3}-\d{3,4}-\d{4}\b"), "전화번호"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "이메일"),
    (re.compile(r"\b\d{6}-\d{7}\b"), "주민등록번호 유사"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "카드번호 유사"),
]

# 초안에 금액/보상 확정이 섞이면 사람 확인 필요
_AMOUNT_RE = re.compile(r"\d[\d,]*\s*원")

_SYSTEM = (
    "너는 한국 이커머스 스토어의 CS 담당자다. 주어진 정책 컨텍스트만 근거로 "
    "정중하고 간결한 존댓말 답변 '초안'을 쓴다. 재고/배송일/환불금액 등 확실치 않은 "
    "숫자는 지어내지 말고 '확인 후 안내드리겠습니다' 톤으로 쓴다. 보상·환불 금액을 확정하지 않는다."
)


def _detect_pii(text: str) -> list[str]:
    hits = []
    for pattern, label in _PII_PATTERNS:
        if pattern.search(text or ""):
            hits.append(label)
    return hits


def _build_prompt(inq: Inquiry, kb: KnowledgeBase, intent: str) -> str:
    return (
        f"{kb.as_context(intent)}\n\n"
        f"[고객 문의]\n{inq.text}\n\n"
        "위 정책만 근거로 답변 초안을 작성해줘. 확정 불가한 정보는 확인 후 안내 톤으로."
    )


def draft_reply(
    inquiry: Inquiry,
    kb: Optional[KnowledgeBase] = None,
    *,
    llm: Optional[LLMClient] = None,
) -> DraftReply:
    """문의 → 의도분류 → 정책 기반 답변 초안. 발송은 하지 않는다."""
    kb = kb or KnowledgeBase()
    client = llm or LLMClient()

    intent, confidence = classify_intent(inquiry.text, llm=client)

    # 초안 본문: LLM 있으면 생성, 없으면 정책 문구 그대로
    provider = "offline"
    draft = kb.policy_for(intent)
    if client.available():
        res = client.generate(_build_prompt(inquiry, kb, intent), system=_SYSTEM, max_tokens=600)
        if res.available and res.text:
            draft = res.text.strip()
            provider = res.provider

    # 사람 확인 필요 판정
    reasons: list[str] = []
    if intent in HUMAN_REQUIRED_INTENTS:
        reasons.append(f"'{intent}' 의도는 금전/분쟁 직결 — 발송 전 사람 확정 필요")
    if confidence < 0.5:
        reasons.append("의도 분류 신뢰도 낮음 — 사람 확인 권장")
    pii = _detect_pii(inquiry.text)
    if pii:
        reasons.append("문의에 개인정보 포함(" + ", ".join(pii) + ") — 마스킹/사람 확인")
    if _AMOUNT_RE.search(draft):
        reasons.append("초안에 금액 표현 포함 — 금액 확정은 사람 검수 필요")
    ad_violations = scan_ad_text(draft)
    if ad_violations:
        reasons.append("초안에 과장/단정 표현 포함 — 검토 필요")

    needs_human = bool(reasons)
    return DraftReply(
        intent=intent,
        draft=draft,
        needs_human=needs_human,
        reasons=reasons,
        confidence=round(confidence, 2),
        provider=provider,
    )
