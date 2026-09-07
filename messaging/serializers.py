from rest_framework import serializers
from .models import Conversation, Message, Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'notification_type', 'reference_id', 'extra_data', 'is_read', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender_id', 'sender_email', 'text', 'is_read', 'created_at']

class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'reel', 'other_participant', 'last_message', 'updated_at']

    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None

    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request:
            user = request.user
            other = obj.participants.exclude(id=user.id).first()
            if other:
                photo_url = None
                if other.profile_photo:
                    photo_url = request.build_absolute_uri(other.profile_photo.url)
                elif other.is_dealer and hasattr(other, 'business_info') and other.business_info.dealership_logo:
                    photo_url = request.build_absolute_uri(other.business_info.dealership_logo.url)
                return {
                    'id': other.id,
                    'full_name': other.full_name,
                    'email': other.email,
                    'profile_photo': photo_url,
                    'is_online': other.is_online,
                }
        return None
