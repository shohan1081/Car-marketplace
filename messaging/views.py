from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Conversation, Message, Notification
from .serializers import ConversationSerializer, MessageSerializer, NotificationSerializer
from vehicles.models import DealerVehicleReel
from django.contrib.auth import get_user_model

User = get_user_model()

class GeneralStartChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            other_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if other_user == request.user:
            return Response({"error": "You cannot start a chat with yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Find or create a conversation between these two participants (with no specific reel)
        conversation = Conversation.objects.filter(
            reel__isnull=True,
            participants=request.user
        ).filter(participants=other_user).first()

        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(request.user, other_user)

        return Response({
            "conversation_id": conversation.id,
            "message": "Conversation ready."
        }, status=status.HTTP_200_OK)

class StartChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        reel_id = request.data.get('reel_id')
        if not reel_id:
            return Response({"error": "reel_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reel = DealerVehicleReel.objects.get(id=reel_id)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

        dealer = reel.dealer
        if dealer == request.user:
            return Response({"error": "You cannot start a chat with yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Find or create a conversation for this specific reel between these two participants
        conversation = Conversation.objects.filter(
            reel=reel,
            participants=request.user
        ).filter(participants=dealer).first()

        if not conversation:
            conversation = Conversation.objects.create(reel=reel)
            conversation.participants.add(request.user, dealer)

        return Response({
            "conversation_id": conversation.id,
            "message": "Conversation ready."
        }, status=status.HTTP_200_OK)

class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)

class MessageHistoryView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        # Ensure user is part of the conversation
        return Message.objects.filter(
            conversation_id=conversation_id, 
            conversation__participants=self.request.user
        ).order_by('created_at')

class SendMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        text = request.data.get('message')
        if not text:
            return Response({"error": "message is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = Conversation.objects.get(id=conversation_id, participants=request.user)
            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                text=text
            )
            serializer = MessageSerializer(msg)
            
            # Broadcast to websocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            channel_layer = get_channel_layer()
            
            payload = {
                'type': 'chat_message',
                'message': msg.text,
                'sender_email': request.user.email,
                'sender_id': request.user.id,
                'created_at': msg.created_at.isoformat(),
                'message_id': msg.id,
                'conversation_id': str(conversation_id)
            }
            
            for participant in conversation.participants.all():
                async_to_sync(channel_layer.group_send)(
                    f'user_{participant.id}',
                    payload
                )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Conversation.DoesNotExist:
            return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

