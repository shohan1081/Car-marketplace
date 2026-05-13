from django.urls import path
from .views import ConversationListView, MessageHistoryView

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/messages/', MessageHistoryView.as_view(), name='message-history'),
]
