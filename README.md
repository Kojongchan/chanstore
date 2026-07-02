# chanstore — 위탁판매 도구 (수집 · 분석 · AI 상세페이지 · AI CS)

국내 오픈마켓의 **공개 상품 데이터**를 수집·분석하고, **AI로 상세페이지·CS를 반자동화**하는
위탁판매 운영 도구입니다.

- 전체 노선/제약/로드맵(수집 노선): [`PROJECT.md`](./PROJECT.md)
- 플랫폼 전체 기획(3대 기능·크롤링 주의·AI): [`PLATFORM_PLAN.md`](./PLATFORM_PLAN.md)

> 설계 철학: **공식 API 우선, 크롤링은 최소·예의바르게**, **AI는 초안까지·발송은 사람이**,
> **경쟁사 이미지는 참고용까지만·판매 이미지는 AI 신규 생성**. (자세한 근거는 PLATFORM_PLAN.md)

---

## 빠른 시작

```bash
pip install -r requirements.txt
cp .env.example .env      # 있는 키만 채우면 됨 (없으면 해당 기능은 폴백/스킵)
```

키가 하나도 없어도 `detail`/`cs`는 **오프라인 폴백**으로 동작합니다(템플릿 카피 + 플레이스홀더 이미지).

---

## CLI (`python main.py <서브커맨드>`)

> **키 없이 지금 체험:** `python main.py demo` → 샘플 데이터 적재 후 아래 명령이 바로 동작합니다.

### 1) collect — 여러 마켓에서 수집
```bash
python main.py collect 햇반 즉석밥 --sources 11st,naver --pages 2
python main.py collect 햇반 --sources 11st,naver --save-thumbs   # 메인 썸네일도 저장
```
- 소스: `11st`(API), `naver`(쇼핑 검색 API=스마트스토어 시세 우회), `gmarket`/`auction`(크롤링, 후순위)
- 키 없는 소스는 자동으로 건너뜁니다. 결과는 `output/결과_<키워드>_<날짜>.xlsx` + `output/chanstore.db`.
- `--save-thumbs`: 각 상품 **메인 썸네일을 내려받아** `output/ref_images/`(참고용)에 저장하고 `image_path`에 기록.
  판매용 이미지(`output/images/`, AI 생성)와 저장소를 분리합니다. 재사용은 별개(저작권) 판단.

### 2) analyze — 수집 데이터 분석
```bash
python main.py analyze --db output/chanstore.db --keyword 햇반 --sourcing-cost 15000 --market 11st
```
- 가격분포·경쟁강도·핫딜 후보를 출력하고, `--sourcing-cost`(소싱처 기준 **원가 입력값**)를 주면 마진을 역산합니다.
- ⚠ 원가는 오픈마켓에 공개되지 않으므로 크롤링 값이 아니라 **직접 입력**합니다(PLATFORM_PLAN.md §1-1).

### 2-b) track — 가격 변동 추적
```bash
python main.py track --db output/chanstore.db --keyword 텀블러
```
- collect 할 때마다 가격 스냅샷이 쌓입니다. 최신 vs 직전을 비교해 **하락/상승/신규**를 감지(하락 폭 큰 순).
- 키 나오면 매일 collect만 자동화하면 그대로 "가격 하락 알림"이 됩니다.

### 3) detail — AI 상세페이지 (단건/배치)
```bash
python main.py detail --input product.json --market naver --outdir output   # 단건
python main.py detail --input specs.json  --market naver                     # 배열이면 배치
```
`product.json` 예시:
```json
{"name":"스테인리스 텀블러 500ml","brand":"챈스토어",
 "features":["이중 진공 보온보냉","식기세척기 사용 가능"],
 "specs":{"용량":"500ml","재질":"스테인리스 304"}}
```
- 카피(LLM/템플릿) + 이미지(nano banana=Gemini/플레이스홀더) → 마켓별 상세 HTML.
- 과장·허위광고 표현은 자동 검출해 `검토필요`로 표시하고 경고를 출력합니다(표시광고법 리스크).

### 4) cs — AI CS 답변 초안
```bash
python main.py cs --text "환불해주세요"
```
- 의도 분류 → 스토어 정책 기반 초안. **환불/교환/클레임·개인정보·금액**이 걸리면 `needs_human` 플래그로
  자동발송을 막습니다(human-in-the-loop).

