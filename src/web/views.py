"""대시보드 렌더링/데이터 함수 (순수 — FastAPI 비의존, 테스트 대상).

모든 사용자 데이터는 html.escape 로 이스케이프한다(XSS 방지).
자체 완결형: 외부 CSS/폰트/CDN 없이 인라인 스타일만 사용.
"""
from __future__ import annotations

import html
from typing import Optional, Sequence

from ..schema import Product

_STYLE = """
:root{--fg:#222;--muted:#777;--line:#ececec;--bg:#faf9f5;--accent:#2b6cb0}
*{box-sizing:border-box}
body{font-family:-apple-system,"Noto Sans KR",sans-serif;color:var(--fg);margin:0;line-height:1.55}
header{background:#1f2933;color:#fff;padding:14px 22px}
header a{color:#cfe3ff;text-decoration:none;margin-right:16px;font-size:14px}
header .brand{font-weight:700;font-size:18px;margin-right:24px}
main{max-width:1040px;margin:0 auto;padding:22px}
h1{font-size:22px;margin:6px 0 16px}
h2{font-size:17px;margin:22px 0 8px}
.card{border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0;background:#fff}
.stat{display:inline-block;background:var(--bg);border-radius:8px;padding:10px 16px;margin:4px 8px 4px 0}
.stat b{font-size:20px;display:block}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:13px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left}
th{background:var(--bg)}
.num{text-align:right;font-variant-numeric:tabular-nums}
form{margin:8px 0}
label{font-size:13px;color:var(--muted);display:inline-block;margin:4px 8px 4px 0}
input,select,textarea{font:inherit;padding:6px 8px;border:1px solid #ccc;border-radius:6px}
textarea{width:100%;min-height:80px}
button{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:8px 16px;cursor:pointer}
.pill{display:inline-block;background:#eef;border-radius:99px;padding:2px 10px;font-size:12px;margin:2px}
.warn{background:#fff7ed;border:1px solid #fdba74;border-radius:8px;padding:10px 12px;font-size:13px}
.ok{color:#256029}.bad{color:#a12}
.muted{color:var(--muted);font-size:13px}
"""

_NAV = (
    '<header><span class="brand">chanstore</span>'
    '<a href="/">홈</a><a href="/products">상품</a><a href="/analyze">분석</a>'
    '<a href="/sourcing">소싱</a><a href="/track">가격변동</a>'
    '<a href="/detail">상세페이지</a><a href="/cs">CS</a>'
    "</header>"
)


def page(title: str, body: str) -> str:
    return (
        f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)} · chanstore</title><style>{_STYLE}</style></head>"
        f"<body>{_NAV}<main>{body}</main></body></html>"
    )


def _won(v) -> str:
    return f"{v:,}" if isinstance(v, int) else "-"


# ------------------------------------------------------------------ 홈
def render_home(stats: dict) -> str:
    src = "".join(f'<span class="stat">{html.escape(k)}<b>{v:,}</b></span>'
                  for k, v in stats.get("by_source", {}).items()) or '<span class="muted">아직 수집 데이터가 없습니다.</span>'
    kws = "".join(f'<a class="pill" href="/analyze?keyword={html.escape(k)}">{html.escape(k)}</a>'
                  for k in list(stats.get("by_keyword", {}).keys())[:30])
    body = (
        "<h1>대시보드</h1>"
        f'<div class="card"><span class="stat">총 상품<b>{stats.get("total",0):,}</b></span>{src}</div>'
        f'<div class="card"><h2>수집 키워드</h2>{kws or "<span class=muted>없음</span>"}</div>'
        '<div class="card muted">수집은 CLI로: <code>python main.py collect &lt;키워드&gt; --save-thumbs</code>. '
        "API 키가 없어도 분석·소싱·상세·CS는 여기서 바로 됩니다.</div>"
    )
    return page("홈", body)


