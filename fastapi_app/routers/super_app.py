from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field


router = APIRouter(prefix="/super-app", tags=["super-app"])


class CartLine(BaseModel):
    sku: str
    name: str
    qty: int = Field(default=1, ge=1)
    price: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=0.18, ge=0)


class PosCheckoutRequest(BaseModel):
    tenant_id: str = "demo"
    business_id: str = "biz_demo"
    store_id: str = "store_main"
    terminal_id: str = "pos_01"
    customer_id: str | None = None
    payment_method: str = "upi"
    lines: list[CartLine]


class ApiTestRequest(BaseModel):
    environment: str = "local"
    method: str = "GET"
    endpoint: str = "/api/system/app-config/"
    mock: bool = False


@router.get("/bootstrap")
def bootstrap():
    return {
        "ok": True,
        "generated_at": _now(),
        "modules": [
            "erp",
            "accounting",
            "pos",
            "self_checkout",
            "ecommerce",
            "crm",
            "hrm",
            "inventory",
            "purchase",
            "sales",
            "reports",
            "admin_builder",
            "api_management",
            "apk_builder",
        ],
        "features": {
            "offline_mode": True,
            "websocket_sync": True,
            "multi_tenant": True,
            "rbac": True,
            "mock_api": True,
            "apk_build_queue": True,
        },
    }


@router.get("/dashboard")
def dashboard():
    return {
        "kpis": [
            {"key": "sales", "label": "Today Sales", "value": 2543210, "delta": "+16.2%"},
            {"key": "orders", "label": "Orders", "value": 1245, "delta": "+12.8%"},
            {"key": "customers", "label": "Customers", "value": 2356, "delta": "+8.1%"},
            {"key": "profit", "label": "Net Profit", "value": 420220, "delta": "+18.4%"},
        ],
        "activity": [
            {"type": "pos", "title": "Invoice created", "amount": 2430, "status": "synced"},
            {"type": "stock", "title": "Low stock alert", "amount": 6, "status": "attention"},
            {"type": "crm", "title": "Lead qualified", "amount": 120000, "status": "pipeline"},
        ],
    }


@router.post("/pos/checkout")
def checkout(payload: PosCheckoutRequest):
    subtotal = sum(line.qty * line.price for line in payload.lines)
    tax = sum(line.qty * line.price * line.tax_rate for line in payload.lines)
    total = subtotal + tax
    return {
        "ok": True,
        "invoice_id": f"INV-{uuid4().hex[:8].upper()}",
        "tenant_id": payload.tenant_id,
        "business_id": payload.business_id,
        "store_id": payload.store_id,
        "terminal_id": payload.terminal_id,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "total": round(total, 2),
        "payment_method": payload.payment_method,
        "offline_sync_token": uuid4().hex,
        "receipt": {"thermal": True, "qr_payment": payload.payment_method in {"upi", "qr"}},
    }


@router.get("/admin/runtime-config")
def runtime_config():
    return {
        "layout_builder": {"enabled": True, "columns": 12, "density": "comfortable"},
        "theme_builder": {"brand": "Billentra", "radius": 8, "dark_mode": True},
        "feature_toggles": {
            "pos": True,
            "crm": True,
            "ecommerce": True,
            "self_checkout": True,
            "api_management": True,
        },
        "widgets": ["kpi_cards", "sales_chart", "live_orders", "stock_alerts"],
    }


@router.post("/api-test")
def api_test(payload: ApiTestRequest):
    return {
        "ok": True,
        "environment": payload.environment,
        "mock": payload.mock,
        "request": {"method": payload.method, "endpoint": payload.endpoint},
        "response": {"status": 200, "latency_ms": 42, "body": {"message": "connected"}},
    }


@router.post("/builds/apk")
def create_apk_build(version: str = "1.0.1+2", channel: str = "release"):
    return {
        "ok": True,
        "build_id": f"APK-{uuid4().hex[:8].upper()}",
        "version": version,
        "channel": channel,
        "status": "queued",
        "download_url": "/distribution/downloads/latest.apk",
        "ota": {"enabled": True, "rollout_percent": 25},
    }


@router.websocket("/ws")
async def super_app_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected", "at": _now()})
        while True:
            event = await websocket.receive_json()
            await websocket.send_json({
                "type": "ack",
                "event": event,
                "stock": {"sku": "P-1003", "qty": 6, "status": "low"},
                "orders": {"new": 3, "paid": 2},
                "at": _now(),
            })
    except WebSocketDisconnect:
        return


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
