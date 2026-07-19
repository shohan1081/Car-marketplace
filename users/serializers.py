from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserPreference, OTP, BusinessInformation

User = get_user_model()

class BuyerSignupSerializer(serializers.ModelSerializer):
    re_enter_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'location', 'profile_photo', 'password', 're_enter_password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['re_enter_password']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

    def create(self, validated_data):
        validated_data.pop('re_enter_password', None)
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            location=validated_data.get('location', ''),
            profile_photo=validated_data.get('profile_photo', None),
            is_buyer=True
        )
        return user

    def update(self, instance, validated_data):
        validated_data.pop('re_enter_password', None)
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=4)

class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=4)
    new_password = serializers.CharField(write_only=True)

class DealerSignupSerializer(serializers.ModelSerializer):
    re_enter_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone_number', 'designation', 'password', 're_enter_password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['re_enter_password']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

    def create(self, validated_data):
        validated_data.pop('re_enter_password', None)
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            phone_number=validated_data.get('phone_number', ''),
            designation=validated_data.get('designation', ''),
            is_dealer=True
        )
        return user

    def update(self, instance, validated_data):
        validated_data.pop('re_enter_password', None)
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class BusinessInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessInformation
        fields = '__all__'
        read_only_fields = ['user', 'verification_status', 'rejection_reason', 'rating', 'review_count', 'follower_count', 'share_count']


    def validate_specialization(self, value):
        import json
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass # let it be a string, though it will fail the list check below
        
        if not isinstance(value, list):
            value = [value]

        valid_choices = [choice[0] for choice in BusinessInformation.SPECIALIZATION_CHOICES]
        for s in value:
            if s not in valid_choices:
                raise serializers.ValidationError(f"{s} is not a valid specialization.")
        return value

class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ['vehicle_types', 'budget_range', 'min_budget', 'max_budget', 'fuel_prefs', 'transmission_prefs', 'condition_prefs', 'city']

    def validate_vehicle_types(self, value):
        valid_types = [choice[0] for choice in UserPreference.VEHICLE_CHOICES]
        for t in value:
            if t not in valid_types:
                raise serializers.ValidationError(f"{t} is not a valid vehicle type.")
        return value

    def validate_fuel_prefs(self, value):
        if not value:
            return value
        valid_fuels = [choice[0] for choice in UserPreference.FUEL_CHOICES]
        for f in value:
            if f not in valid_fuels:
                raise serializers.ValidationError(f"{f} is not a valid fuel preference.")
        return value

class UserProfileSerializer(serializers.ModelSerializer):
    preferences = UserPreferenceSerializer(read_only=True)
    business_info = BusinessInformationSerializer(read_only=True)
    subscription = serializers.SerializerMethodField()
    activities = serializers.SerializerMethodField()
    saved_reels_count = serializers.SerializerMethodField()
    unread_messages_count = serializers.SerializerMethodField()
    inquiry_count = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'phone_number', 'designation', 'profile_photo', 'location', 
            'preferences', 'business_info', 'subscription',
            'activities', 'saved_reels_count', 'unread_messages_count', 'inquiry_count',
            'verification_status', 'is_buyer', 'is_dealer'
        ]

    def get_subscription(self, obj):
        if not obj.is_dealer:
            return None
        from subscriptions.serializers import DealerSubscriptionSerializer
        try:
            return DealerSubscriptionSerializer(obj.subscription).data
        except Exception:
            return None

    def get_verification_status(self, obj):
        if obj.is_dealer:
            try:
                return obj.business_info.verification_status
            except BusinessInformation.DoesNotExist:
                return 'not_submitted'
        return 'n/a'

    def get_saved_reels_count(self, obj):
        from vehicles.models import SavedReel
        return SavedReel.objects.filter(user=obj).count()

    def get_unread_messages_count(self, obj):
        from messaging.models import Message
        return Message.objects.filter(
            conversation__participants=obj, 
            is_read=False
        ).exclude(sender=obj).count()

    def get_inquiry_count(self, obj):
        from vehicles.models import VehicleInquiry
        return VehicleInquiry.objects.filter(buyer=obj).count()

    def get_activities(self, obj):
        from vehicles.models import Like, SavedReel
        from vehicles.serializers import ReelNewsfeedSerializer
        
        # Get last 5 likes
        recent_likes = Like.objects.filter(user=obj).order_by('-created_at')[:5]
        # Get last 5 saves
        recent_saves = SavedReel.objects.filter(user=obj).order_by('-created_at')[:5]
        
        activities = []
        
        for like in recent_likes:
            activities.append({
                'type': 'like',
                'created_at': like.created_at,
                'reel': ReelNewsfeedSerializer(like.reel, context=self.context).data
            })
            
        for save in recent_saves:
            activities.append({
                'type': 'save',
                'created_at': save.created_at,
                'reel': ReelNewsfeedSerializer(save.reel, context=self.context).data
            })
            
        # Sort combined activities by date
        activities.sort(key=lambda x: x['created_at'], reverse=True)
        return activities[:10]

