from django.urls import path
from .views import ConversationListView, MessageHistoryView, StartChatView, GeneralStartChatView, SendMessageView

urlpatterns = [
    path('start-chat/', StartChatView.as_view(), name='start-chat'),
    path('start-chat-general/', GeneralStartChatView.as_view(), name='start-chat-general'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/messages/', MessageHistoryView.as_view(), name='message-history'),
    path('conversations/<int:conversation_id>/messages/send/', SendMessageView.as_view(), name='send-message'),
]
