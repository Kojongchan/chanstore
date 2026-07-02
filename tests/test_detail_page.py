"""AI 상세페이지 생성 테스트 (오프라인 폴백 경로, 네트워크·키 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ai.llm import LLMClient  # noqa: E402
from src.ai.image import ImageClient  # noqa: E402
from src.ai.copy import generate_copy  # noqa: E402
from src.ai.detail_page import build_detail_page, export_for_market  # noqa: E402

# 키가 설정돼 있어도 테스트는 오프라인 경로로 강제(빈 문자열 = 미사용)
OFFLINE_LLM = LLMClient(anthropic_key="", gemini_key="")
OFFLINE_IMG = ImageClient(gemini_key="")

SPEC = {
    "name": "스테인리스 텀블러 500ml",
    "brand": "챈스토어",
    "features": ["이중 진공 보온보냉", "식기세척기 사용 가능", "최고의 마감"],
    "specs": {"용량": "500ml", "재질": "스테인리스 304"},
}


def test_generate_copy_offline_and_compliance():
    copy = generate_copy(SPEC, llm=OFFLINE_LLM)
    assert copy.provider == "offline"
    assert "챈스토어" in copy.title and "텀블러" in copy.title
    assert len(copy.bullets) == 3
    assert ("용량", "500ml") in copy.spec_rows
    # '최고의' 셀링포인트는 광고필터가 잡아 표식 처리 + 경고
    assert any("최고" in w.phrase for w in copy.warnings)
    assert all("최고" not in b for b in copy.bullets)


def test_build_detail_page_html_with_placeholder():
    page = build_detail_page(
        SPEC, llm=OFFLINE_LLM, image_client=OFFLINE_IMG, with_images=True)
    html = page["html"]
    assert "<!DOCTYPE html>" in html
    assert "스테인리스 텀블러 500ml" in html
    # 이미지 키 없음 → 플레이스홀더 SVG
    assert "<svg" in html
    assert page["images"] and page["images"][0]["available"] is False
    assert page["warnings"]  # 광고문구 경고 전달


def test_export_for_market_width():
    page = build_detail_page(SPEC, llm=OFFLINE_LLM, image_client=OFFLINE_IMG,
                             with_images=False)
    exported = export_for_market(page, "11st")
    assert exported["label"] == "11번가"
    assert "max-width:780px" in exported["html"]


if __name__ == "__main__":
    test_generate_copy_offline_and_compliance()
    test_build_detail_page_html_with_placeholder()
    test_export_for_market_width()
    print("test_detail_page 통과 ✅")
