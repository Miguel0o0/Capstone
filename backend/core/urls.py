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
    path("reuniones/", views.MeetingListView.as_view(), name="meeting_list"),
    path("reuniones/<int:pk>/", views.MeetingDetailView.as_view(), name="meeting_detail"),
    path("reuniones/nueva/", views.MeetingCreateView.as_view(), name="meeting_create"),
    path("reuniones/<int:pk>/editar/", views.MeetingUpdateView.as_view(), name="meeting_update"),
    path("reuniones/<int:pk>/eliminar/", views.MeetingDeleteView.as_view(), name="meeting_delete"),
    path("actas/<int:pk>/", views.MinutesDetailView.as_view(), name="minutes_detail"),
    path("actas/nueva/", views.MinutesCreateView.as_view(), name="minutes_create"),
    path("actas/<int:pk>/editar/", views.MinutesUpdateView.as_view(), name="minutes_update"),
    path("actas/<int:pk>/eliminar/", views.MinutesDeleteView.as_view(), name="minutes_delete"),
]
