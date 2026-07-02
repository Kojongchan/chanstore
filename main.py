#!/usr/bin/env python3
"""chanstore 통합 CLI — 위탁판매 도구 (수집 · 분석 · AI 상세페이지 · AI CS).

서브커맨드:
  collect  키워드 → 여러 마켓에서 상품 수집 → 엑셀 + SQLite
  analyze  수집 DB 분석(가격분포·마진역산·핫딜·경쟁강도)
  detail   상품 스펙(JSON) → AI 상세페이지 HTML
  cs       CS 문의(텍스트/JSON) → 답변 초안(사람 검수용)

예:
  python main.py collect 햇반 즉석밥 --sources 11st,naver --pages 2
  python main.py analyze --db output/chanstore.db --keyword 햇반 --sourcing-cost 15000
  python main.py detail --input product.json --market naver --outdir output
  python main.py cs --text "배송 언제 오나요?"

제약(PROJECT.md / PLATFORM_PLAN.md):
- 가격 등 '사실 데이터'만 수집. 이미지 URL은 참고용까지만.
- 원가는 크롤링 값이 아니라 --sourcing-cost 로 넣는 소싱처 기준값.
- AI 상세/CS는 초안까지. 발송·게시는 사람이 검수 후.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from src.schema import Product
from src.sources import SOURCE_CODES, SourceError, build_source
from src.storage import Database, save_xlsx

log = logging.getLogger("chanstore")


# ------------------------------------------------------------------ collect
def cmd_collect(args: argparse.Namespace) -> int:
    codes = [c.strip() for c in args.sources.split(",") if c.strip()]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    db_path = outdir / "chanstore.db"

    # 소스 인스턴스 준비(키 없는 소스는 건너뜀)
    sources = []
    for code in codes:
        try:
            sources.append(build_source(
                code, page_size=args.page_size, delay=args.delay))
        except SourceError as e:
            log.warning("[skip] 소스 '%s' 사용 불가: %s", code, e)
    if not sources:
        log.error("사용 가능한 소스가 없습니다. (키 설정 또는 --sources 확인)")
        return 2

    total = inserted = updated = 0
    with Database(db_path) as db:
        for keyword in args.keywords:
            kw_products: list[Product] = []
            for src in sources:
                log.info("=== '%s' @ %s (pages=%d) ===", keyword, src.name, args.pages)
                try:
                    kw_products.extend(src.search(keyword, pages=args.pages))
                except SourceError as e:
                    log.error("[실패] %s/'%s': %s", src.name, keyword, e)
                except Exception as e:  # 크롤러 등 예기치 못한 오류로 파이프라인이 죽지 않게
                    log.error("[오류] %s/'%s': %s", src.name, keyword, e)

            if not kw_products:
                log.warning("[결과없음] '%s'", keyword)
                continue

            safe = "".join(c for c in keyword if c.isalnum() or c in " _-").strip()
            xlsx = outdir / f"결과_{safe}_{date.today():%Y%m%d}.xlsx"
            save_xlsx(kw_products, xlsx)
            ins, upd = db.upsert_many(kw_products)
            total += len(kw_products)
            inserted += ins
            updated += upd
            log.info("[완료] '%s': %d건 → %s | DB 신규 %d/갱신 %d",
                     keyword, len(kw_products), xlsx.name, ins, upd)
        db_total = db.count()

    log.info("\n===== 수집 요약 =====")
    log.info("총 수집 %d건 (신규 %d/갱신 %d) | DB 누적 %d (%s)",
             total, inserted, updated, db_total, db_path)
    return 0 if total else 1


# ------------------------------------------------------------------ analyze
def cmd_analyze(args: argparse.Namespace) -> int:
    from src.analysis import analyze_keyword

    db_path = Path(args.db)
    if not db_path.exists():
        log.error("DB 없음: %s (먼저 collect 하세요)", db_path)
        return 2
    with Database(db_path) as db:
        products = db.fetch(args.keyword)
    if not products:
        log.error("분석할 데이터가 없습니다. (keyword=%r)", args.keyword)
        return 1

    report = analyze_keyword(
        products, keyword=args.keyword or "(전체)",
        sourcing_cost=args.sourcing_cost, target_price=args.target_price,
        market=args.market,
    )
    d = report.to_dict()
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0

    s = d["stats"]
    print(f"\n[분석] '{d['keyword']}'  (표본 {s['count']}건)")
    if s["count"]:
        print(f"  가격 최저 {s['min']:,} / 중앙 {s['median']:,} / 평균 {s['mean']:,} / 최고 {s['max']:,}원")
    c = d["competition"]
    print(f"  경쟁강도: {c['level']} (상품 {c['listings']} / 판매자 {c['sellers']} / "
          f"최다셀러점유 {c['seller_concentration']:.0%})")
    if d["distribution"]:
        print("  가격분포:")
        for b in d["distribution"]:
            bar = "█" * b["count"]
            print(f"    {b['low']:>8,}~{b['high']:>8,}원 | {bar} {b['count']}")
    if d["hot_deals"]:
        print(f"  핫딜 후보 {len(d['hot_deals'])}건(중앙값 대비 저가):")
        for h in d["hot_deals"][:5]:
            price = f"{h['price']:,}" if h["price"] else "?"
            print(f"    - {price}원  {h['name'][:40]}  [{h['source']}]")
    if d["margin"]:
        m = d["margin"]
        rate = f"{m['margin_rate']:.1%}" if m["margin_rate"] is not None else "-"
        print(f"  마진(원가 {m['cost']:,} 기준, 판매가 {m['revenue']:,}): "
              f"수수료 {m['fee']:,} + 부가세 {m['vat']:,} + 배송 {m['shipping']:,} → "
              f"마진 {m['margin']:,}원 ({rate})")
    else:
        print("  마진: --sourcing-cost 를 주면 마진을 역산합니다 (원가는 소싱처 기준 입력값).")
    return 0


# ------------------------------------------------------------------ detail
def cmd_detail(args: argparse.Namespace) -> int:
    from src.ai import build_detail_page, export_for_market

    spec = _load_spec(args)
    if spec is None:
        return 2
    page = build_detail_page(spec, with_images=not args.no_images)
    exported = export_for_market(page, args.market)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    name = "".join(c for c in str(spec.get("name", "detail")) if c.isalnum() or c in " _-").strip() or "detail"
    html_path = outdir / f"상세_{name}.html"
    html_path.write_text(exported["html"], encoding="utf-8")

    print(f"[완료] 상세페이지 → {html_path}  (마켓: {exported['label']}, 생성: {page['copy']['provider']})")
    if page["warnings"]:
        print("  ⚠ 광고문구 검토필요:")
        for w in page["warnings"]:
            print(f"    - '{w['phrase']}' : {w['reason']}")
    img_note = ", ".join(f"{i['provider']}({'생성' if i['available'] else '자리표시'})"
                         for i in page["images"])
    if img_note:
        print(f"  이미지: {img_note}")
    return 0


# ------------------------------------------------------------------ cs
def cmd_cs(args: argparse.Namespace) -> int:
    from src.cs import Inquiry, KnowledgeBase, draft_reply

    if args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        inq = Inquiry(
            text=data.get("text", ""), channel=data.get("channel", "unknown"),
            author=data.get("author", ""), order_id=data.get("order_id"),
            product=data.get("product"),
        )
    elif args.text:
        inq = Inquiry(text=args.text, channel=args.channel)
    else:
        log.error("--text 또는 --input 중 하나가 필요합니다.")
        return 2

    reply = draft_reply(inq, KnowledgeBase(store_name=args.store))
    d = reply.to_dict()
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    print(f"\n[의도] {d['intent']} (신뢰도 {d['confidence']})  | 생성: {d['provider']}")
    print(f"[초안]\n{d['draft']}")
    if d["needs_human"]:
        print("\n⚠ 사람 확인 후 발송 (자동발송 금지):")
        for r in d["reasons"]:
            print(f"  - {r}")
    else:
        print("\n(자동 위험요소는 감지되지 않았으나, 발송 전 검수를 권장합니다.)")
    return 0


def _load_spec(args: argparse.Namespace) -> dict | None:
    if not args.input:
        log.error("--input 상품 스펙 JSON 파일이 필요합니다.")
        return None
    path = Path(args.input)
    if not path.exists():
        log.error("파일 없음: %s", path)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.error("JSON 파싱 실패: %s", e)
        return None


# ------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chanstore", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true", help="상세 로그")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("collect", help="여러 마켓에서 상품 수집")
    c.add_argument("keywords", nargs="+", help="검색 키워드(1개 이상)")
    c.add_argument("--sources", default="11st,naver",
                   help=f"수집 소스(쉼표). 가능: {','.join(SOURCE_CODES)} (기본 11st,naver)")
    c.add_argument("--pages", type=int, default=2)
    c.add_argument("--page-size", type=int, default=40)
    c.add_argument("--delay", type=float, default=0.5)
    c.add_argument("--outdir", default="output")
    c.set_defaults(func=cmd_collect)

    a = sub.add_parser("analyze", help="수집 DB 분석")
    a.add_argument("--db", default="output/chanstore.db")
    a.add_argument("--keyword", default=None, help="특정 키워드만(미지정 시 전체)")
    a.add_argument("--sourcing-cost", type=int, default=None,
                   help="매입원가(소싱처 기준). 주면 마진 역산")
    a.add_argument("--target-price", type=int, default=None, help="가정 판매가(미지정 시 중앙값)")
    a.add_argument("--market", default="_default", help="수수료율 기준 마켓")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_analyze)

    d = sub.add_parser("detail", help="AI 상세페이지 생성")
    d.add_argument("--input", required=True, help="상품 스펙 JSON")
    d.add_argument("--market", default="_default")
    d.add_argument("--outdir", default="output")
    d.add_argument("--no-images", action="store_true", help="이미지 생성 생략")
    d.set_defaults(func=cmd_detail)

    s = sub.add_parser("cs", help="AI CS 답변 초안")
    s.add_argument("--text", help="문의 텍스트")
    s.add_argument("--input", help="문의 JSON 파일")
    s.add_argument("--channel", default="unknown")
    s.add_argument("--store", default="우리 스토어")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_cs)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
