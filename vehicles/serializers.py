import os
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from .models import Music, Vehicle, DealerVehicleReel, Like, SavedReel, VehicleInquiry, AIVideoGeneration, Comment
from django.contrib.auth import get_user_model

User = get_user_model()


def _copy_ai_generated_video_to_reel(reel, generation):
    """Copies a completed AIVideoGeneration's file onto a reel's video_file, avoiding a client-side re-upload."""
    reel.video_file.save(
        os.path.basename(generation.generated_video.name),
        ContentFile(generation.generated_video.read()),
        save=False
    )

class MusicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Music
        fields = ['id', 'title', 'file']

class DealerVehicleReelSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealerVehicleReel
        fields = ['id', 'video_file', 'background_music']

class VehicleSerializer(serializers.ModelSerializer):
    video_file = serializers.FileField(write_only=True, required=False)
    background_music = serializers.PrimaryKeyRelatedField(
        queryset=Music.objects.all(),
        required=False,
        write_only=True
    )
    # Alternative to uploading video_file: the job_id of a dealer's own
    # completed AIVideoGeneration. Lets the app skip downloading the
    # generated video and re-uploading it — we copy the file server-side.
    ai_video_generation = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    reels = DealerVehicleReelSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ['dealer', 'is_draft']

    def validate(self, data):
        video_file = data.get('video_file')
        job_id = data.get('ai_video_generation')

        if video_file and job_id:
            raise serializers.ValidationError("Provide only one of 'video_file' or 'ai_video_generation', not both.")

        if self.instance is None and not video_file and not job_id:
            raise serializers.ValidationError("Provide either 'video_file' or 'ai_video_generation'.")

        if job_id:
            try:
                generation = AIVideoGeneration.objects.get(job_id=job_id)
            except (AIVideoGeneration.DoesNotExist, DjangoValidationError, ValueError):
                raise serializers.ValidationError({"ai_video_generation": "AI video generation not found."})

            request = self.context.get('request')
            if request and generation.dealer_id != request.user.id:
                raise serializers.ValidationError({"ai_video_generation": "This AI video does not belong to you."})

            if generation.status != 'completed' or not generation.generated_video:
                raise serializers.ValidationError({"ai_video_generation": "This AI video generation is not completed yet."})

            data['_ai_video_generation_obj'] = generation

        return data

    def create(self, validated_data):
        video_file = validated_data.pop('video_file', None)
        background_music = validated_data.pop('background_music', None)
        validated_data.pop('ai_video_generation', None)
        ai_generation = validated_data.pop('_ai_video_generation_obj', None)

        vehicle = Vehicle.objects.create(**validated_data)

        # Create the primary reel for this vehicle automatically
        reel = DealerVehicleReel(vehicle=vehicle, dealer=vehicle.dealer, background_music=background_music)
        if video_file:
            reel.video_file = video_file
        else:
            _copy_ai_generated_video_to_reel(reel, ai_generation)
        reel.save()
        return vehicle

    def update(self, instance, validated_data):
        video_file = validated_data.pop('video_file', None)
        background_music = validated_data.pop('background_music', None)
        validated_data.pop('ai_video_generation', None)
        ai_generation = validated_data.pop('_ai_video_generation_obj', None)

        # Update vehicle fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update the associated reel if video or music is changed
        if video_file or ai_generation or background_music:
            reel = instance.reels.first() # Get the primary reel
            if reel:
                if video_file:
                    reel.video_file = video_file
                elif ai_generation:
                    _copy_ai_generated_video_to_reel(reel, ai_generation)
                if background_music:
                    reel.background_music = background_music
                reel.save()
        
        return instance

class DealerMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email']

class VehicleMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['name', 'year', 'asking_price', 'negotiable', 'mileage_km', 'fuel_type', 'transmission']

class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_profile_pic = serializers.ImageField(source='user.profile_photo', read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'user_name', 'user_email', 'user_profile_pic', 'text', 'created_at', 'is_owner']

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

