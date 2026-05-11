from django.urls import path
from .views import (
    MusicListView, VehicleCreateView, 
    VehiclePreviewView, VehicleDraftPublishView
)

urlpatterns = [
    path('music/', MusicListView.as_view(), name='music-list'),
    path('create/', VehicleCreateView.as_view(), name='vehicle-create'),
    path('preview/', VehiclePreviewView.as_view(), name='vehicle-preview'),
    path('publish/<int:pk>/', VehicleDraftPublishView.as_view(), name='vehicle-publish'),
]
