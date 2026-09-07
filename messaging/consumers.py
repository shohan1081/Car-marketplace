import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation, Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        print(f"Connecting user: {self.user} (Authenticated: {self.user.is_authenticated})")
        
        if not self.user.is_authenticated:
            print("Connection rejected: User not authenticated")
            await self.close()
            return

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Update last_active
        from django.utils import timezone
        self.user.last_active = timezone.now()
        await database_sync_to_async(self.user.save)(update_fields=['last_active'])

        # Check if user is part of the conversation
        is_part = await self.is_participant(self.user, self.conversation_id)
        print(f"Is participant in conversation {self.conversation_id}: {is_part}")
        
        if not is_part:
            print(f"Connection rejected: User {self.user.email} is not a participant in conversation {self.conversation_id}")
            await self.close()
            return

        print(f"Connection accepted for user {self.user.email} in room {self.room_group_name}")
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get('message')

        if not message_text:
            return

        # Save message to DB
        msg = await self.save_message(self.user, self.conversation_id, message_text)

        # Send message to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_text,
                'sender_email': self.user.email,
                'created_at': str(msg.created_at)
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def is_participant(self, user, conversation_id):
        return Conversation.objects.filter(id=conversation_id, participants=user).exists()

    @database_sync_to_async
    def save_message(self, user, conversation_id, text):
        try:
            conv = Conversation.objects.get(id=conversation_id)
            msg = Message.objects.create(conversation=conv, sender=user, text=text)
            conv.save() # Triggers auto_now updated_at
            return msg
        except Conversation.DoesNotExist:
            return None

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f'user_{self.user.id}'
        
        from django.utils import timezone
        self.user.last_active = timezone.now()
        await database_sync_to_async(self.user.save)(update_fields=['last_active'])

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
