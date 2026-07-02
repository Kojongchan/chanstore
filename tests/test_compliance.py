"""과장광고 문구 필터 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ai.compliance import scan_ad_text, sanitize_ad_text  # noqa: E402


def test_scan_detects_banned():
    v = scan_ad_text("국내 1위 최고의 품질, 부작용 전혀 없음")
    phrases = [x.phrase for x in v]
    assert any("1위" in p for p in phrases)
    assert any("최고" in p for p in phrases)
    assert any("부작용" in p for p in phrases)


def test_clean_text_no_violation():
    assert scan_ad_text("튼튼한 스테인리스 재질, 210g 용량") == []


def test_sanitize_masks():
    text = "이 제품은 최고의 선택입니다"
    cleaned, violations = sanitize_ad_text(text)
    assert violations
    assert "최고" not in cleaned
    assert "검토필요" in cleaned


if __name__ == "__main__":
    test_scan_detects_banned()
    test_clean_text_no_violation()
    test_sanitize_masks()
    print("test_compliance 통과 ✅")
