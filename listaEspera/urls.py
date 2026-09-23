from django.urls import path
from . import views as v

app_name = "listaEspera"

urlpatterns = [
    path("", v.index, name="index"),
    path("status", v.status_page, name="status"),
    path("saude", v.saude, name="saude"),
    path("lista-espera/", v.waitlist_submit, name="waitlist_submit"),
]
