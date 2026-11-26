from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("manifest.webmanifest", views.manifest),
    path("api/search", views.search),
    path("api/line", views.line),
    path("api/about", views.about),
]
