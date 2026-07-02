"""상세페이지 조립: 카피 + 이미지 → 마켓용 HTML.

흐름(PLATFORM_PLAN.md §6):
  상품 스펙 → generate_copy(LLM/템플릿) → 이미지(nano banana/placeholder) → HTML 조립
  → export_for_market(마켓별 규격 어댑터)

- 광고문구 위반은 고객용 HTML에는 노출하지 않고, 반환 메타(warnings)로만 운영자에게 보고한다.
- 이미지가 실제 생성 안 됐으면 인라인 SVG 플레이스홀더로 자리표시 → 페이지가 항상 완성된다.
"""
from __future__ import annotations

import html
from typing import Optional

from .copy import DetailCopy, generate_copy
from .image import ImageClient, ImageResult
from .llm import LLMClient

# 마켓별 상세페이지 대략 규격(권장 폭 등). 실제 정책은 마켓 가이드 확인 필요.
MARKET_SPECS: dict[str, dict] = {
    "11st": {"max_width": 780, "label": "11번가"},
    "naver": {"max_width": 860, "label": "스마트스토어"},
    "gmarket": {"max_width": 860, "label": "지마켓"},
    "auction": {"max_width": 860, "label": "옥션"},
    "_default": {"max_width": 800, "label": "일반"},
}


def _img_tag(img: ImageResult, alt: str) -> str:
    alt_e = html.escape(alt)
    if img.available and img.path:
        return f'<img src="{html.escape(img.path)}" alt="{alt_e}" style="max-width:100%;height:auto;">'
    # 플레이스홀더 SVG 인라인
    return f'<figure class="ph" aria-label="{alt_e}">{img.placeholder_svg}</figure>'


def build_detail_page(
    spec: dict,
    *,
    copy: Optional[DetailCopy] = None,
    llm: Optional[LLMClient] = None,
    image_client: Optional[ImageClient] = None,
    with_images: bool = True,
) -> dict:
    """상세페이지 HTML과 메타데이터를 만든다.

    반환: {html, copy(dict), warnings(list), images(list of dict)}
    """
    dc = copy or generate_copy(spec, llm=llm)
    imgs: list[ImageResult] = []
    if with_images:
        ic = image_client or ImageClient()
        # 히어로 1컷 + 셀링포인트 인포그래픽 1컷 (스펙 기반 프롬프트, 신규 생성)
        hero_prompt = f"{dc.title} 상품 대표 연출컷, 깔끔한 배경, 스튜디오 조명"
        imgs.append(ic.generate(hero_prompt, filename="hero"))
        if dc.bullets:
            info_prompt = f"{dc.title} 핵심 특징 인포그래픽: " + " / ".join(dc.bullets[:3])
            imgs.append(ic.generate(info_prompt, filename="features"))

    page_html = _render_html(dc, imgs)
    return {
        "html": page_html,
        "copy": dc.to_dict(),
        "warnings": [{"phrase": w.phrase, "reason": w.reason} for w in dc.warnings],
        "images": [
            {"provider": i.provider, "available": i.available, "path": i.path, "note": i.note}
            for i in imgs
        ],
    }


def _render_html(dc: DetailCopy, imgs: list[ImageResult]) -> str:
    title = html.escape(dc.title)
    subtitle = html.escape(dc.subtitle)
    bullets = "".join(f"<li>{html.escape(b)}</li>" for b in dc.bullets)
    spec_rows = "".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
        for k, v in dc.spec_rows
    )
    notice = html.escape(dc.notice).replace("\n", "<br>")
    hero = _img_tag(imgs[0], dc.title) if imgs else ""
    info = _img_tag(imgs[1], f"{dc.title} 특징") if len(imgs) > 1 else ""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  .detail {{ font-family: -apple-system, "Noto Sans KR", sans-serif; color:#222;
             max-width:860px; margin:0 auto; line-height:1.6; }}
  .detail h1 {{ font-size:26px; margin:16px 0 4px; }}
  .detail .sub {{ color:#666; margin:0 0 20px; }}
  .detail img, .detail .ph svg {{ width:100%; height:auto; border-radius:8px; margin:12px 0; }}
  .detail ul {{ padding-left:20px; }}
  .detail table {{ width:100%; border-collapse:collapse; margin:16px 0; }}
  .detail th, .detail td {{ border:1px solid #eee; padding:10px 12px; text-align:left; font-size:14px; }}
  .detail th {{ background:#faf9f5; width:32%; }}
  .detail .notice {{ background:#faf9f5; padding:14px 16px; border-radius:8px;
                     font-size:13px; color:#555; }}
</style></head>
<body><article class="detail">
  <h1>{title}</h1>
  {'<p class="sub">' + subtitle + '</p>' if subtitle else ''}
  {hero}
  <ul>{bullets}</ul>
  {info}
  {'<table><tbody>' + spec_rows + '</tbody></table>' if spec_rows else ''}
  <div class="notice">{notice}</div>
</article></body></html>"""


def export_for_market(page: dict, market: str = "_default") -> dict:
    """조립된 페이지를 마켓별 규격에 맞춰 감싸 반환.

    반환: {market, label, html, max_width, image_notes}
    실제 업로드 규격(이미지 용량/태그 제한)은 마켓 가이드에 따라 추가 조정 필요.
    """
    spec = MARKET_SPECS.get(market, MARKET_SPECS["_default"])
    wrapped = page["html"].replace(
        "max-width:860px", f"max-width:{spec['max_width']}px"
    )
    return {
        "market": market,
        "label": spec["label"],
        "max_width": spec["max_width"],
        "html": wrapped,
        "image_notes": page.get("images", []),
    }
