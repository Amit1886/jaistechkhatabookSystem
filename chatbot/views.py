from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from .models import ChatFAQ, ChatMessage
from .models import ChatbotFlow, ChatbotNode, ChatbotEdge
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
import uuid
import json

try:
    import openai
    from django.conf import settings
    openai.api_key = getattr(settings, 'OPENAI_API_KEY', None)
except ImportError:
    openai = None


@csrf_exempt
def chatbot_reply(request):
    data = json.loads(request.body)
    user_msg = data.get("message","").lower()

    # 1️⃣ Create message entry
    chat = ChatMessage.objects.create(user_message=user_msg)

    # 2️⃣ Admin reply check
    if chat.admin_reply:
        chat.is_replied_by_admin = True
        chat.bot_reply = chat.admin_reply
        chat.save()
        return JsonResponse({"reply": chat.bot_reply})

    # 3️⃣ FAQ match
    for faq in ChatFAQ.objects.all():
        if faq.keyword.lower() in user_msg:
            chat.bot_reply = faq.answer
            chat.save()
            return JsonResponse({"reply": faq.answer})

    # 4️⃣ Default AI-style fallback
    smart_reply = (
        "Thanks for your message 🙏\n"
        "Our team will get back to you shortly.\n"
        "You can also contact us on WhatsApp 📞"
    )

    chat.bot_reply = smart_reply
    chat.save()
    return JsonResponse({"reply": smart_reply})


# ---------------- Flow Builder (Admin) ----------------
@staff_member_required(login_url="/superadmin/login/")
def flow_list(request):
    if not (request.user.is_staff or request.user.has_perm("chatbot.can_manage_flows")):
        return HttpResponseForbidden("Forbidden")
    flows = ChatbotFlow.objects.all().order_by("-created_at")
    context = admin.site.each_context(request)
    context.update({"flows": flows})
    return render(request, "chatbot/flow_list.html", context)


@staff_member_required(login_url="/superadmin/login/")
def flow_builder(request, flow_id):
    if not (request.user.is_staff or request.user.has_perm("chatbot.can_manage_flows")):
        return HttpResponseForbidden("Forbidden")
    flow = get_object_or_404(ChatbotFlow, id=flow_id)
    nodes = list(flow.nodes.values("node_id", "node_type", "data", "position_x", "position_y"))
    edges = list(flow.edges.values("source_id", "target_id", "condition_text", "is_default"))
    context = admin.site.each_context(request)
    context.update(
        {
            "flow": flow,
            "nodes_json": json.dumps(nodes),
            "edges_json": json.dumps(edges),
        }
    )
    return render(request, "chatbot/flow_builder.html", context)


@staff_member_required(login_url="/superadmin/login/")
def flow_create(request):
    if not (request.user.is_staff or request.user.has_perm("chatbot.can_manage_flows")):
        return HttpResponseForbidden("Forbidden")
    if request.method == "POST":
        name = request.POST.get("name") or f"Flow {uuid.uuid4().hex[:6].upper()}"
        flow = ChatbotFlow.objects.create(name=name, is_active=True)
        ChatbotNode.objects.create(flow=flow, node_id="start", node_type="start", data={"text": "Start"})
        return JsonResponse({"success": True, "flow_id": flow.id})
    return JsonResponse({"error": "POST required"}, status=405)


@staff_member_required(login_url="/superadmin/login/")
@require_POST
def flow_save(request, flow_id):
    if not (request.user.is_staff or request.user.has_perm("chatbot.can_manage_flows")):
        return HttpResponseForbidden("Forbidden")
    flow = get_object_or_404(ChatbotFlow, id=flow_id)

    payload = json.loads(request.body.decode("utf-8"))
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])

    flow.nodes.all().delete()
    flow.edges.all().delete()

    for n in nodes:
        ChatbotNode.objects.create(
            flow=flow,
            node_id=n.get("node_id"),
            node_type=n.get("node_type"),
            data=n.get("data") or {},
            position_x=int(n.get("position_x", 40)),
            position_y=int(n.get("position_y", 40)),
        )

    for e in edges:
        ChatbotEdge.objects.create(
            flow=flow,
            source_id=e.get("source_id"),
            target_id=e.get("target_id"),
            condition_text=e.get("condition_text") or "",
            is_default=bool(e.get("is_default")),
        )

    return JsonResponse({"success": True})


def get_ai_reply(message):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
              {"role":"system","content":"You are a polite Indian business assistant."},
              {"role":"user","content":message}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Our executive will reply shortly 🙏"
