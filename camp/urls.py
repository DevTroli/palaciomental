from django.urls import path

from . import views

app_name = "camp"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cadastro/", views.camp_register, name="register"),
    path("historia/", views.history, name="history"),
    path("mensagens/", views.inbox, name="inbox"),
    path("mensagens/<int:pk>/decidir/", views.inbox_decide, name="inbox_decide"),
    path("gestao/", views.manage, name="manage"),
    path("sair/", views.logout_view, name="logout"),
    path("explorar/", views.explore, name="explore"),
    path("explorar/<int:pk>/participar/", views.join_project, name="join_project"),
    path("perfil/participacoes/<int:pk>/sair/", views.leave_project, name="leave_project"),
    path("calendario/", views.calendar_view, name="calendar"),
    path("calendario/novo/", views.event_create, name="event_create"),
    path("calendario/<int:pk>/editar/", views.event_edit, name="event_edit"),
    path("calendario/<int:pk>/excluir/", views.event_delete, name="event_delete"),
    path("calendario/<int:pk>/entregar/", views.calendar_toggle, name="calendar_toggle"),
    path("perfil/", views.profile, name="profile"),
    path("perfil/projetos/novo/", views.project_create, name="project_create"),
    path("perfil/projetos/<int:pk>/editar/", views.project_edit, name="project_edit"),
    path("perfil/projetos/<int:pk>/excluir/", views.project_delete, name="project_delete"),
]
