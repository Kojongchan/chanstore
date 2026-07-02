"""가격 변동 추적 + 배치 상세 + 데모 시더 테스트 (네트워크·키 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.analysis import summarize_price_changes, group_by_status  # noqa: E402
from src.ai.llm import LLMClient  # noqa: E402
from src.ai.image import ImageClient  # noqa: E402
from src.ai import generate_batch  # noqa: E402
from src.storage import Database  # noqa: E402
from src.web import views  # noqa: E402


def _row(src, code, price, ts, name="상품"):
    return {"source": src, "product_code": code, "keyword": "k",
            "name": name, "price": price, "snapshot_at": ts}


def test_summarize_detects_down_up_new():
    rows = [
        _row("naver", "a", 10000, "2026-01-01"), _row("naver", "a", 8000, "2026-01-02"),   # down
        _row("11st", "b", 5000, "2026-01-01"), _row("11st", "b", 6000, "2026-01-02"),      # up
        _row("gmarket", "c", 3000, "2026-01-02"),                                          # new
    ]
    changes = summarize_price_changes(rows)
    by = group_by_status(changes)
    assert len(by["down"]) == 1 and by["down"][0].delta == -2000
    assert len(by["up"]) == 1 and by["up"][0].delta == 1000
    assert len(by["new"]) == 1 and by["new"][0].status == "new"
    # 하락이 맨 앞(정렬)
    assert changes[0].status == "down"


def test_summarize_ignores_non_int_price():
    rows = [_row("naver", "a", None, "2026-01-01"), _row("naver", "a", 9000, "2026-01-02")]
    changes = summarize_price_changes(rows)
    assert changes[0].status == "new"   # 유효 스냅샷 1개뿐


def test_render_tracking_view():
    changes = [{"source": "naver", "product_code": "a", "name": "샘플 텀블러",
                "latest": 8000, "previous": 10000, "delta": -2000, "pct": -0.2,
                "status": "down", "snapshots": 2}]
    html = views.render_tracking(changes, "텀블러")
    assert "하락" in html and "8,000" in html and "-20.0%" in html


OFFLINE_LLM = LLMClient(anthropic_key="", gemini_key="")
OFFLINE_IMG = ImageClient(gemini_key="")


def test_generate_batch(tmp_path):
    specs = [
        {"name": "텀블러 A", "features": ["보온"]},
        {"name": "텀블러 B", "features": ["보냉", "최고의 마감"]},   # 광고문구 포함
    ]
    results = generate_batch(specs, outdir=tmp_path, market="naver",
                             with_images=False, llm=OFFLINE_LLM, image_client=OFFLINE_IMG)
    assert len(results) == 2
    assert all(Path(r["path"]).exists() for r in results)
    # 두 번째는 '최고' 광고경고
    assert any(r["warnings"] for r in results)


def test_demo_seed_and_history(tmp_path):
    from src.demo import seed
    db_path = tmp_path / "demo.db"
    r = seed(db_path)
    assert r["products"] == 8 and r["snapshots"] == 2
    with Database(db_path) as db:
        rows = db.fetch_history("텀블러")
        assert rows                                   # 이력 존재
    changes = summarize_price_changes(rows)
    by = group_by_status(changes)
    assert by["down"]                                 # 샘플에 하락 포함


if __name__ == "__main__":
    test_summarize_detects_down_up_new()
    test_summarize_ignores_non_int_price()
    test_render_tracking_view()
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        test_generate_batch(Path(d))
        test_demo_seed_and_history(Path(d))
    print("test_tracking 통과 ✅")
