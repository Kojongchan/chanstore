"""CS 지식베이스: 스토어 정책 + FAQ.

초안 생성기가 인용할 '사실'의 단일 출처. LLM이 정책을 지어내지 않도록,
답변 초안은 여기 담긴 내용만 근거로 삼는다(PLATFORM_PLAN.md §7).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 기본 스토어 정책(운영자가 자기 스토어 기준으로 교체). 의도별 안내 뼈대.
DEFAULT_POLICY: dict[str, str] = {
    "배송": "주문은 결제 확인 후 영업일 기준 1~2일 내 출고되며, 택배사 사정에 따라 "
            "수령까지 2~3일 소요될 수 있습니다. 정확한 배송 현황은 주문내역에서 확인 후 안내드리겠습니다.",
    "교환반품": "단순 변심 교환/반품은 수령 후 7일 이내 가능하며 왕복 배송비가 부과될 수 있습니다. "
                "상품 하자/오배송은 무료로 처리됩니다. 접수 후 담당자가 확인해 안내드리겠습니다.",
    "환불": "환불은 반품 상품 회수·검수 완료 후 결제수단 기준으로 진행됩니다. "
            "구체적 금액과 일정은 주문 확인 후 담당자가 안내드리겠습니다.",
    "상품문의": "문의 주신 상품 사양은 상세페이지 스펙 기준으로 확인해 안내드리겠습니다. "
                "추가로 궁금하신 점을 알려주시면 확인 후 답변드리겠습니다.",
    "클레임": "불편을 드려 죄송합니다. 상황을 정확히 확인하기 위해 주문번호와 사진(해당 시)을 "
              "보내주시면 담당자가 신속히 확인해 처리 방안을 안내드리겠습니다.",
    "기타": "문의 감사합니다. 내용을 확인한 뒤 담당자가 정확히 안내드리겠습니다.",
}


@dataclass
class KnowledgeBase:
    policy: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_POLICY))
    faqs: list[dict] = field(default_factory=list)   # [{"q":..., "a":...}]
    store_name: str = "우리 스토어"
    tone: str = "정중하고 간결한 존댓말"

    def policy_for(self, intent: str) -> str:
        return self.policy.get(intent, self.policy.get("기타", ""))

    def as_context(self, intent: str) -> str:
        """LLM 프롬프트에 넣을 정책 컨텍스트 문자열."""
        lines = [f"[스토어] {self.store_name}", f"[말투] {self.tone}",
                 f"[해당 의도 정책] {self.policy_for(intent)}"]
        if self.faqs:
            lines.append("[FAQ]")
            for f in self.faqs[:10]:
                lines.append(f"- Q:{f.get('q','')} / A:{f.get('a','')}")
        return "\n".join(lines)
