# chanstore — 위탁판매 시장조사·소싱판단 도구

국내 오픈마켓의 **공개 상품 데이터(가격·리뷰수 등 사실 정보)**를 수집·분석하여,
국내 위탁판매의 **소싱·가격 판단**을 돕는 도구입니다.

전체 노선/제약/로드맵은 [`PROJECT.md`](./PROJECT.md)를 기준으로 합니다.
데이터수집·AI 상세페이지·AI CS를 아우르는 **플랫폼 전체 기획**은 [`PLATFORM_PLAN.md`](./PLATFORM_PLAN.md)를 참고하세요.

> **이 저장소의 현재 범위는 1단계 — 11번가 공식 오픈API(ProductSearch) 수집기**입니다.
> 키워드 → 상품 목록 → 엑셀(.xlsx) + SQLite 저장까지 동작합니다.

---

## 빠른 시작

### 1) 의존성 설치
```bash
pip install -r requirements.txt
```

### 2) API 키 설정
11번가 판매자 계정에서 오픈API 키를 발급한 뒤:
```bash
cp .env.example .env
# .env 의 ELEVENST_API_KEY= 뒤에 발급받은 키 입력
```

### 3) 실행
```bash
python main.py 햇반                 # '햇반' 2페이지 수집
python main.py 햇반 즉석밥 --pages 3 # 키워드 여러 개, 3페이지씩
python main.py 햇반 --outdir output # 저장 폴더 지정
```

### 결과물
- `output/결과_<키워드>_<날짜>.xlsx` — 키워드별 엑셀
- `output/chanstore.db` — SQLite 누적 DB (중복은 자동 UPSERT)

---

## CLI 옵션
| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `keywords` | (필수) | 검색 키워드 1개 이상 |
| `--pages` | 2 | 키워드당 수집 페이지 수 |
| `--page-size` | 40 | 페이지당 상품 수 |
| `--delay` | 0.5 | 호출 간 딜레이(초) |
| `--outdir` | output | 결과 저장 폴더 |
| `-v, --verbose` | - | 상세 로그 |

---

## 수집 필드
상품명 · 판매가 · 이미지URL · 상품URL · 판매자 · 리뷰수 · 평점 · 카테고리 · 순위 · 배송 · 수집시각

> ⚠️ **이미지 정책**: 이미지 URL은 **분석 참고용**으로만 저장합니다.
> 다운로드·재가공·판매용 재사용은 하지 않습니다 (PROJECT.md 2-1).

---

## 프로젝트 구조
```
chanstore/
├── main.py                 # CLI 진입점 (수집 → 정규화 → 저장 파이프라인)
├── src/
│   ├── schema.py           # 공통 데이터 스키마 (Product dataclass) — 모든 소스 공유
│   ├── config.py           # .env 키 로딩
│   ├── sources/
│   │   ├── base.py         # 소스 공통 인터페이스 (BaseSource)
│   │   └── elevenst.py     # 11번가 API 모듈 (EUC-KR/CP949 처리 포함)
│   └── storage/
│       ├── database.py     # SQLite 저장 (복합키 UPSERT 중복처리)
│       └── excel.py        # xlsx 저장
└── tests/
    └── test_elevenst.py    # 인코딩 파싱 / 중복처리 테스트 (네트워크 불필요)
```

설계 원칙: **소스별 모듈 독립**. 2단계 네이버, 5단계 크롤러는 `BaseSource`를 상속해
`search()`만 구현하면 동일 파이프라인에 끼워집니다. 하나가 깨져도 나머지는 동작합니다.

---

## 테스트
```bash
python tests/test_elevenst.py        # 단독 실행
# 또는
pytest tests/                        # pytest 사용 시
```

---

## 로드맵 (PROJECT.md)
- [x] **1단계** — 11번가 공식 API 수집기
- [ ] 2단계 — 네이버 쇼핑 API 추가
- [ ] 3단계 — 분석 레이어 (가격분포·마진역산·핫딜·경쟁강도)
- [ ] 4단계 — AI 텍스트 가공 모듈
- [ ] 5단계 — 지마켓·옥션 크롤링
