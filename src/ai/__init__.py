"""AI 레이어: 상세페이지(카피·이미지) + CS 초안 생성의 공용 기반.

- llm      : 텍스트 LLM 추상화 (Claude 우선 → Gemini → 오프라인 템플릿 폴백)
- image    : nano banana(Gemini 2.5 Flash Image) 이미지 생성 래퍼
- compliance: 과장·허위광고 문구 필터(표시광고법 리스크 차단)
- copy     : 상세페이지 카피 생성
- detail_page: 카피+이미지 → 마켓별 상세 HTML 조립

키가 없어도 파이프라인이 끝까지 돌도록 모든 외부호출에 오프라인 폴백을 둔다.
"""

from .llm import LLMClient, LLMResult
from .image import ImageClient, ImageResult
from .compliance import scan_ad_text, sanitize_ad_text, BANNED_PHRASES
from .copy import DetailCopy, generate_copy
from .detail_page import build_detail_page, export_for_market

__all__ = [
    "LLMClient", "LLMResult",
    "ImageClient", "ImageResult",
    "scan_ad_text", "sanitize_ad_text", "BANNED_PHRASES",
    "DetailCopy", "generate_copy",
    "build_detail_page", "export_for_market",
]
