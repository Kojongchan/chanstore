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
    source        TEXT NOT NULL,
    product_code  TEXT NOT NULL,
    keyword       TEXT,
    name          TEXT,
    price         INTEGER,
    image_url     TEXT,
    product_url   TEXT,
    seller        TEXT,
    review_count  INTEGER,
    rating        REAL,
    category      TEXT,
    rank          INTEGER,
    delivery      TEXT,
    collected_at  TEXT,
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
        update_set = ", ".join(f"{c}=excluded.{c}" for c in update_cols)
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

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
