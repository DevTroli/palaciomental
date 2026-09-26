from django.urls import path

from . import views

app_name = "core"

urlpatterns = [path("mvp/", views.index, name="index")]
