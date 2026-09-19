from django.urls import path
from . import views as v

app_name = "listaEspera"

urlpatterns = [
    path("", v.index, name="index"),
    path("saude", v.saude, name="saude")
]
