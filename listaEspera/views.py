from django.http import JsonResponse
from django.shortcuts import render

def index(request):
    return render(request, "listaEspera/index.html")


def saude(request):
    return JsonResponse({"status": "ok"})
