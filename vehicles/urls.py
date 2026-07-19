from django.urls import path
from .views import (
    MusicListView, VehicleCreateView, VehicleDetailView, DealerDashboardView,
    DealerInventoryView, VehiclePreviewView, VehicleDraftPublishView,
    NewsfeedView, ReelDetailView, LikeReelView, SaveReelView, ShareReelView,
    SavedReelsListView, VehicleInquiryCreateView, ReelViewCountView,
    DealerInquiryListView, DealerInquiryDetailView, DealerInquiryActionView,
    VehicleSearchView
)

urlpatterns = [
    path('music/', MusicListView.as_view(), name='music-list'),
    path('dashboard/', DealerDashboardView.as_view(), name='dealer-dashboard'),
    path('inventory/', DealerInventoryView.as_view(), name='dealer-inventory'),
    path('create/', VehicleCreateView.as_view(), name='vehicle-create'),
    path('<int:pk>/', VehicleDetailView.as_view(), name='vehicle-detail'),
    path('preview/', VehiclePreviewView.as_view(), name='vehicle-preview'),
    path('publish/<int:pk>/', VehicleDraftPublishView.as_view(), name='vehicle-publish'),
    
    # Dealer Inquiries
    path('inquiries/', DealerInquiryListView.as_view(), name='dealer-inquiries-list'),
    path('inquiries/<int:pk>/', DealerInquiryDetailView.as_view(), name='dealer-inquiry-detail'),
    path('inquiries/<int:pk>/<str:action>/', DealerInquiryActionView.as_view(), name='dealer-inquiry-action'),
    
    # Newsfeed & Interactions
    path('newsfeed/', NewsfeedView.as_view(), name='newsfeed'),
    path('search/', VehicleSearchView.as_view(), name='vehicle-search'),
    path('reels/<int:pk>/', ReelDetailView.as_view(), name='reel-detail'),
    path('reels/<int:pk>/like/', LikeReelView.as_view(), name='reel-like'),
    path('reels/<int:pk>/save/', SaveReelView.as_view(), name='reel-save'),
    path('reels/saved/', SavedReelsListView.as_view(), name='saved-reels-list'),
    path('reels/<int:pk>/share/', ShareReelView.as_view(), name='reel-share'),
    path('reels/<int:pk>/view/', ReelViewCountView.as_view(), name='reel-view'),
    path('reels/<int:pk>/inquiry/', VehicleInquiryCreateView.as_view(), name='reel-inquiry'),
]
