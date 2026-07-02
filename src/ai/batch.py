"""배치 상세페이지 생성 — 여러 상품 스펙을 한 번에 상세 HTML로.

키가 없어도 오프라인 폴백으로 전부 생성된다. 마켓 업로드(판매자 API)는 별개 단계(키 필요).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .detail_page import build_detail_page, export_for_market
from .image import ImageClient
from .llm import LLMClient

log = logging.getLogger(__name__)


def _safe_name(spec: dict, idx: int) -> str:
    raw = str(spec.get("name", "")) or f"item{idx}"
    return "".join(c for c in raw if c.isalnum() or c in " _-").strip() or f"item{idx}"


def generate_batch(
    specs: list[dict],
    *,
    outdir: str | Path = "output/details",
    market: str = "_default",
    with_images: bool = True,
    llm: Optional[LLMClient] = None,
    image_client: Optional[ImageClient] = None,
) -> list[dict]:
    """스펙 리스트 → 각 상세페이지 HTML 파일 생성. 결과 요약 리스트 반환.

    반환 항목: {index, name, path, market, provider, warnings, images, error?}
    한 상품 생성이 실패해도 나머지는 계속한다.
    """
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for i, spec in enumerate(specs, start=1):
        try:
            page = build_detail_page(
                spec, llm=llm, image_client=image_client, with_images=with_images)
            exported = export_for_market(page, market)
            name = _safe_name(spec, i)
            path = out / f"상세_{i:02d}_{name}.html"
            path.write_text(exported["html"], encoding="utf-8")
            results.append({
                "index": i, "name": page["copy"]["title"], "path": str(path),
                "market": exported["label"], "provider": page["copy"]["provider"],
                "warnings": page["warnings"], "images": page["images"],
            })
        except Exception as e:  # 한 건 실패로 배치 전체가 멈추지 않게
            log.error("[batch] %d번 상세 생성 실패: %s", i, e)
            results.append({"index": i, "name": spec.get("name", ""),
                            "path": None, "error": str(e)})
    return results
