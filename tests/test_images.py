"""썸네일 저장소 테스트 (fetch 주입으로 네트워크 불필요)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.schema import Product  # noqa: E402
from src.storage import ThumbnailStore  # noqa: E402


def _stub_fetch(calls):
    def fetch(url):
        calls.append(url)
        return b"\x89PNG_fake_bytes", "image/png"
    return fetch


def _p(code="A1", url="https://cdn.example/img/a.jpg", source="naver"):
    return Product(source=source, product_code=code, keyword="k",
                   name="상품", image_url=url)


def test_save_downloads_and_sets_path(tmp_path):
    calls = []
    store = ThumbnailStore(tmp_path, fetch=_stub_fetch(calls))
    p = _p()
    path = store.save(p)
    assert path is not None
    assert Path(path).exists()
    assert Path(path).suffix == ".png"     # content-type 우선
    assert "naver" in path                  # 소스별 폴더 분리
    assert len(calls) == 1


def test_no_image_url_returns_none(tmp_path):
    store = ThumbnailStore(tmp_path, fetch=_stub_fetch([]))
    assert store.save(_p(url="")) is None


def test_cache_skips_redownload(tmp_path):
    calls = []
    store = ThumbnailStore(tmp_path, fetch=_stub_fetch(calls))
    p = _p()
    store.save(p)
    store.save(p)                           # 두 번째는 캐시 사용
    assert len(calls) == 1                   # 다운로드는 1회뿐


def test_save_all_sets_image_path(tmp_path):
    store = ThumbnailStore(tmp_path, fetch=_stub_fetch([]))
    products = [_p("A1"), _p("A2", url=""), _p("A3")]
    saved = store.save_all(products)
    assert saved == 2                        # A2는 url 없어 스킵
    assert products[0].image_path and Path(products[0].image_path).exists()
    assert products[1].image_path == ""


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        test_save_downloads_and_sets_path(base / "1")
        test_no_image_url_returns_none(base / "2")
        test_cache_skips_redownload(base / "3")
        test_save_all_sets_image_path(base / "4")
    print("test_images 통과 ✅")
