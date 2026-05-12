from rest_framework import serializers
from .models import Music, Vehicle, DealerVehicleReel, Like, SavedReel
from django.contrib.auth import get_user_model

User = get_user_model()

class MusicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Music
        fields = ['id', 'title', 'file']

class DealerVehicleReelSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealerVehicleReel
        fields = ['id', 'video_file', 'background_music']

class VehicleSerializer(serializers.ModelSerializer):
    reels = DealerVehicleReelSerializer(many=True, required=False)

    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ['dealer', 'is_draft']

    def create(self, validated_data):
        reels_data = validated_data.pop('reels', [])
        vehicle = Vehicle.objects.create(**validated_data)
        for reel_data in reels_data:
            DealerVehicleReel.objects.create(vehicle=vehicle, dealer=vehicle.dealer, **reel_data)
        return vehicle

class DealerMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email']

class VehicleMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['name', 'year', 'asking_price', 'negotiable', 'mileage_km', 'fuel_type', 'transmission']

class ReelNewsfeedSerializer(serializers.ModelSerializer):
    dealer_name = serializers.CharField(source='dealer.full_name', read_only=True)
    vehicle_details = VehicleMinimalSerializer(source='vehicle', read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = DealerVehicleReel
        fields = ['id', 'video_file', 'dealer_name', 'vehicle_details', 'likes_count', 'share_count', 'is_liked', 'is_saved', 'created_at']

    def get_is_liked(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return Like.objects.filter(user=user, reel=obj).exists()
        return False

    def get_is_saved(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return SavedReel.objects.filter(user=user, reel=obj).exists()
        return False

class ReelDetailSerializer(serializers.ModelSerializer):
    dealer = DealerMinimalSerializer(read_only=True)
    vehicle = VehicleSerializer(read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    saves_count = serializers.IntegerField(source='saves.count', read_only=True)

    class Meta:
        model = DealerVehicleReel
        fields = '__all__'
