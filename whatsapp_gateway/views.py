from django.shortcuts import render
from django.http import JsonResponse
from .services import get_qr, get_status, reconnect


def setup_page(request):
    return render(request, "whatsapp/setup.html")


def qr_api(request):
    data = get_qr()
    return JsonResponse(data)


def status_api(request):
    data = get_status()
    return JsonResponse(data)


def reconnect_api(request):
    data = reconnect()
    return JsonResponse(data)