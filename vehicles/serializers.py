from rest_framework import serializers
from .models import Music, Vehicle, DealerVehicleReel, Like, SavedReel, VehicleInquiry, Comment
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
    video_file = serializers.FileField(write_only=True, required=False)
    background_music = serializers.PrimaryKeyRelatedField(
        queryset=Music.objects.all(), 
        required=False, 
        write_only=True
    )
    reels = DealerVehicleReelSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ['dealer', 'is_draft']

    def create(self, validated_data):
        video_file = validated_data.pop('video_file')
        background_music = validated_data.pop('background_music', None)
        
        vehicle = Vehicle.objects.create(**validated_data)
        
        # Create the primary reel for this vehicle automatically
        DealerVehicleReel.objects.create(
            vehicle=vehicle,
            dealer=vehicle.dealer,
            video_file=video_file,
            background_music=background_music
        )
        return vehicle

    def update(self, instance, validated_data):
        video_file = validated_data.pop('video_file', None)
        background_music = validated_data.pop('background_music', None)

        # Update vehicle fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update the associated reel if video or music is changed
        if video_file or background_music:
            reel = instance.reels.first() # Get the primary reel
            if reel:
                if video_file:
                    reel.video_file = video_file
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
