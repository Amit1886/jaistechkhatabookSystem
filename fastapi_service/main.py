from __future__ import annotations

import os
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException, Query


def _db_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return url


app = FastAPI(title="KhataPro FastAPI Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/products/search")
def product_search(q: str = Query(default="", min_length=0, max_length=80), limit: int = 20) -> dict[str, Any]:
    q = (q or "").strip()
    limit = max(1, min(int(limit or 20), 100))
    if not q:
        return {"ok": True, "count": 0, "items": []}

    sql = """
    SELECT id, name, price, stock, sku
    FROM commerce_product
    WHERE name ILIKE %(q)s
    ORDER BY name ASC
    LIMIT %(limit)s
    """
    with psycopg.connect(_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"q": f"%{q}%", "limit": limit})
            rows = cur.fetchall()
    items = [{"id": r[0], "name": r[1], "price": str(r[2]), "stock": int(r[3] or 0), "sku": r[4]} for r in rows]
    return {"ok": True, "count": len(items), "items": items}


@app.get("/products/by-sku/{sku}")
def product_by_sku(sku: str) -> dict[str, Any]:
    sku = (sku or "").strip()[:50]
    if not sku:
        raise HTTPException(status_code=400, detail="missing_sku")

    sql = """
    SELECT id, name, price, stock, sku
    FROM commerce_product
    WHERE sku = %(sku)s
    LIMIT 1
    """
    with psycopg.connect(_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"sku": sku})
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True, "item": {"id": row[0], "name": row[1], "price": str(row[2]), "stock": int(row[3] or 0), "sku": row[4]}}

