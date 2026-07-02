"""문의 의도 분류.

LLM이 있으면 라벨을 물어 분류하고, 없으면 키워드 규칙으로 폴백한다.
반환: (intent, confidence 0~1).
"""
from __future__ import annotations

import logging
from typing import Optional

from ..ai.llm import LLMClient
from .models import INTENTS

log = logging.getLogger(__name__)

# 키워드 규칙(폴백). 위에 있을수록 우선순위 높음(클레임>환불>교환반품>배송>상품문의).
_RULES: list[tuple[str, list[str]]] = [
    ("클레임", ["화나", "최악", "환불해줘요", "불량", "하자", "파손", "터졌", "신고",
                "고장", "썩", "이물질", "사기"]),
    ("환불", ["환불", "결제취소", "돈 돌려", "취소해"]),
    ("교환반품", ["교환", "반품", "다른 색", "사이즈 변경", "바꿔", "반송"]),
    ("배송", ["배송", "언제 와", "출고", "송장", "택배", "도착", "언제쯤", "운송장"]),
    ("상품문의", ["사이즈", "재질", "색상", "스펙", "호환", "용량", "사용법", "정품",
                 "성분", "재고", "옵션"]),
]

_SYSTEM = (
    "너는 이커머스 CS 문의 분류기다. 문의를 다음 중 하나로만 분류해 라벨 한 단어로 답한다: "
    + ", ".join(INTENTS)
)


def _rule_based(text: str) -> tuple[str, float]:
    t = text or ""
    for intent, kws in _RULES:
        if any(kw in t for kw in kws):
            return intent, 0.6
    return "기타", 0.3


def classify_intent(text: str, *, llm: Optional[LLMClient] = None) -> tuple[str, float]:
    client = llm or LLMClient()
    if client.available():
        res = client.generate(f"문의: {text}\n라벨만 답해.", system=_SYSTEM, max_tokens=10)
        if res.available and res.text:
            label = res.text.strip().split()[0].strip("[]:.\"' ")
            for intent in INTENTS:
                if intent in label:
                    return intent, 0.85
            log.info("[cs] LLM 라벨 미매칭(%r) — 규칙 폴백", res.text[:40])
    return _rule_based(text)
