# backend/core/urls.py
from django.urls import path
from . import views

app_name = "core"  

urlpatterns = [
    path("", views.home, name="home"),
    path("panel/", views.dashboard, name="dashboard"),
    path("avisos/", views.AnnouncementListView.as_view(), name="announcement_list"),
    path("avisos/<int:pk>/", views.AnnouncementDetailView.as_view(), name="announcement_detail"),
    path("avisos/nuevo/", views.AnnouncementCreateView.as_view(), name="announcement_create"),
    path("avisos/<int:pk>/editar/", views.AnnouncementUpdateView.as_view(), name="announcement_update"),
    path("avisos/<int:pk>/eliminar/", views.AnnouncementDeleteView.as_view(), name="announcement_delete"),
]