from .models import DealerReview

class DealerReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.full_name', read_only=True)

    class Meta:
        model = DealerReview
        fields = ['id', 'reviewer_name', 'rating', 'comment', 'created_at']

class PublicBusinessInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessInformation
        fields = [
            'dealership_name', 'display_name', 'specialization', 
            'street_address', 'state', 'division', 
            'latitude', 'longitude',
            'business_website', 'dealership_logo', 'cover_image', 
            'dealership_description', 'operating_hours', 
            'facebook_url', 'instagram_url', 'trade_license_number',
            'rating', 'review_count', 'follower_count', 'share_count', 'verification_status'
        ]

class DealerProfileSerializer(serializers.ModelSerializer):
    business_info = PublicBusinessInformationSerializer(read_only=True)
    reviews = serializers.SerializerMethodField()
    review_stats = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    reels = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone_number', 'designation', 'profile_photo', 'business_info', 'reviews', 'review_stats', 'is_following', 'reels', 'share_url']

    def get_reviews(self, obj):
        # Return only the 10 most recent reviews
        reviews = obj.reviews_received.all().order_by('-created_at')[:10]
        return DealerReviewSerializer(reviews, many=True).data

    def get_review_stats(self, obj):
        from django.db.models import Count, Avg
        total_count = obj.reviews_received.count()
        avg_rating = obj.reviews_received.aggregate(Avg('rating'))['rating__avg'] or 0.0

        # Group by rating to get counts for 1-5 stars
        rating_counts = obj.reviews_received.values('rating').annotate(count=Count('id'))
        
        # Initialize breakdown
        breakdown = {i: 0 for i in range(1, 6)}
        for item in rating_counts:
            breakdown[item['rating']] = item['count']

        # Calculate percentages
        percentages = {}
        for star, count in breakdown.items():
            percentage = (count / total_count * 100) if total_count > 0 else 0
            percentages[f"{star}_star"] = {
                "count": count,
                "percentage": round(percentage, 1)
            }

        return {
            "average_rating": round(avg_rating, 1),
            "total_reviews": total_count,
            "breakdown": percentages
        }

    def get_share_url(self, obj):
        return f"https://yourapp.com/dealer/{obj.id}" # Placeholder URL

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from .models import Follow
            return Follow.objects.filter(follower=request.user, dealer=obj).exists()
        return False

    def get_reels(self, obj):
        from vehicles.models import DealerVehicleReel
        from vehicles.serializers import ReelNewsfeedSerializer
        
        # Only show published (not draft) reels
        reels = DealerVehicleReel.objects.filter(dealer=obj, vehicle__is_draft=False).order_by('-created_at')
        return ReelNewsfeedSerializer(reels, many=True, context=self.context).data

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'profile_photo', 'location', 'email', 'phone_number']

class DealerProfileUpdateSerializer(serializers.ModelSerializer):
    dealership_name = serializers.CharField(source='business_info.dealership_name', required=False)
    display_name = serializers.CharField(source='business_info.display_name', required=False)
    specialization = serializers.JSONField(source='business_info.specialization', required=False)
    street_address = serializers.CharField(source='business_info.street_address', required=False)
    state = serializers.CharField(source='business_info.state', required=False)
    division = serializers.CharField(source='business_info.division', required=False)
    business_website = serializers.URLField(source='business_info.business_website', required=False)
    trade_license_number = serializers.CharField(source='business_info.trade_license_number', required=False)
    dealership_description = serializers.CharField(source='business_info.dealership_description', required=False)
    operating_hours = serializers.JSONField(source='business_info.operating_hours', required=False)
    facebook_url = serializers.URLField(source='business_info.facebook_url', required=False)
    instagram_url = serializers.URLField(source='business_info.instagram_url', required=False)
    latitude = serializers.DecimalField(source='business_info.latitude', max_digits=9, decimal_places=6, required=False)
    longitude = serializers.DecimalField(source='business_info.longitude', max_digits=9, decimal_places=6, required=False)

    class Meta:
        model = User
        fields = [
            'full_name', 'phone_number', 'designation', 'profile_photo',
            'dealership_name', 'display_name', 'specialization',
            'street_address', 'state', 'division',
            'business_website', 'trade_license_number', 'dealership_description',
            'operating_hours', 'facebook_url', 'instagram_url',
            'latitude', 'longitude'
        ]

    def update(self, instance, validated_data):
        business_info_data = validated_data.pop('business_info', {})
        
        # Update User fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create BusinessInformation fields
        if business_info_data:
            business_info, created = BusinessInformation.objects.get_or_create(user=instance)
            for attr, value in business_info_data.items():
                setattr(business_info, attr, value)
            business_info.save()
            
        return instance

class UserSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'profile_photo', 'is_buyer', 'is_dealer']

class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

class FollowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'profile_photo']
