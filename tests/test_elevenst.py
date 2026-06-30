"""11번가 파서 / 저장 로직 테스트 (네트워크·API 키 불필요).

핵심 검증: EUC-KR/CP949 인코딩 응답에서 한글이 깨지지 않고 파싱되는가.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sources.elevenst import ElevenStSource, _decode_xml, _to_int  # noqa: E402
from src.storage import Database  # noqa: E402

# 실제 11번가 응답과 유사한 형태 (EUC-KR 선언 + 한글)
SAMPLE_XML = """<?xml version="1.0" encoding="EUC-KR"?>
<ProductSearchResponse>
  <Products>
    <Product>
      <ProductCode>1234567890</ProductCode>
      <ProductName>CJ 햇반 즉석밥 210g 24개</ProductName>
      <ProductPrice>23,900</ProductPrice>
      <ProductImage>http://example.com/img/a.jpg</ProductImage>
      <DetailPageUrl>http://example.com/products/1234567890</DetailPageUrl>
      <Seller>CJ제일제당</Seller>
      <ReviewCount>1,532</ReviewCount>
      <Rating>4.8</Rating>
      <CategoryName>식품/즉석밥</CategoryName>
      <Delivery>무료배송</Delivery>
    </Product>
    <Product>
      <ProductCode>9876543210</ProductCode>
      <ProductName>오뚜기 맛있는 밥 210g 12개입</ProductName>
      <ProductPrice>12900</ProductPrice>
      <ProductImage>http://example.com/img/b.jpg</ProductImage>
      <DetailPageUrl>http://example.com/products/9876543210</DetailPageUrl>
      <Seller>오뚜기몰</Seller>
      <ReviewCount>842</ReviewCount>
    </Product>
  </Products>
  <TotalCount>2</TotalCount>
</ProductSearchResponse>
"""

SAMPLE_BYTES = SAMPLE_XML.encode("cp949")  # EUC-KR/CP949 로 인코딩된 실제 바이트


def test_decode_xml_handles_euckr():
    text = _decode_xml(SAMPLE_BYTES)
    assert "햇반" in text                       # 한글 깨짐 없음
    assert "<?xml" not in text                  # XML 선언(encoding) 제거됨


def test_parse_extracts_fields():
    src = ElevenStSource(api_key="dummy")
    products = src._parse(SAMPLE_BYTES, keyword="햇반")

    assert len(products) == 2

    p = products[0]
    assert p.source == "11st"
    assert p.product_code == "1234567890"
    assert p.name == "CJ 햇반 즉석밥 210g 24개"
    assert p.price == 23900                      # '23,900' → 23900
    assert p.review_count == 1532                # '1,532' → 1532
    assert p.rating == 4.8
    assert p.seller == "CJ제일제당"
    assert p.category == "식품/즉석밥"
    assert p.image_url == "http://example.com/img/a.jpg"
    assert p.keyword == "햇반"


def test_to_int():
    assert _to_int("23,900원") == 23900
    assert _to_int("12900") == 12900
    assert _to_int("") is None
    assert _to_int("없음") is None


def test_dedup_upsert(tmp_path):
    src = ElevenStSource(api_key="dummy")
    products = src._parse(SAMPLE_BYTES, keyword="햇반")

    db_path = tmp_path / "test.db"
    with Database(db_path) as db:
        ins, upd = db.upsert_many(products)
        assert (ins, upd) == (2, 0)
        assert db.count() == 2

        # 동일 상품 재삽입 → 갱신만, 레코드 수 불변
        ins2, upd2 = db.upsert_many(products)
        assert (ins2, upd2) == (0, 2)
        assert db.count() == 2


if __name__ == "__main__":
    test_decode_xml_handles_euckr()
    test_parse_extracts_fields()
    test_to_int()
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        test_dedup_upsert(Path(d))
    print("모든 테스트 통과 ✅")
