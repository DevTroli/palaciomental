from django.urls import path
from . import views

app_name = "listaEspera"

urlpatterns = [
    path("", v.index, name="index"),
]
