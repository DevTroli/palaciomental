from django.urls import path
from . import views as v

app_name = "listaEspera"

urlpatterns = [
    path("", v.index, name="index"),
    path("entrar/", v.login_view, name="login"),
    path("cadastrar/", v.register, name="register"),
    path("sair/", v.logout_view, name="logout"),
    path("perfil/editar/", v.profile_edit, name="profile_edit"),
    path("perfil/<str:username>/", v.profile, name="profile"),
    path("projetos/", v.projects, name="projects"),
    path("projetos/novo/", v.project_create, name="project_create"),
    path("projetos/<int:pk>/", v.project_detail, name="project_detail"),
    path("projetos/<int:pk>/contexto/", v.project_context, name="project_context"),
    path("projetos/<int:pk>/editar/", v.project_edit, name="project_edit"),
    path("projetos/<int:pk>/excluir/", v.project_delete, name="project_delete"),
    path("status", v.status_page, name="status"),
    path("status/", v.status_page, name="status-slash"),
    path("saude", v.saude, name="saude"),
    path("lista-espera/", v.waitlist_submit, name="waitlist_submit"),
    path("projetos/<int:pk>/comentarios/", v.add_comment, name="add_comment"),
    path("comentarios/<int:comment_id>/editar/", v.edit_comment, name="edit_comment"),
    path("comentarios/<int:comment_id>/remover/", v.delete_comment, name="delete_comment"),
    path("projetos/<int:pk>/relevancia/", v.toggle_vote, name="toggle_vote"),
    path("projetos/<int:pk>/marcos/", v.add_milestone, name="add_milestone"),
    path("projetos/<int:pk>/permissao-marcos/", v.set_milestone_permission, name="set_milestone_permission"),
    path("marcos/<int:milestone_id>/editar/", v.edit_milestone, name="edit_milestone"),
    path("marcos/<int:milestone_id>/remover/", v.delete_milestone, name="delete_milestone"),
    path("projetos/<int:pk>/colaboracao/", v.request_collaboration, name="request_collaboration"),
    path("colaboracoes/<int:request_id>/decidir/", v.decide_collaboration, name="decide_collaboration"),
    path("caixa-de-entrada/", v.inbox, name="inbox"),
]
