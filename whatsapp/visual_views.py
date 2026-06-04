from __future__ import annotations

import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from whatsapp.models import VisualEdge, VisualFlow, VisualNode, WhatsAppAccount


def _ensure_account_for_user(*, account_id: str, user) -> WhatsAppAccount:
    return get_object_or_404(WhatsAppAccount, id=account_id, owner=user)


def _create_blank_flow(*, owner, account: WhatsAppAccount, name: str) -> VisualFlow:
    flow = VisualFlow.objects.create(owner=owner, whatsapp_account=account, name=name, is_active=True)
    VisualNode.objects.create(flow=flow, node_id="start", node_type=VisualFlow.NodeType.START, data={"text": "Start"}, position_x=40, position_y=40)
    return flow


def _create_demo_flow(*, owner, account: WhatsAppAccount) -> VisualFlow:
    """
    Creates a demo visual flow that does NOT override commerce unless the user types hi/menu/help.
    """
    name = "Demo WhatsApp Menu"
    # If already exists, reuse (and re-activate).
    existing = VisualFlow.objects.filter(owner=owner, whatsapp_account=account, name=name).first()
    if existing:
        VisualFlow.objects.filter(owner=owner, whatsapp_account=account).exclude(id=existing.id).update(is_active=False)
        existing.is_active = True
        existing.save(update_fields=["is_active", "updated_at"])
        return existing

    flow = _create_blank_flow(owner=owner, account=account, name=name)

    # Nodes
    VisualNode.objects.update_or_create(
        flow=flow,
        node_id="welcome",
        defaults={
            "node_type": VisualFlow.NodeType.MESSAGE,
            "data": {
                "text": (
                    "Welcome! Reply with:\n"
                    "1 View Products\n"
                    "2 Place Order\n"
                    "3 My Orders\n"
                    "4 Customer Support\n\n"
                    "Tip: you can also type products/cart/checkout anytime."
                )
            },
            "position_x": 280,
            "position_y": 40,
        },
    )
    VisualNode.objects.update_or_create(
        flow=flow,
        node_id="products",
        defaults={
            "node_type": VisualFlow.NodeType.ACTION,
            "data": {"action": "show_catalog"},
            "position_x": 280,
            "position_y": 150,
        },
    )
    VisualNode.objects.update_or_create(
        flow=flow,
        node_id="order",
        defaults={
            "node_type": VisualFlow.NodeType.MESSAGE,
            "data": {"text": "To order: add 2 <product>\nView cart: cart\nCheckout: checkout"},
            "position_x": 280,
            "position_y": 260,
        },
    )
    VisualNode.objects.update_or_create(
        flow=flow,
        node_id="orders",
        defaults={
            "node_type": VisualFlow.NodeType.ACTION,
            "data": {"action": "my_orders"},
            "position_x": 280,
            "position_y": 370,
        },
    )
    VisualNode.objects.update_or_create(
        flow=flow,
        node_id="support",
        defaults={
            "node_type": VisualFlow.NodeType.MESSAGE,
            "data": {"text": "Support: Please share your issue. A human agent will contact you shortly."},
            "position_x": 280,
            "position_y": 480,
        },
    )

    # Edges (explicit triggers only - no default to avoid overriding normal commerce)
    VisualEdge.objects.bulk_create(
        [
            VisualEdge(flow=flow, source_id="start", target_id="welcome", condition_text="hi", is_default=False),
            VisualEdge(flow=flow, source_id="start", target_id="welcome", condition_text="hello", is_default=False),
            VisualEdge(flow=flow, source_id="start", target_id="welcome", condition_text="help", is_default=False),
            VisualEdge(flow=flow, source_id="start", target_id="welcome", condition_text="menu", is_default=False),
            VisualEdge(flow=flow, source_id="start", target_id="welcome", condition_text="start", is_default=False),
            VisualEdge(flow=flow, source_id="welcome", target_id="products", condition_text="1", is_default=False),
            VisualEdge(flow=flow, source_id="welcome", target_id="order", condition_text="2", is_default=False),
            VisualEdge(flow=flow, source_id="welcome", target_id="orders", condition_text="3", is_default=False),
            VisualEdge(flow=flow, source_id="welcome", target_id="support", condition_text="4", is_default=False),
            VisualEdge(flow=flow, source_id="products", target_id="welcome", condition_text="menu", is_default=False),
            VisualEdge(flow=flow, source_id="order", target_id="welcome", condition_text="menu", is_default=False),
            VisualEdge(flow=flow, source_id="orders", target_id="welcome", condition_text="menu", is_default=False),
            VisualEdge(flow=flow, source_id="support", target_id="welcome", condition_text="menu", is_default=False),
        ]
    )

    return flow


