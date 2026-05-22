from django.urls import path
from .views import ConversationListView, MessageHistoryView, StartChatView

urlpatterns = [
    path('start-chat/', StartChatView.as_view(), name='start-chat'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/messages/', MessageHistoryView.as_view(), name='message-history'),
]
