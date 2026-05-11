from rest_framework import serializers
from .models import Music, Vehicle, DealerVehicleReel

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
