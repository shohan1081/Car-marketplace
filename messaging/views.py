from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from vehicles.models import DealerVehicleReel

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
