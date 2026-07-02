"""데모 샘플 데이터 시더 — 키 없이 대시보드/소싱/추적을 바로 체험.

`python main.py demo` 로 실행하면 여러 마켓·키워드의 가짜 상품과 2회분 가격 스냅샷
(일부 가격 하락 포함)을 DB에 넣는다. 실제 수집 데이터가 아님을 이름에 표시한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .schema import Product
from .storage import Database

# (source, product_code, keyword, name, 이전가, 현재가, seller)
_SAMPLE = [
    ("naver", "n-hb1", "햇반", "[샘플] CJ 햇반 210g 24개입 무료배송", 22000, 20000, "최저가몰"),
    ("11st", "e-hb1", "햇반", "[샘플] CJ 햇반 210g 24개", 25000, 25000, "11번가샵"),
    ("gmarket", "g-hb1", "햇반", "[샘플] CJ 햇반 210g 24개입", 30000, 28000, "지마켓셀러"),
    ("naver", "n-hb2", "햇반", "[샘플] 오뚜기 맛있는밥 210g 12개", 13000, 12000, "오뚜기몰"),
    ("naver", "n-tb1", "텀블러", "[샘플] 스테인리스 텀블러 500ml 블랙", 15900, 13900, "리빙샵"),
    ("11st", "e-tb1", "텀블러", "[샘플] 진공 보온 텀블러 500ml", 16900, 16900, "굿즈몰"),
    ("gmarket", "g-tb1", "텀블러", "[샘플] 스테인리스 텀블러 500ml", 18000, 14500, "텀블러천국"),
    ("auction", "a-tb1", "텀블러", "[샘플] 대용량 보온보냉 텀블러 500ml", 17000, 17000, "옥션스토어"),
]


def seed(db_path: str | Path) -> dict:
    """샘플 상품 + 2회 가격 스냅샷을 적재. 요약 dict 반환."""
    now = datetime.now(timezone.utc)
    prev_ts = (now - timedelta(days=1)).isoformat()
    cur_ts = now.isoformat()

    prev_products, cur_products = [], []
    for i, (src, code, kw, name, old, new, seller) in enumerate(_SAMPLE, start=1):
        base = dict(source=src, product_code=code, keyword=kw, name=name,
                    seller=seller, rank=i, review_count=100 + i)
        prev_products.append(Product(price=old, **base))
        cur_products.append(Product(price=new, **base))

    with Database(db_path) as db:
        # 현재 상태를 products 에 upsert
        db.upsert_many(cur_products)
        # 어제/오늘 두 스냅샷을 이력에 적재(추적 데모용)
        db.snapshot_prices(prev_products, snapshot_at=prev_ts)
        db.snapshot_prices(cur_products, snapshot_at=cur_ts)
        total = db.count()

    return {"products": len(cur_products), "snapshots": 2, "db_total": total}