# ------------------------------------------------------------------ 상품
def render_products(products: Sequence[Product], *, keyword: str = "",
                    source: str = "", limit: int = 200) -> str:
    rows = []
    for p in products[:limit]:
        thumb = (f'<img src="/thumb?path={html.escape(p.image_path)}" style="height:40px">'
                 if p.image_path else "")
        url = (f'<a href="{html.escape(p.product_url)}" target="_blank" rel="noopener">열기</a>'
               if p.product_url else "")
        rows.append(
            f"<tr><td>{thumb}</td><td>{html.escape(p.name[:60])}</td>"
            f'<td>{html.escape(p.source)}</td><td class="num">{_won(p.price)}</td>'
            f"<td>{html.escape(p.seller[:16])}</td><td>{url}</td></tr>"
        )
    table = ("<table><thead><tr><th>썸네일</th><th>상품명</th><th>소스</th>"
             "<th class='num'>가격</th><th>판매자</th><th>링크</th></tr></thead>"
             f"<tbody>{''.join(rows) or '<tr><td colspan=6 class=muted>데이터 없음</td></tr>'}</tbody></table>")
    body = (
        "<h1>상품</h1>"
        f'<form method="get" action="/products"><label>키워드 <input name="keyword" value="{html.escape(keyword)}"></label>'
        f'<label>소스 <input name="source" value="{html.escape(source)}"></label>'
        "<button>조회</button></form>"
        f'<div class="card"><div class="muted">{len(products)}건 (최대 {limit} 표시)</div>{table}</div>'
    )
    return page("상품", body)


# ------------------------------------------------------------------ 분석
def render_analysis(report: Optional[dict], keyword: str) -> str:
    form = (
        f'<form method="get" action="/analyze">'
        f'<label>키워드 <input name="keyword" value="{html.escape(keyword)}"></label>'
        '<label>원가(소싱) <input name="sourcing_cost" type="number"></label>'
        '<label>되팔가 <input name="target_price" type="number"></label>'
        '<label>마켓 <input name="market" value="_default"></label>'
        "<button>분석</button></form>"
    )
    if not report:
        return page("분석", "<h1>분석</h1>" + form +
                    '<div class="card muted">키워드를 입력하고 분석을 눌러주세요.</div>')
    s = report["stats"]
    stat_html = (
        f'<span class="stat">표본<b>{s["count"]:,}</b></span>'
        f'<span class="stat">최저<b>{_won(s["min"])}</b></span>'
        f'<span class="stat">중앙<b>{_won(s["median"])}</b></span>'
        f'<span class="stat">평균<b>{_won(s["mean"])}</b></span>'
        f'<span class="stat">최고<b>{_won(s["max"])}</b></span>'
    )
    dist = "".join(
        f'<tr><td class="num">{_won(b["low"])}~{_won(b["high"])}</td>'
        f'<td>{"█"*b["count"]} {b["count"]}</td></tr>'
        for b in report["distribution"]
    )
    c = report["competition"]
    comp = (f'경쟁강도 <b>{html.escape(c["level"])}</b> · 상품 {c["listings"]} · '
            f'판매자 {c["sellers"]} · 최다셀러점유 {c["seller_concentration"]:.0%}')
    margin = ""
    if report.get("margin"):
        m = report["margin"]
        rate = f'{m["margin_rate"]:.1%}' if m["margin_rate"] is not None else "-"
        cls = "ok" if m["margin"] > 0 else "bad"
        margin = (f'<div class="card"><h2>마진(원가 {_won(m["cost"])} · 판매가 {_won(m["revenue"])})</h2>'
                  f'수수료 {_won(m["fee"])} + 부가세 {_won(m["vat"])} + 배송 {_won(m["shipping"])} → '
                  f'<span class="{cls}">마진 {_won(m["margin"])}원 ({rate})</span></div>')
    body = (
        f"<h1>분석 · {html.escape(report['keyword'])}</h1>" + form +
        f'<div class="card">{stat_html}<div class="muted" style="margin-top:8px">{comp}</div></div>'
        f'<div class="card"><h2>가격분포</h2><table>{dist}</table></div>' + margin
    )
    return page("분석", body)


