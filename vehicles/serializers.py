import os
import shutil
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from .models import Music, Vehicle, DealerVehicleReel, Like, SavedReel, VehicleInquiry, AIVideoGeneration, Comment
from django.contrib.auth import get_user_model

User = get_user_model()


def _copy_ai_generated_video_to_reel(reel, generation):
    """Copies a completed AIVideoGeneration's file onto a reel's video_file, avoiding in-memory buffering."""
    src_file = generation.generated_video
    if not src_file:
        return

    dest_filename = os.path.basename(src_file.name)
    target_rel_path = reel.video_file.field.generate_filename(reel, dest_filename)

    try:
        # Fast local filesystem copy (zero memory allocation)
        src_path = src_file.path
        target_full_path = reel.video_file.storage.path(target_rel_path)
        os.makedirs(os.path.dirname(target_full_path), exist_ok=True)
        shutil.copy2(src_path, target_full_path)
        reel.video_file.name = target_rel_path
    except Exception:
        # Fallback for cloud/remote storage backends
        src_file.open('rb')
        reel.video_file.save(dest_filename, src_file, save=False)

class MusicSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    class Meta:
        model = Music
        fields = ['id', 'title', 'file']

    def get_file(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        if request:
            try:
                return request.build_absolute_uri(obj.file.url)
            except Exception:
                return obj.file.url
        return obj.file.url

class FlexibleMusicRelatedField(serializers.PrimaryKeyRelatedField):
    """Accepts Music ID (int/str), None, null, or empty string from multipart forms."""
    def to_internal_value(self, data):
        if data in ('', 'null', 'None', 0, '0', None):
            return None
        return super().to_internal_value(data)

class DealerVehicleReelSerializer(serializers.ModelSerializer):
    background_music = MusicSerializer(read_only=True)

    class Meta:
        model = DealerVehicleReel
        fields = ['id', 'video_file', 'background_music']

class VehicleSerializer(serializers.ModelSerializer):
    video_file = serializers.FileField(write_only=True, required=False)
    background_music = FlexibleMusicRelatedField(
        queryset=Music.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    # Alternative to uploading video_file: the job_id of a dealer's own
    # completed AIVideoGeneration. Lets the app skip downloading the
    # generated video and re-uploading it — we copy the file server-side.
    ai_video_generation = serializers.CharField(write_only=True, required=False, allow_null=True)
    reels = DealerVehicleReelSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ['dealer', 'is_draft']

    def validate(self, data):
        video_file = data.get('video_file')
        # Allow flexible field names for the AI video: 'ai_video_generation', 'job_id', 'ai_video_job_id', or 'video_url'
        job_id = (
            data.get('ai_video_generation')
            or (self.initial_data.get('job_id') if hasattr(self, 'initial_data') and isinstance(self.initial_data, dict) else None)
            or (self.initial_data.get('ai_video_job_id') if hasattr(self, 'initial_data') and isinstance(self.initial_data, dict) else None)
        )
        if not job_id and hasattr(self, 'initial_data') and isinstance(self.initial_data, dict) and self.initial_data.get('video_url'):
            import re
            match = re.search(r'ai_gen_([a-f0-9\-]{36})\.mp4', str(self.initial_data.get('video_url')))
            if match:
                job_id = match.group(1)

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
            reel.is_ai_generated = False
        else:
            _copy_ai_generated_video_to_reel(reel, ai_generation)
            reel.is_ai_generated = True
            reel.ai_generation = ai_generation
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
                    reel.is_ai_generated = False
                    reel.ai_generation = None
                elif ai_generation:
                    _copy_ai_generated_video_to_reel(reel, ai_generation)
                    reel.is_ai_generated = True
                    reel.ai_generation = ai_generation
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
    background_music = MusicSerializer(read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    dealer_is_followed = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)

    class Meta:
        model = DealerVehicleReel
        fields = [
            'id', 'video_file', 'background_music', 'is_ai_generated', 'dealer_id', 'dealer_name',
            'dealer_profile_photo', 'dealer_rating', 'dealer_reviews',
            'dealer_is_followed', 'vehicle_details', 'likes_count', 'share_count',
            'view_count', 'comments_count', 'is_liked', 'is_saved', 'created_at'
        ]

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
    background_music = MusicSerializer(read_only=True)
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
    vehicle_id = serializers.IntegerField(source='reel.vehicle.id', read_only=True)
    vehicle_year = serializers.IntegerField(source='reel.vehicle.year', read_only=True)
    vehicle_price = serializers.DecimalField(source='reel.vehicle.asking_price', max_digits=12, decimal_places=2, read_only=True)
    dealer_id = serializers.IntegerField(source='reel.dealer.id', read_only=True)
    dealer_name = serializers.CharField(source='reel.dealer.full_name', read_only=True)
    dealer_photo = serializers.SerializerMethodField()
    reel_video = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    loan_tenure_display = serializers.CharField(source='get_loan_tenure_display', read_only=True)
    credit_estimate_display = serializers.CharField(source='get_credit_estimate_display', read_only=True)

    class Meta:
        model = VehicleInquiry
        fields = '__all__'
        read_only_fields = ['buyer', 'reel']

    def get_conversation_id(self, obj):
        from messaging.models import Conversation
        if obj.reel and obj.buyer and obj.reel.dealer:
            conv = Conversation.objects.filter(
                reel=obj.reel,
                participants=obj.buyer
            ).filter(participants=obj.reel.dealer).first()
            return conv.id if conv else None
        return None

    def get_dealer_photo(self, obj):
        if not obj.reel or not obj.reel.dealer:
            return None
        dealer = obj.reel.dealer
        request = self.context.get('request')
        url = None
        if hasattr(dealer, 'business_info') and dealer.business_info and dealer.business_info.dealership_logo:
            url = dealer.business_info.dealership_logo.url
        elif dealer.profile_photo:
            url = dealer.profile_photo.url
        if url and request:
            return request.build_absolute_uri(url)
        return url

    def get_reel_video(self, obj):
        if obj.reel and obj.reel.video_file:
            request = self.context.get('request')
            url = obj.reel.video_file.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

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
    is_used = serializers.SerializerMethodField()
    vehicle_id = serializers.SerializerMethodField()
    vehicle_name = serializers.SerializerMethodField()
    generated_video = serializers.SerializerMethodField()

    class Meta:
        model = AIVideoGeneration
        fields = [
            'job_id', 'prompt', 'duration', 'resolution',
            'status', 'generated_video', 'is_used', 'vehicle_id', 'vehicle_name',
            'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'generated_video', 'error_message', 'created_at', 'updated_at']

    def get_is_used(self, obj):
        return obj.reels.exists()

    def get_vehicle_id(self, obj):
        first_reel = obj.reels.first()
        return first_reel.vehicle_id if first_reel else None

    def get_vehicle_name(self, obj):
        first_reel = obj.reels.first()
        return first_reel.vehicle.name if first_reel else None

    def get_generated_video(self, obj):
        if not obj.generated_video:
            return None
        request = self.context.get('request')
        if request:
            try:
                return request.build_absolute_uri(obj.generated_video.url)
            except Exception:
                return obj.generated_video.url
        return obj.generated_video.url
