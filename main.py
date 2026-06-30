#!/usr/bin/env python3
"""위탁판매 시장조사 도구 — 1단계 CLI (11번가 공식 API 수집기).

사용 예:
    python main.py 햇반
    python main.py 햇반 즉석밥 --pages 3
    python main.py 햇반 --pages 2 --outdir output

키워드를 입력하면 11번가 공개 API(ProductSearch)로 상품 목록을 받아
  - 결과_<키워드>_<날짜>.xlsx
  - chanstore.db (SQLite, 중복 자동 처리)
에 저장한다.

제약(PROJECT.md): 가격·리뷰수 등 '사실 데이터' 수집 전용. 이미지 URL은 참고용 표시까지만.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from src.config import get_elevenst_api_key
from src.schema import Product
from src.sources import ElevenStSource, SourceError
from src.storage import Database, save_xlsx

KEY_GUIDE = """\
[안내] 11번가 오픈API 키가 설정되지 않았습니다.

  1) 11번가 판매자 계정 로그인 → 오픈API 서비스 등록 → 키 발급
  2) 프로젝트 루트에서:  cp .env.example .env
  3) .env 파일의 ELEVENST_API_KEY= 뒤에 발급받은 키를 입력

키 없이는 수집을 진행할 수 없습니다.
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="chanstore",
        description="11번가 공식 API로 키워드 상품을 수집해 엑셀+SQLite로 저장",
    )
    p.add_argument("keywords", nargs="+", help="검색 키워드 (1개 이상)")
    p.add_argument("--pages", type=int, default=2, help="키워드당 수집 페이지 수 (기본 2)")
    p.add_argument("--page-size", type=int, default=40, help="페이지당 상품 수 (기본 40)")
    p.add_argument("--delay", type=float, default=0.5, help="호출 간 딜레이(초, 기본 0.5)")
    p.add_argument("--outdir", default="output", help="결과 저장 폴더 (기본 output)")
    p.add_argument("-v", "--verbose", action="store_true", help="상세 로그")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    log = logging.getLogger("chanstore")

    api_key = get_elevenst_api_key()
    if not api_key:
        print(KEY_GUIDE, file=sys.stderr)
        return 2

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    db_path = outdir / "chanstore.db"

    source = ElevenStSource(
        api_key,
        page_size=args.page_size,
        delay=args.delay,
    )

    total_collected = 0
    total_inserted = 0
    total_updated = 0
    failed_keywords: list[str] = []

    with Database(db_path) as db:
        for keyword in args.keywords:
            log.info("\n=== '%s' 수집 시작 (pages=%d) ===", keyword, args.pages)
            try:
                products: list[Product] = list(
                    source.search(keyword, pages=args.pages)
                )
            except SourceError as e:
                log.error("[실패] '%s': %s", keyword, e)
                failed_keywords.append(keyword)
                continue

            if not products:
                log.warning("[결과없음] '%s': 수집된 상품이 없습니다.", keyword)
                continue

            # 엑셀: 키워드별 파일
            safe_kw = "".join(c for c in keyword if c.isalnum() or c in " _-").strip()
            xlsx_path = outdir / f"결과_{safe_kw}_{date.today():%Y%m%d}.xlsx"
            save_xlsx(products, xlsx_path)

            # SQLite: 누적 (중복 UPSERT)
            inserted, updated = db.upsert_many(products)

            total_collected += len(products)
            total_inserted += inserted
            total_updated += updated
            log.info(
                "[완료] '%s': %d건 수집 → 엑셀 %s | DB 신규 %d, 갱신 %d",
                keyword, len(products), xlsx_path.name, inserted, updated,
            )

        db_total = db.count()

    # 최종 요약
    log.info("\n========== 수집 요약 ==========")
    log.info("총 수집: %d건 (DB 신규 %d, 갱신 %d)", total_collected, total_inserted, total_updated)
    log.info("DB 누적 레코드: %d건  (%s)", db_total, db_path)
    if failed_keywords:
        log.warning("실패한 키워드: %s", ", ".join(failed_keywords))

    return 0 if total_collected > 0 or not failed_keywords else 1


if __name__ == "__main__":
    raise SystemExit(main())
