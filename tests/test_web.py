"""대시보드 렌더링 함수 테스트 (FastAPI 불필요 — 순수 HTML 빌더)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.schema import Product  # noqa: E402
from src.web import views  # noqa: E402


def test_home_renders_stats():
    html = views.render_home({"total": 5, "by_source": {"naver": 3, "11st": 2},
                              "by_keyword": {"햇반": 5}})
    assert "<!DOCTYPE html>" in html
    assert "naver" in html and "햇반" in html
    assert "5" in html


def test_products_table_and_escaping():
    p = Product(source="naver", product_code="1", keyword="k",
                name="<script>alert(1)</script> 텀블러", price=9900, seller="몰")
    html = views.render_products([p], keyword="텀블러")
    assert "9,900" in html
    assert "<script>alert(1)</script>" not in html   # 이스케이프됨
    assert "&lt;script&gt;" in html


def test_analysis_none_shows_form():
    html = views.render_analysis(None, "")
    assert "분석" in html and "<form" in html


def test_sourcing_result_renders_margin():
    opp = {
        "name": "CJ 햇반 24개", "buy": {"total": 20000, "source": "naver", "url": "http://x"},
        "sell_ref": {"total": 25000, "basis": "median"}, "spread": 5000,
        "margin": {"margin": 3175, "margin_rate": 0.116}, "listings": 3,
        "sources": ["11st", "naver"],
    }
    html = views.render_sourcing([opp], "햇반", "11st")
    assert "20,000" in html and "3,175" in html and "11.6%" in html


def test_cs_result_flags_human():
    reply = {"intent": "환불", "draft": "환불 안내드리겠습니다", "needs_human": True,
             "reasons": ["'환불' 의도는 금전 직결"], "confidence": 0.6, "provider": "offline"}
    html = views.render_cs_result(reply)
    assert "자동발송 금지" in html and "환불" in html


if __name__ == "__main__":
    test_home_renders_stats()
    test_products_table_and_escaping()
    test_analysis_none_shows_form()
    test_sourcing_result_renders_margin()
    test_cs_result_flags_human()
    print("test_web 통과 ✅")