@login_required
def visual_flow_list(request, account_id: str):
    account = _ensure_account_for_user(account_id=str(account_id), user=request.user)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "create":
            name = (request.POST.get("name") or "").strip()[:140] or f"Flow {uuid.uuid4().hex[:6].upper()}"
            try:
                # Enforce single active flow
                VisualFlow.objects.filter(owner=request.user, whatsapp_account=account).update(is_active=False)
                flow = _create_blank_flow(owner=request.user, account=account, name=name)
                messages.success(request, "Flow created.")
                return redirect(reverse("whatsapp:visual_flow_builder", kwargs={"account_id": str(account.id), "flow_id": str(flow.id)}))
            except Exception:
                messages.error(request, "Failed to create flow (duplicate name?).")
                return redirect(request.path)

        if action == "demo":
            try:
                VisualFlow.objects.filter(owner=request.user, whatsapp_account=account).update(is_active=False)
                flow = _create_demo_flow(owner=request.user, account=account)
                messages.success(request, "Demo flow created. Type 'hi' on WhatsApp to test.")
                return redirect(reverse("whatsapp:visual_flow_builder", kwargs={"account_id": str(account.id), "flow_id": str(flow.id)}))
            except Exception:
                messages.error(request, "Failed to create demo flow.")
                return redirect(request.path)

        if action == "activate":
            flow_id = (request.POST.get("flow_id") or "").strip()
            flow = VisualFlow.objects.filter(id=flow_id, owner=request.user, whatsapp_account=account).first()
            if flow:
                VisualFlow.objects.filter(owner=request.user, whatsapp_account=account).exclude(id=flow.id).update(is_active=False)
                flow.is_active = True
                flow.save(update_fields=["is_active", "updated_at"])
                messages.success(request, "Flow activated.")
            return redirect(request.path)

        if action == "delete":
            flow_id = (request.POST.get("flow_id") or "").strip()
            VisualFlow.objects.filter(id=flow_id, owner=request.user, whatsapp_account=account).delete()
            messages.success(request, "Flow deleted.")
            return redirect(request.path)

    flows = list(VisualFlow.objects.filter(owner=request.user, whatsapp_account=account).order_by("-updated_at", "-created_at")[:200])
    return render(request, "whatsapp/visual_flow_list.html", {"account": account, "flows": flows})


@login_required
def visual_flow_builder(request, account_id: str, flow_id: str):
    account = _ensure_account_for_user(account_id=str(account_id), user=request.user)
    flow = get_object_or_404(VisualFlow, id=flow_id, owner=request.user, whatsapp_account=account)

    nodes = list(flow.nodes.values("node_id", "node_type", "data", "position_x", "position_y"))
    edges = list(flow.edges.values("source_id", "target_id", "condition_text", "is_default"))

    return render(
        request,
        "whatsapp/visual_flow_builder.html",
        {
            "account": account,
            "flow": flow,
            "nodes_json": json.dumps(nodes),
            "edges_json": json.dumps(edges),
        },
    )


@login_required
@require_POST
def visual_flow_save(request, account_id: str, flow_id: str):
    account = _ensure_account_for_user(account_id=str(account_id), user=request.user)
    flow = get_object_or_404(VisualFlow, id=flow_id, owner=request.user, whatsapp_account=account)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"success": False, "error": "invalid_json"}, status=400)

    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])

    flow.nodes.all().delete()
    flow.edges.all().delete()

    for n in nodes:
        if not isinstance(n, dict):
            continue
        VisualNode.objects.create(
            flow=flow,
            node_id=str(n.get("node_id") or "")[:80],
            node_type=str(n.get("node_type") or VisualFlow.NodeType.MESSAGE)[:20],
            data=n.get("data") if isinstance(n.get("data"), dict) else {},
            position_x=int(n.get("position_x", 40)),
            position_y=int(n.get("position_y", 40)),
        )

    for e in edges:
        if not isinstance(e, dict):
            continue
        VisualEdge.objects.create(
            flow=flow,
            source_id=str(e.get("source_id") or "")[:80],
            target_id=str(e.get("target_id") or "")[:80],
            condition_text=str(e.get("condition_text") or "")[:200],
            is_default=bool(e.get("is_default")),
        )

    # Touch updated_at
    VisualFlow.objects.filter(id=flow.id).update(updated_at=timezone.now())
    return JsonResponse({"success": True})
