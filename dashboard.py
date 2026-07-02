#!/usr/bin/env python3
"""chanstore 로컬 대시보드 (FastAPI).

수집·분석·소싱·상세페이지·CS를 CLI 없이 한 화면에서. API 키가 없어도 전부 동작한다
(분석·소싱은 수집 DB 기반, 상세·CS는 오프라인 폴백).

실행:
    pip install fastapi uvicorn
    python dashboard.py            # http://127.0.0.1:8000
    CHANSTORE_DB=output/chanstore.db python dashboard.py   # DB 경로 지정

렌더링/데이터 로직은 src/web/views.py(순수 함수)에 있고, 여기선 라우팅만 한다.
"""
# 주의: `from __future__ import annotations` 를 쓰지 않는다.
# 그러면 라우트의 `request: Request` 힌트가 문자열이 되어 FastAPI가 build_app() 지역
# 스코프의 Request 를 못 찾고 쿼리 파라미터로 오인(422)한다. 힌트를 즉시 평가시킨다.
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs

from src.web import views

DB_PATH = os.getenv("CHANSTORE_DB", "output/chanstore.db")
# /thumb 로 서빙 허용할 루트(경로 traversal 방지)
THUMB_ROOT = Path(os.getenv("CHANSTORE_OUTDIR", "output")).resolve()


def _load_products(keyword: str | None):
    from src.storage import Database
    if not Path(DB_PATH).exists():
        return []
    with Database(DB_PATH) as db:
        return db.fetch(keyword or None)


def _stats() -> dict:
    from src.storage import Database
    if not Path(DB_PATH).exists():
        return {"total": 0, "by_source": {}, "by_keyword": {}}
    with Database(DB_PATH) as db:
        return db.stats()


def _int(v) -> int | None:
    try:
        return int(v) if v not in (None, "", []) else None
    except (TypeError, ValueError):
        return None


def build_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse

    app = FastAPI(title="chanstore dashboard")

    async def form(request: Request) -> dict:
        raw = (await request.body()).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw).items()}

    @app.get("/", response_class=HTMLResponse)
    def home():
        return views.render_home(_stats())

    @app.get("/products", response_class=HTMLResponse)
    def products(request: Request):
        q = request.query_params
        keyword, source = q.get("keyword", ""), q.get("source", "")
        items = _load_products(keyword)
        if source:
            items = [p for p in items if p.source == source]
        return views.render_products(items, keyword=keyword, source=source)

    @app.get("/analyze", response_class=HTMLResponse)
    def analyze(request: Request):
        from src.analysis import analyze_keyword
        q = request.query_params
        keyword = q.get("keyword", "")
        if not keyword:
            return views.render_analysis(None, keyword)
        report = analyze_keyword(
            _load_products(keyword), keyword=keyword,
            sourcing_cost=_int(q.get("sourcing_cost")),
            target_price=_int(q.get("target_price")),
            market=q.get("market") or "_default",
        )
        return views.render_analysis(report.to_dict(), keyword)

    @app.get("/sourcing", response_class=HTMLResponse)
    def sourcing(request: Request):
        from src.analysis import find_arbitrage
        q = request.query_params
        keyword = q.get("keyword", "")
        sell_market = q.get("sell_market", "_default")
        if not keyword:
            return views.render_sourcing(None, keyword, sell_market)
        opps = find_arbitrage(
            _load_products(keyword), sell_market=sell_market,
            target_price=_int(q.get("target_price")),
            min_margin=_int(q.get("min_margin")) or 1,
        )
        return views.render_sourcing([o.to_dict() for o in opps], keyword, sell_market)

    @app.get("/track", response_class=HTMLResponse)
    def track(request: Request):
        from src.analysis import summarize_price_changes
        from src.storage import Database
        q = request.query_params
        keyword = q.get("keyword", "")
        if not Path(DB_PATH).exists():
            return views.render_tracking([], keyword)
        with Database(DB_PATH) as db:
            rows = db.fetch_history(keyword or None)
        changes = summarize_price_changes(rows)
        return views.render_tracking([c.to_dict() for c in changes], keyword)

    @app.get("/detail", response_class=HTMLResponse)
    def detail_form():
        return views.render_detail_form()

    @app.post("/detail", response_class=HTMLResponse)
    async def detail_make(request: Request):
        import json
        from src.ai import build_detail_page, export_for_market
        data = await form(request)
        try:
            spec = json.loads(data.get("spec", "{}"))
        except json.JSONDecodeError as e:
            return HTMLResponse(views.page("오류", f"<h1>JSON 오류</h1><p>{e}</p>"), status_code=400)
        page = build_detail_page(spec)
        exported = export_for_market(page, data.get("market", "_default"))
        result = {"html": exported["html"], "warnings": page["warnings"],
                  "images": page["images"], "copy": page["copy"]}
        return views.render_detail_result(result, exported["label"])

    @app.get("/cs", response_class=HTMLResponse)
    def cs_form():
        return views.render_cs_form()

    @app.post("/cs", response_class=HTMLResponse)
    async def cs_make(request: Request):
        from src.cs import Inquiry, KnowledgeBase, draft_reply
        data = await form(request)
        reply = draft_reply(Inquiry(text=data.get("text", "")), KnowledgeBase())
        return views.render_cs_result(reply.to_dict())

    @app.get("/thumb")
    def thumb(request: Request):
        raw = request.query_params.get("path", "")
        target = Path(raw).resolve()
        # THUMB_ROOT 밖 경로는 거부(경로 traversal 방지)
        if not str(target).startswith(str(THUMB_ROOT)) or not target.is_file():
            return PlainTextResponse("not found", status_code=404)
        return FileResponse(target)

    return app


def main() -> int:
    try:
        import uvicorn  # noqa: F401
        app = build_app()
    except ImportError:
        print("[안내] 대시보드는 fastapi, uvicorn 이 필요합니다:\n"
              "  pip install fastapi uvicorn\n"
              "  python dashboard.py", file=sys.stderr)
        return 2
    import uvicorn
    host = os.getenv("CHANSTORE_HOST", "127.0.0.1")
    port = int(os.getenv("CHANSTORE_PORT", "8000"))
    print(f"chanstore dashboard → http://{host}:{port}  (DB: {DB_PATH})")
    uvicorn.run(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