class ReelNewsfeedSerializer(serializers.ModelSerializer):
    dealer_id = serializers.IntegerField(source='dealer.id', read_only=True)
    dealer_name = serializers.CharField(source='dealer.full_name', read_only=True)
    dealer_profile_photo = serializers.ImageField(source='dealer.business_info.dealership_logo', read_only=True)
    dealer_rating = serializers.DecimalField(source='dealer.business_info.rating', max_digits=3, decimal_places=2, read_only=True)
    dealer_reviews = serializers.IntegerField(source='dealer.business_info.review_count', read_only=True)
    vehicle_details = VehicleMinimalSerializer(source='vehicle', read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    dealer_is_followed = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)

    class Meta:
        model = DealerVehicleReel
        fields = ['id', 'video_file', 'dealer_id', 'dealer_name', 'dealer_profile_photo', 'dealer_rating', 'dealer_reviews', 'dealer_is_followed', 'vehicle_details', 'likes_count', 'share_count', 'view_count', 'comments_count', 'is_liked', 'is_saved', 'created_at']

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

    def get_dealer_is_followed(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            from users.models import Follow
            return Follow.objects.filter(follower=user, dealer=obj.dealer).exists()
        return False

class SavedReelListSerializer(serializers.ModelSerializer):
    reel = ReelNewsfeedSerializer(read_only=True)

    class Meta:
        from .models import SavedReel
        model = SavedReel
        fields = ['id', 'reel', 'created_at']

class ReelDetailSerializer(serializers.ModelSerializer):
    dealer = DealerMinimalSerializer(read_only=True)
    vehicle = VehicleSerializer(read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    saves_count = serializers.IntegerField(source='saves.count', read_only=True)
    suggested_reels = serializers.SerializerMethodField()
    location_details = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    dealer_is_followed = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)

    class Meta:
        model = DealerVehicleReel
        fields = '__all__'

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Like.objects.filter(user=request.user, reel=obj).exists()
        return False

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedReel.objects.filter(user=request.user, reel=obj).exists()
        return False

    def get_dealer_is_followed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from users.models import Follow
            return Follow.objects.filter(follower=request.user, dealer=obj.dealer).exists()
        return False

    def get_location_details(self, obj):
        vehicle = obj.vehicle
        dealer_info = None
        try:
            dealer_info = obj.dealer.business_info
        except:
            pass

        # Priority: 1. Vehicle specific location, 2. Dealer business location
        lat = vehicle.latitude or (dealer_info.latitude if dealer_info else None)
        long = vehicle.longitude or (dealer_info.longitude if dealer_info else None)
        
        address = vehicle.location # The CharField in Vehicle model
        if dealer_info and not lat:
             # If no coordinates on vehicle, maybe use dealer address as fallback
             pass

        return {
            "latitude": float(lat) if lat else None,
            "longitude": float(long) if long else None,
            "address": address,
            "city": dealer_info.division if dealer_info else None,
            "state": dealer_info.state if dealer_info else None,
            "full_address": f"{dealer_info.street_address}, {dealer_info.state}" if dealer_info else address
        }

    def get_suggested_reels(self, obj):
        # Get other reels from the same dealer, excluding the current one
        # Limit to 5 suggestions
        other_reels = DealerVehicleReel.objects.filter(
            dealer=obj.dealer,
            vehicle__is_draft=False
        ).exclude(id=obj.id).order_by('-created_at')[:5]
        
        return ReelNewsfeedSerializer(other_reels, many=True, context=self.context).data

class VehicleInquirySerializer(serializers.ModelSerializer):
    vehicle_title = serializers.CharField(source='reel.vehicle.name', read_only=True)
    dealer_name = serializers.CharField(source='reel.dealer.full_name', read_only=True)
    vehicle_price = serializers.DecimalField(source='reel.vehicle.asking_price', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = VehicleInquiry
        fields = '__all__'
        read_only_fields = ['buyer', 'reel']

    def validate(self, data):
        reel = self.context.get('reel')
        if not reel:
             raise serializers.ValidationError("Reel context is required.")
             
        if data.get('offered_price') and not reel.vehicle.negotiable:
            raise serializers.ValidationError({"offered_price": "This vehicle's price is not negotiable."})
            
        if not data.get('agreed_to_share'):
            raise serializers.ValidationError({"agreed_to_share": "You must agree to share this information."})

        return data

class AIVideoGenerationSerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = AIVideoGeneration
        fields = [
            'job_id', 'prompt', 'duration', 'resolution',
            'status', 'generated_video', 'error_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'generated_video', 'error_message', 'created_at', 'updated_at']