---

## 로컬 대시보드 (웹 UI)

CLI 대신 한 화면에서 수집현황·분석·소싱·상세페이지·CS를 씁니다. **키 없이도 전부 동작**합니다.
```bash
pip install fastapi uvicorn
python dashboard.py                                  # http://127.0.0.1:8000
CHANSTORE_DB=output/chanstore.db python dashboard.py # DB 경로 지정
```
- `/products` 수집 상품(썸네일 포함) · `/analyze` 가격분포·마진 · `/sourcing` 되팔기 기회
- `/detail` 상세페이지 생성 · `/cs` CS 초안 · `/thumb` 참고용 썸네일(경로 보안 처리)
- 렌더링 로직은 `src/web/views.py`(순수 함수)라 FastAPI 없이도 테스트됩니다.

---

## MCP 서버 (상세페이지·CS 자동화)

```bash
pip install mcp anthropic google-genai   # 선택
python mcp_server.py                       # stdio MCP 서버
```
노출 도구: `generate_copy` · `generate_detail_image`(nano banana) · `build_detail_page` ·
`draft_cs_reply` · `analyze_products`. 핵심 로직은 `mcp_server.py`의 `tool_*` 순수 함수라
mcp 없이도 import 해서 쓸 수 있습니다.

---

## 프로젝트 구조
```
chanstore/
├── main.py                 # 통합 CLI (collect/analyze/detail/cs)
├── mcp_server.py           # MCP 서버 + tool_* 순수 함수
├── src/
│   ├── schema.py           # 공통 Product 스키마(가격세부·원가·마진 필드 포함)
│   ├── config.py           # .env 키 로딩(11번가·네이버·Anthropic·Gemini)
│   ├── crawl/              # 매너 크롤링 코어
│   │   ├── ratelimit.py    #   도메인별 랜덤 지터 딜레이
│   │   ├── robots.py       #   robots.txt 준수
│   │   ├── breaker.py      #   서킷 브레이커(403/429/캡차 감지 시 중단)
│   │   └── fetcher.py      #   예의바른 HTTP 페처(재시도·백오프)
│   ├── sources/            # 소스별 독립 모듈 (하나 죽어도 나머지 동작)
│   │   ├── elevenst.py     #   11번가 API
│   │   ├── naver.py        #   네이버 쇼핑 검색 API
│   │   ├── gmarket.py / auction.py  # 크롤러(JSON-LD 우선 파싱)
│   │   └── crawler_base.py #   크롤러 공통 베이스
│   ├── analysis/metrics.py # 가격분포·마진역산·핫딜·경쟁강도
│   ├── ai/                 # 상세페이지: llm·image·compliance·copy·detail_page
│   ├── cs/                 # CS: classify·knowledge·draft (human-in-the-loop)
│   └── storage/            # SQLite + xlsx
└── tests/                  # 네트워크 없는 단위테스트
```

---

## 테스트
```bash
python -m pytest tests/          # 전체
python tests/test_analysis.py    # 개별 실행도 가능
```
모든 테스트는 네트워크·API 키 없이 동작합니다.

---

## 로드맵 (PLATFORM_PLAN.md §9)
- [x] 1단계 — 11번가 API 수집기
- [x] 2단계 — 네이버 쇼핑 API (스마트스토어 시세 포함)
- [x] 3단계 — 분석 레이어(가격분포·마진역산·핫딜·경쟁강도)
- [x] 4단계 — 지마켓·옥션 크롤러(매너 크롤링 규칙 적용)
- [x] 5단계 — AI 상세페이지 MCP(카피 + nano banana + 마켓별 export)
- [x] 6단계 — AI CS(human-in-the-loop)
- [x] 되팔기 소싱 분석 (동일상품 매칭 + 최저가 매입 + 마진) — `sourcing`
- [x] 로컬 대시보드 (`dashboard.py`)
- [x] 가격 변동 추적 (`track`) · 배치 상세페이지 (`detail` 배열) · 데모 시더 (`demo`)
- [ ] 키 필요 — 매일 자동수집·알림 발송 / 마켓 자동 업로드(판매자 API) / 리뷰 트렌드