# ------------------------------------------------------------------ 소싱
def render_sourcing(opps: Optional[list], keyword: str, sell_market: str) -> str:
    form = (
        f'<form method="get" action="/sourcing">'
        f'<label>키워드 <input name="keyword" value="{html.escape(keyword)}"></label>'
        f'<label>되팔 마켓 <input name="sell_market" value="{html.escape(sell_market or "_default")}"></label>'
        '<label>되팔 목표가 <input name="target_price" type="number"></label>'
        '<label>최소마진 <input name="min_margin" type="number" value="1"></label>'
        "<button>소싱 기회 찾기</button></form>"
    )
    if opps is None:
        return page("소싱", "<h1>소싱(되팔기)</h1>" + form +
                    '<div class="card muted">키워드를 넣고 실행하세요. 최저가 매입→마진을 계산합니다.</div>')
    if not opps:
        return page("소싱", "<h1>소싱(되팔기)</h1>" + form +
                    '<div class="card muted">조건을 만족하는 기회가 없습니다.</div>')
    cards = []
    for o in opps:
        m = o["margin"]
        rate = f'{m["margin_rate"]:.1%}' if m["margin_rate"] is not None else "-"
        cls = "ok" if m["margin"] > 0 else "bad"
        url = (f'<a href="{html.escape(o["buy"]["url"])}" target="_blank" rel="noopener">매입처</a>'
               if o["buy"].get("url") else "")
        cards.append(
            f'<div class="card"><b>{html.escape(o["name"][:60])}</b> '
            f'<span class="muted">(매물 {o["listings"]} · {", ".join(o["sources"])})</span><br>'
            f'매입 <b>{_won(o["buy"]["total"])}</b> [{html.escape(o["buy"]["source"])}] → '
            f'되팔 <b>{_won(o["sell_ref"]["total"])}</b>({html.escape(o["sell_ref"]["basis"])}) '
            f'· 차액 {_won(o["spread"])} → <span class="{cls}">마진 {_won(m["margin"])}원 ({rate})</span> {url}</div>'
        )
    body = ("<h1>소싱(되팔기)</h1>" + form +
            f'<div class="muted">기회 {len(opps)}건 · 매입가=수집 전 마켓 최저가</div>' + "".join(cards) +
            '<div class="warn">매입 전 실제 재고·정품·A/S를 확인하세요. 되팔기는 판매자 책임·마켓 약관 리스크가 있습니다.</div>')
    return page("소싱", body)


# ------------------------------------------------------------------ 가격변동
def render_tracking(changes: Optional[list], keyword: str) -> str:
    form = (
        f'<form method="get" action="/track">'
        f'<label>키워드 <input name="keyword" value="{html.escape(keyword)}"></label>'
        "<button>변동 조회</button></form>"
    )
    if changes is None:
        return page("가격변동", "<h1>가격 변동</h1>" + form +
                    '<div class="card muted">collect를 여러 번 돌리면 스냅샷이 쌓입니다. '
                    "샘플은 <code>python main.py demo</code>.</div>")
    if not changes:
        return page("가격변동", "<h1>가격 변동</h1>" + form +
                    '<div class="card muted">이력이 없습니다.</div>')
    rows = []
    for c in changes:
        if c["status"] == "down":
            badge, cls = "▼ 하락", "ok"
        elif c["status"] == "up":
            badge, cls = "▲ 상승", "bad"
        elif c["status"] == "new":
            badge, cls = "＋ 신규", "muted"
        else:
            badge, cls = "= 동일", "muted"
        prev = _won(c["previous"]) if c["previous"] is not None else "-"
        delta = f'{c["delta"]:+,}' if c["delta"] is not None else "-"
        pct = f'{c["pct"]:.1%}' if c["pct"] is not None else "-"
        rows.append(
            f'<tr><td class="{cls}">{badge}</td><td>{html.escape(c["name"][:50])}</td>'
            f'<td>{html.escape(c["source"])}</td><td class="num">{prev}</td>'
            f'<td class="num">{_won(c["latest"])}</td><td class="num">{delta}</td>'
            f'<td class="num">{pct}</td></tr>'
        )
    table = ("<table><thead><tr><th>변동</th><th>상품</th><th>소스</th>"
             "<th class='num'>이전</th><th class='num'>현재</th>"
             "<th class='num'>차액</th><th class='num'>%</th></tr></thead>"
             f"<tbody>{''.join(rows)}</tbody></table>")
    body = ("<h1>가격 변동</h1>" + form +
            f'<div class="card"><div class="muted">하락 폭 큰 순</div>{table}</div>')
    return page("가격변동", body)


