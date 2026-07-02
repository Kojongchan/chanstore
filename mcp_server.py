#!/usr/bin/env python3
"""chanstore MCP 서버 — AI 상세페이지·CS·분석 능력을 도구로 노출.

PLATFORM_PLAN.md §6: Claude/에이전트가 MCP 도구를 호출해 "상품 하나 넣으면 상세페이지
초안이 나온다"를 자동화한다. 이미지 생성(nano banana) 호출은 도구 내부에 캡슐화돼 있어
모델을 바꿔도 상위 흐름은 그대로다.

도구:
  - generate_copy(spec)                 : 상세페이지 카피 생성(+광고문구 검사)
  - generate_detail_image(prompt)       : nano banana 이미지 생성(없으면 플레이스홀더)
  - build_detail_page(spec, market)     : 카피+이미지 → 마켓별 상세 HTML
  - draft_cs_reply(text, ...)           : CS 답변 초안(human-in-the-loop)
  - analyze_products(db_path, keyword..): 저장된 데이터 분석 리포트

핵심 로직은 모두 아래 순수 함수(tool_*)에 있어 mcp 패키지 없이도 테스트/재사용 가능하다.
`python mcp_server.py` 로 실행하면 stdio MCP 서버가 뜬다(mcp 패키지 필요).
"""
from __future__ import annotations

import sys
from typing import Any, Optional

from src.ai import build_detail_page, export_for_market, generate_copy, ImageClient
from src.cs import Inquiry, KnowledgeBase, draft_reply
from src.analysis import analyze_keyword


# --- 순수 함수 코어 (MCP 래핑과 무관하게 직접 호출/테스트 가능) ---

def tool_generate_copy(spec: dict) -> dict:
    """상품 스펙 dict → 상세페이지 카피(dict). 광고문구 위반은 warnings에."""
    return generate_copy(spec).to_dict()


def tool_generate_detail_image(prompt: str, filename: str = "detail") -> dict:
    """프롬프트 → 이미지(nano banana). 키 없으면 플레이스홀더 결과."""
    res = ImageClient().generate(prompt, filename=filename)
    return {
        "provider": res.provider,
        "available": res.available,
        "path": res.path,
        "note": res.note,
        "placeholder_svg": res.placeholder_svg if not res.available else "",
    }


def tool_build_detail_page(spec: dict, market: str = "_default",
                           with_images: bool = True) -> dict:
    """상품 스펙 → 마켓별 상세 HTML + 메타(warnings/images)."""
    page = build_detail_page(spec, with_images=with_images)
    exported = export_for_market(page, market)
    return {
        "market": exported["market"],
        "label": exported["label"],
        "html": exported["html"],
        "warnings": page["warnings"],
        "images": page["images"],
        "copy": page["copy"],
    }


def tool_draft_cs_reply(text: str, *, channel: str = "unknown",
                        order_id: Optional[str] = None,
                        product: Optional[str] = None,
                        store_name: str = "우리 스토어") -> dict:
    """CS 문의 텍스트 → 답변 초안(dict). needs_human/reasons 포함."""
    inq = Inquiry(text=text, channel=channel, order_id=order_id, product=product)
    kb = KnowledgeBase(store_name=store_name)
    return draft_reply(inq, kb).to_dict()


def tool_analyze_products(db_path: str, keyword: Optional[str] = None,
                          sourcing_cost: Optional[int] = None,
                          target_price: Optional[int] = None,
                          market: str = "_default") -> dict:
    """저장된 수집 데이터를 읽어 분석 리포트(dict) 반환."""
    from src.storage import Database
    with Database(db_path) as db:
        products = db.fetch(keyword)
    report = analyze_keyword(
        products, keyword=keyword or "", sourcing_cost=sourcing_cost,
        target_price=target_price, market=market,
    )
    return report.to_dict()


# --- MCP 서버 등록 (mcp 패키지 있을 때만) ---

def build_mcp():
    from mcp.server.fastmcp import FastMCP  # type: ignore

    mcp = FastMCP("chanstore")

    @mcp.tool()
    def generate_copy_tool(spec: dict[str, Any]) -> dict:
        """상품 스펙으로 상세페이지 카피를 생성한다(과장광고 필터 포함)."""
        return tool_generate_copy(spec)

    @mcp.tool()
    def generate_detail_image_tool(prompt: str, filename: str = "detail") -> dict:
        """nano banana(Gemini)로 상세페이지 이미지를 생성한다. 키 없으면 플레이스홀더."""
        return tool_generate_detail_image(prompt, filename)

    @mcp.tool()
    def build_detail_page_tool(spec: dict[str, Any], market: str = "_default",
                               with_images: bool = True) -> dict:
        """상품 스펙으로 마켓별 상세 HTML을 조립한다."""
        return tool_build_detail_page(spec, market, with_images)

    @mcp.tool()
    def draft_cs_reply_tool(text: str, channel: str = "unknown",
                            order_id: str = "", product: str = "",
                            store_name: str = "우리 스토어") -> dict:
        """CS 문의에 대한 답변 초안을 만든다(발송은 사람이)."""
        return tool_draft_cs_reply(text, channel=channel,
                                   order_id=order_id or None,
                                   product=product or None, store_name=store_name)

    @mcp.tool()
    def analyze_products_tool(db_path: str, keyword: str = "",
                              sourcing_cost: int = 0, target_price: int = 0,
                              market: str = "_default") -> dict:
        """수집 DB를 분석해 가격분포·마진·경쟁강도 리포트를 낸다."""
        return tool_analyze_products(
            db_path, keyword or None,
            sourcing_cost or None, target_price or None, market)

    return mcp


def main() -> int:
    try:
        mcp = build_mcp()
    except ImportError:
        print(
            "[안내] MCP 서버를 실행하려면 mcp 패키지가 필요합니다:\n"
            "  pip install mcp\n"
            "핵심 도구 함수(tool_*)는 mcp 없이도 import 해서 직접 쓸 수 있습니다.",
            file=sys.stderr,
        )
        return 2
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
