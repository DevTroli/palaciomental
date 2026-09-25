from django.urls import path
from . import views as v

app_name = "listaEspera"

urlpatterns = [
    path("entrar/", v.login_view, name="login"),
    path("cadastrar/", v.register, name="register"),
    path("sair/", v.logout_view, name="logout"),
    path("perfil/editar/", v.profile_edit, name="profile_edit"),
    path("perfil/<str:username>/", v.profile, name="profile"),
    path("projetos/", v.projects, name="projects"),
    path("projetos/novo/", v.project_create, name="project_create"),
    path("projetos/<int:pk>/", v.project_detail, name="project_detail"),
    path("projetos/<int:pk>/editar/", v.project_edit, name="project_edit"),
    path("status", v.status_page, name="status"),
    path("status/", v.status_page, name="status-slash"),
    path("saude", v.saude, name="saude"),
    path("lista-espera/", v.waitlist_submit, name="waitlist_submit"),
]
