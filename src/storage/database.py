"""SQLite 저장. (source, product_code) 복합키로 중복(UPSERT) 처리."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from ..schema import COLUMNS, Product

TABLE = "products"

# dedup_key = source + product_code → PRIMARY KEY 로 중복 방지
_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    source            TEXT NOT NULL,
    product_code      TEXT NOT NULL,
    keyword           TEXT,
    name              TEXT,
    price             INTEGER,
    list_price        INTEGER,
    sale_price        INTEGER,
    coupon_price      INTEGER,
    shipping_fee      INTEGER,
    sourcing_cost     INTEGER,
    estimated_margin  INTEGER,
    image_url         TEXT,
    image_path        TEXT,
    product_url       TEXT,
    seller            TEXT,
    review_count      INTEGER,
    rating            REAL,
    category          TEXT,
    rank              INTEGER,
    delivery          TEXT,
    collected_at      TEXT,
    PRIMARY KEY (source, product_code)
);
"""


class Database:
    """간단한 SQLite 래퍼. with 문으로 사용."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute(_CREATE_SQL)
        self.conn.commit()

    def upsert_many(self, products: Iterable[Product]) -> tuple[int, int]:
        """상품들을 UPSERT. (신규삽입수, 갱신수) 반환."""
        cols = ", ".join(COLUMNS)
        placeholders = ", ".join("?" for _ in COLUMNS)
        update_cols = [c for c in COLUMNS if c not in ("source", "product_code")]
        # 재수집 시 갱신 규칙:
        # - sourcing_cost/estimated_margin 은 수집 소스가 채우지 않는 '판단용' 값이므로,
        #   새 값이 NULL이면 기존 값을 보존한다(수동 입력/분석 결과가 날아가지 않도록).
        # - 나머지 사실 데이터는 최신 수집값으로 덮어쓴다.
        _preserve = {"sourcing_cost", "estimated_margin"}
        update_set = ", ".join(
            (f"{c}=COALESCE(excluded.{c}, {TABLE}.{c})" if c in _preserve
             else f"{c}=excluded.{c}")
            for c in update_cols
        )
        sql = (
            f"INSERT INTO {TABLE} ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(source, product_code) DO UPDATE SET {update_set}"
        )

        inserted = updated = 0
        cur = self.conn.cursor()
        for p in products:
            row = p.to_row()
            existed = cur.execute(
                f"SELECT 1 FROM {TABLE} WHERE source=? AND product_code=?",
                (p.source, p.product_code),
            ).fetchone()
            cur.execute(sql, [row[c] for c in COLUMNS])
            if existed:
                updated += 1
            else:
                inserted += 1
        self.conn.commit()
        return inserted, updated

    def count(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]

    def stats(self) -> dict:
        """대시보드용 요약: 총계, 소스별/키워드별 건수."""
        cur = self.conn.cursor()
        total = cur.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
        by_source = dict(cur.execute(
            f"SELECT source, COUNT(*) FROM {TABLE} GROUP BY source ORDER BY 2 DESC"
        ).fetchall())
        by_keyword = dict(cur.execute(
            f"SELECT keyword, COUNT(*) FROM {TABLE} GROUP BY keyword ORDER BY 2 DESC"
        ).fetchall())
        return {"total": total, "by_source": by_source, "by_keyword": by_keyword}

    def keywords(self) -> list[str]:
        rows = self.conn.execute(
            f"SELECT DISTINCT keyword FROM {TABLE} ORDER BY keyword"
        ).fetchall()
        return [r[0] for r in rows if r[0]]

    def fetch(self, keyword: str | None = None) -> list[Product]:
        """저장된 상품을 Product 리스트로 읽는다(분석 레이어용). keyword로 필터 가능."""
        cols = ", ".join(COLUMNS)
        if keyword:
            rows = self.conn.execute(
                f"SELECT {cols} FROM {TABLE} WHERE keyword=?", (keyword,)
            ).fetchall()
        else:
            rows = self.conn.execute(f"SELECT {cols} FROM {TABLE}").fetchall()
        products: list[Product] = []
        for row in rows:
            data = dict(zip(COLUMNS, row))
            products.append(Product(**data))
        return products

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