# ------------------------------------------------------------------ 상세페이지
def render_detail_form(spec_json: str = "") -> str:
    sample = spec_json or (
        '{\n  "name": "스테인리스 텀블러 500ml",\n  "brand": "챈스토어",\n'
        '  "features": ["이중 진공 보온보냉", "식기세척기 사용 가능"],\n'
        '  "specs": {"용량": "500ml", "재질": "스테인리스 304"}\n}'
    )
    return page("상세페이지",
        "<h1>AI 상세페이지</h1>"
        '<form method="post" action="/detail">'
        '<label>마켓 <input name="market" value="naver"></label>'
        f'<textarea name="spec">{html.escape(sample)}</textarea>'
        "<button>생성</button></form>"
        '<div class="card muted">키가 없으면 템플릿 카피 + 이미지 자리표시로 생성됩니다.</div>')


def render_detail_result(result: dict, market_label: str) -> str:
    warns = ""
    if result.get("warnings"):
        items = "".join(f'<li>{html.escape(w["phrase"])} — {html.escape(w["reason"])}</li>'
                        for w in result["warnings"])
        warns = f'<div class="warn"><b>광고문구 검토필요</b><ul>{items}</ul></div>'
    imgs = ", ".join(f'{html.escape(i["provider"])}({"생성" if i["available"] else "자리표시"})'
                     for i in result.get("images", []))
    body = (
        f"<h1>상세페이지 결과 · {html.escape(market_label)}</h1>" + warns +
        f'<div class="muted">이미지: {imgs or "-"} · 생성: {html.escape(result["copy"]["provider"])}</div>'
        f'<div class="card">{result["html"]}</div>'
        '<p><a href="/detail">← 다시 생성</a></p>'
    )
    return page("상세페이지 결과", body)


# ------------------------------------------------------------------ CS
def render_cs_form(text: str = "") -> str:
    return page("CS",
        "<h1>AI CS 답변 초안</h1>"
        '<form method="post" action="/cs">'
        f'<textarea name="text" placeholder="고객 문의를 붙여넣으세요">{html.escape(text)}</textarea>'
        "<button>초안 생성</button></form>"
        '<div class="card muted">환불·교환·클레임·개인정보·금액이 걸리면 사람 확인 플래그가 붙습니다(자동발송 금지).</div>')


def render_cs_result(reply: dict) -> str:
    flag = ""
    if reply["needs_human"]:
        items = "".join(f"<li>{html.escape(r)}</li>" for r in reply["reasons"])
        flag = f'<div class="warn"><b>⚠ 사람 확인 후 발송 (자동발송 금지)</b><ul>{items}</ul></div>'
    else:
        flag = '<div class="muted">자동 위험요소는 없지만, 발송 전 검수를 권장합니다.</div>'
    body = (
        f'<h1>CS 초안 · 의도 {html.escape(reply["intent"])} '
        f'<span class="muted">(신뢰도 {reply["confidence"]}, {html.escape(reply["provider"])})</span></h1>'
        f'<div class="card" style="white-space:pre-wrap">{html.escape(reply["draft"])}</div>' + flag +
        '<p><a href="/cs">← 다시</a></p>'
    )
    return page("CS 결과", body)
