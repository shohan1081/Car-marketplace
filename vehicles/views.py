import os
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Case, When, Value, IntegerField, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Music, Vehicle, DealerVehicleReel, Like, SavedReel, ReelView, VehicleInquiry, AIVideoGeneration, Comment
from .serializers import (
    MusicSerializer, VehicleSerializer, ReelNewsfeedSerializer,
    ReelDetailSerializer, VehicleInquirySerializer, AIVideoGenerationSerializer, CommentSerializer
)
from .ai_video import dispatch_video_generation, download_generated_video
from messaging.models import Conversation, Message, Notification
from users.models import BusinessInformation, Follow

class ReelViewCountView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
            reel.view_count += 1
            reel.save()
            
            # Log the view for performance tracking
            viewer_ip = request.META.get('REMOTE_ADDR')
            user = request.user if request.user.is_authenticated else None
            ReelView.objects.create(reel=reel, user=user, viewer_ip=viewer_ip)
            
            return Response({
                "message": "View count incremented.",
                "view_count": reel.view_count
            }, status=status.HTTP_200_OK)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

class DealerDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can access the dashboard."}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        now = timezone.now()
        last_month = now - timedelta(days=30)

        # 1. Inventory Stats
        total_inventory = Vehicle.objects.filter(dealer=user).count()
        active_reels = DealerVehicleReel.objects.filter(dealer=user, vehicle__is_draft=False).count()
        draft_listings = Vehicle.objects.filter(dealer=user, is_draft=True).count()

        # 2. Performance Stats (Views)
        total_views = DealerVehicleReel.objects.filter(dealer=user).aggregate(total=Sum('view_count'))['total'] or 0
        
        # New: Views in last 30 days using our new ReelView model
        last_month_views = ReelView.objects.filter(
            reel__dealer=user, 
            created_at__gte=last_month
        ).count()

        # 3. Engagement Stats
        total_likes = Like.objects.filter(reel__dealer=user).count()
        total_followers = Follow.objects.filter(dealer=user).count()
        total_inquiries = VehicleInquiry.objects.filter(reel__dealer=user).count()
        last_month_leads = VehicleInquiry.objects.filter(
            reel__dealer=user, 
            created_at__gte=last_month
        ).count()

        # 4. Recent Activity (Combined list)
        # Recent Likes
        recent_likes = Like.objects.filter(reel__dealer=user).order_by('-created_at')[:5]
        # Recent Inquiries
        recent_inquiries = VehicleInquiry.objects.filter(reel__dealer=user).order_by('-created_at')[:5]
        
        activities = []
        for like in recent_likes:
            activities.append({
                "type": "like",
                "user_name": like.user.full_name or like.user.email,
                "reel_id": like.reel.id,
                "vehicle_name": like.reel.vehicle.name,
                "created_at": like.created_at
            })
        
        for inquiry in recent_inquiries:
            activities.append({
                "type": "inquiry",
                "user_name": inquiry.full_name,
                "reel_id": inquiry.reel.id,
                "vehicle_name": inquiry.reel.vehicle.name,
                "created_at": inquiry.created_at
            })

        # Sort combined activities by date
        activities.sort(key=lambda x: x['created_at'], reverse=True)

        dashboard_data = {
            "inventory": {
                "total_vehicles": total_inventory,
                "active_reels": active_reels,
                "draft_listings": draft_listings,
            },
            "performance": {
                "total_views": total_views,
                "last_month_views": last_month_views,
                "total_likes": total_likes,
                "total_followers": total_followers,
                "leads_received": total_inquiries,
                "last_month_leads": last_month_leads
            },
            "recent_activity": activities[:10]
        }

        return Response(dashboard_data)

class DealerInventoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can access their inventory."}, status=status.HTTP_403_FORBIDDEN)
        
        # Get all reels belonging to this dealer
        reels = DealerVehicleReel.objects.filter(dealer=request.user).order_by('-created_at')

        # Filter by AI vs Manual
        is_ai = request.query_params.get('is_ai_generated')
        if is_ai is not None:
            if is_ai.lower() in ('true', '1', 'yes'):
                reels = reels.filter(is_ai_generated=True)
            elif is_ai.lower() in ('false', '0', 'no'):
                reels = reels.filter(is_ai_generated=False)

        type_param = request.query_params.get('type')
        if type_param:
            if type_param.lower() == 'ai':
                reels = reels.filter(is_ai_generated=True)
            elif type_param.lower() == 'manual':
                reels = reels.filter(is_ai_generated=False)
        
        # A single list with 'is_draft' and 'is_ai_generated' property is most flexible for Flutter.
        serializer = ReelNewsfeedSerializer(reels, many=True, context={'request': request})
        
        # Add is_draft status to the response for each reel
        data = serializer.data
        for i, reel_obj in enumerate(reels):
            data[i]['is_draft'] = reel_obj.vehicle.is_draft
            data[i]['vehicle_id'] = reel_obj.vehicle.id # Useful for editing

        return Response(data)

class NewsfeedView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        user = request.user
        
        # Only show reels from verified dealers and non-draft vehicles
        queryset = DealerVehicleReel.objects.filter(
            vehicle__is_draft=False,
            dealer__business_info__verification_status='verified'
        ).distinct()

        if user.is_authenticated:
            try:
                prefs = user.preferences
                
                # Initialize score components
                # 1. Body Type Match (Weight: 3)
                body_type_q = Q(vehicle__body_type__in=prefs.vehicle_types) if prefs.vehicle_types else Q(pk__isnull=True)
                
                # 2. Fuel Preference Match (Weight: 2)
                fuel_q = Q(vehicle__fuel_type__in=prefs.fuel_prefs) if prefs.fuel_prefs else Q(pk__isnull=True)
                
                # 3. City Match (Weight: 1)
                city_q = Q(vehicle__location__icontains=prefs.city) if prefs.city else Q(pk__isnull=True)

                queryset = queryset.annotate(
                    match_score=(
                        Case(When(body_type_q, then=Value(3)), default=Value(0), output_field=IntegerField()) +
                        Case(When(fuel_q, then=Value(2)), default=Value(0), output_field=IntegerField()) +
                        Case(When(city_q, then=Value(1)), default=Value(0), output_field=IntegerField())
                    )
                ).order_by('-match_score', '-created_at')
            except:
                # If no preferences found or other error, fallback to normal sorting
                queryset = queryset.order_by('-created_at')
        else:
            queryset = queryset.order_by('-created_at')

        serializer = ReelNewsfeedSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

class VehicleSearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        
        # Base queryset: only verified dealers and non-draft vehicles
        queryset = DealerVehicleReel.objects.filter(
            vehicle__is_draft=False,
            dealer__business_info__verification_status='verified'
        )

        if query:
            # Search by vehicle name, dealer name, or location
            queryset = queryset.filter(
                Q(vehicle__name__icontains=query) |
                Q(vehicle__model__icontains=query) |
                Q(dealer__business_info__display_name__icontains=query) |
                Q(dealer__business_info__dealership_name__icontains=query) |
                Q(vehicle__location__icontains=query)
            )

        # Filters (Optional)
        brand = request.query_params.get('brand')
        if brand:
            queryset = queryset.filter(vehicle__name__icontains=brand)

        body_type = request.query_params.get('body_type')
        if body_type:
            queryset = queryset.filter(vehicle__body_type__iexact=body_type)

        transmission = request.query_params.get('transmission')
        if transmission:
            queryset = queryset.filter(vehicle__transmission__iexact=transmission)

        min_price = request.query_params.get('min_price')
        if min_price and min_price.isdigit():
            queryset = queryset.filter(vehicle__asking_price__gte=int(min_price))

        max_price = request.query_params.get('max_price')
        if max_price and max_price.isdigit():
            queryset = queryset.filter(vehicle__asking_price__lte=int(max_price))

        specialization = request.query_params.get('specialization')
        if specialization:
            # Since specialization is a JSONField (list), we can check if it contains the spec
            queryset = queryset.filter(dealer__business_info__specialization__contains=specialization)

        queryset = queryset.distinct().order_by('-created_at')
        
        serializer = ReelNewsfeedSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

class ReelDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
            serializer = ReelDetailSerializer(reel, context={'request': request})
            return Response(serializer.data)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

class LikeReelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
            like, created = Like.objects.get_or_create(user=request.user, reel=reel)
            if not created:
                like.delete()
                return Response({"message": "Unliked successfully."}, status=status.HTTP_200_OK)
            return Response({"message": "Liked successfully."}, status=status.HTTP_201_CREATED)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

class SaveReelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
            save, created = SavedReel.objects.get_or_create(user=request.user, reel=reel)
            if not created:
                save.delete()
                return Response({"saved": False, "message": "Removed from saved successfully."}, status=status.HTTP_200_OK)
            return Response({"saved": True, "message": "Saved successfully."}, status=status.HTTP_201_CREATED)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

class SavedReelsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .serializers import SavedReelListSerializer
        saved_reels = SavedReel.objects.filter(user=request.user).order_by('-created_at')
        serializer = SavedReelListSerializer(saved_reels, many=True, context={'request': request})
        return Response(serializer.data)

class ShareReelView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
            reel.share_count += 1
            reel.save()
            return Response({
                "message": "Share count incremented.",
                "share_count": reel.share_count
            }, status=status.HTTP_200_OK)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

class MusicListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        musics = Music.objects.all()
        serializer = MusicSerializer(musics, many=True, context={'request': request})
        return Response(serializer.data)

class VehicleCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can post vehicle listings."}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if dealer is verified
        try:
            if request.user.business_info.verification_status != 'verified':
                return Response({
                    "error": "Your account is not verified. Please complete your business information and wait for admin approval before posting reels."
                }, status=status.HTTP_403_FORBIDDEN)
        except BusinessInformation.DoesNotExist:
            return Response({
                "error": "Please complete your business information first."
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check for active subscription (Temporarily bypassed for seamless testing)
        # if not hasattr(request.user, 'subscription') or not request.user.subscription.is_valid:
        #     return Response({
        #         "error": "You need an active subscription to post vehicle listings. Please purchase a plan."
        #     }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = VehicleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            is_draft_val = request.data.get('is_draft')
            if is_draft_val is not None:
                is_draft = str(is_draft_val).lower() in ['true', '1', 'yes']
            else:
                is_draft = request.query_params.get('draft', 'false').lower() == 'true'
            vehicle = serializer.save(dealer=request.user, is_draft=is_draft)
            return Response(VehicleSerializer(vehicle, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VehiclePreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Temporary preview that doesn't save to DB.
        """
        serializer = VehicleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Return validated data as a preview
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VehicleDraftPublishView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        # Check if dealer is verified
        try:
            if request.user.business_info.verification_status != 'verified':
                return Response({
                    "error": "Your account is not verified. Please complete your business information and wait for admin approval before publishing."
                }, status=status.HTTP_403_FORBIDDEN)
        except BusinessInformation.DoesNotExist:
            return Response({
                "error": "Please complete your business information first."
            }, status=status.HTTP_403_FORBIDDEN)

        # Check for active subscription
        if not hasattr(request.user, 'subscription') or not request.user.subscription.is_valid:
            return Response({
                "error": "You need an active subscription to publish vehicle listings. Please purchase a plan."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            vehicle = Vehicle.objects.get(pk=pk, dealer=request.user)
            vehicle.is_draft = False
            vehicle.save()
            return Response({"message": "Vehicle listing published successfully."}, status=status.HTTP_200_OK)
        except Vehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

class VehicleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            vehicle = Vehicle.objects.get(pk=pk, dealer=request.user)
            serializer = VehicleSerializer(vehicle, context={'request': request})
            return Response(serializer.data)
        except Vehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            vehicle = Vehicle.objects.get(pk=pk, dealer=request.user)
            serializer = VehicleSerializer(vehicle, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Vehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            vehicle = Vehicle.objects.get(pk=pk, dealer=request.user)
            vehicle.delete()
            return Response({"message": "Vehicle deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Vehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

class BuyerInquiryListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        inquiries = VehicleInquiry.objects.filter(buyer=request.user).order_by('-created_at')
        serializer = VehicleInquirySerializer(inquiries, many=True, context={'request': request})
        return Response(serializer.data)

class VehicleInquiryCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
            serializer = VehicleInquirySerializer(data=request.data, context={'reel': reel, 'request': request})
            if serializer.is_valid():
                inquiry = serializer.save(buyer=request.user, reel=reel)
                
                # Auto-create or get conversation
                conversation = Conversation.objects.filter(
                    reel=reel,
                    participants=request.user
                ).filter(participants=reel.dealer).first()
                
                if not conversation:
                    conversation = Conversation.objects.create(reel=reel)
                    conversation.participants.add(request.user, reel.dealer)
                
                # Format professional inquiry message
                price_info = f"Offered Price: {inquiry.offered_price}" if inquiry.offered_price else "Price: Fixed"
                message_text = (
                    f"Hi, I'm interested in this {reel.vehicle.name}.\n\n"
                    f"Inquiry Details:\n"
                    f"- {price_info}\n"
                    f"- Down Payment: {inquiry.down_payment}\n"
                    f"- Loan Tenure: {inquiry.get_loan_tenure_display()}\n"
                    f"- Credit Estimate: {inquiry.get_credit_estimate_display()}\n"
                    f"- Notes: {inquiry.additional_notes or 'None'}"
                )
                
                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    text=message_text
                )
                
                return Response({
                    "message": "Inquiry submitted and dealer notified.",
                    "conversation_id": conversation.id
                }, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

class DealerInquiryListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can access inquiries."}, status=status.HTTP_403_FORBIDDEN)
        
        inquiries = VehicleInquiry.objects.filter(reel__dealer=request.user).order_by('-created_at')
        serializer = VehicleInquirySerializer(inquiries, many=True, context={'request': request})
        return Response(serializer.data)

class DealerInquiryDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can access inquiry details."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            inquiry = VehicleInquiry.objects.get(pk=pk, reel__dealer=request.user)
            serializer = VehicleInquirySerializer(inquiry, context={'request': request})
            return Response(serializer.data)
        except VehicleInquiry.DoesNotExist:
            return Response({"error": "Inquiry not found."}, status=status.HTTP_404_NOT_FOUND)

class DealerInquiryActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, action):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can perform this action."}, status=status.HTTP_403_FORBIDDEN)
        
        if action not in ['accept', 'reject']:
            return Response({"error": "Invalid action. Use 'accept' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            inquiry = VehicleInquiry.objects.get(pk=pk, reel__dealer=request.user)
            inquiry.status = 'accepted' if action == 'accept' else 'rejected'
            inquiry.save()

            # Find the conversation to send a notification message
            conversation = Conversation.objects.filter(
                reel=inquiry.reel,
                participants=inquiry.buyer
            ).filter(participants=request.user).first()

            if conversation:
                status_text = "accepted" if action == "accept" else "declined"
                notif_message = f"Hello {inquiry.full_name}, I have {status_text} your inquiry for the {inquiry.reel.vehicle.name}. Let's discuss the next steps."
                if action == 'reject':
                    notif_message = f"Hello {inquiry.full_name}, I have reviewed your inquiry for the {inquiry.reel.vehicle.name} but I am unable to proceed at this time. Thank you for your interest."
                
                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    text=notif_message
                )
            
            return Response({
                "message": f"Inquiry {action}ed successfully and buyer notified.",
                "status": inquiry.status
            })
        except VehicleInquiry.DoesNotExist:
            return Response({"error": "Inquiry not found."}, status=status.HTTP_404_NOT_FOUND)

ALLOWED_AI_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.avif'}

class AIVideoGenerationView(APIView):
    """
    Accepts 5-7 reference images (+ optional prompt/duration/resolution) from
    a dealer and hands the job off to the external car-video-agent service.
    That service generates the video asynchronously and calls our webhook
    (AIVideoWebhookView) when it's done.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can generate AI videos."}, status=status.HTTP_403_FORBIDDEN)

        try:
            if request.user.business_info.verification_status != 'verified':
                return Response({
                    "error": "Your account is not verified. Please complete your business information and wait for admin approval before generating AI videos."
                }, status=status.HTTP_403_FORBIDDEN)
        except BusinessInformation.DoesNotExist:
            return Response({
                "error": "Please complete your business information first."
            }, status=status.HTTP_403_FORBIDDEN)

        if not hasattr(request.user, 'subscription') or not request.user.subscription.is_valid:
            return Response({
                "error": "You need an active subscription to generate AI videos. Please purchase a plan."
            }, status=status.HTTP_403_FORBIDDEN)

        images = request.FILES.getlist('images')
        if len(images) < 1 or len(images) > 7:
            return Response({"error": "Provide between 1 and 7 images."}, status=status.HTTP_400_BAD_REQUEST)

        for img in images:
            ext = os.path.splitext(img.name)[1].lower()
            if ext not in ALLOWED_AI_IMAGE_EXTENSIONS:
                return Response({
                    "error": f"Unsupported file format: {ext}. Allowed: PNG, JPG, JPEG, WEBP, AVIF"
                }, status=status.HTTP_400_BAD_REQUEST)

        generation = AIVideoGeneration.objects.create(
            dealer=request.user,
            prompt=request.data.get('prompt', ''),
            duration=request.data.get('duration', '10'),
            resolution=request.data.get('resolution', '720p'),
        )

        if not dispatch_video_generation(generation, images):
            return Response({
                "error": "Could not reach the AI video generation service. Please try again shortly.",
                "job_id": generation.job_id
            }, status=status.HTTP_502_BAD_GATEWAY)

        return Response(AIVideoGenerationSerializer(generation, context={'request': request}).data, status=status.HTTP_201_CREATED)

class AIVideoStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        try:
            generation = AIVideoGeneration.objects.get(job_id=job_id, dealer=request.user)
        except (AIVideoGeneration.DoesNotExist, DjangoValidationError, ValueError):
            return Response({"error": "AI generation request not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AIVideoGenerationSerializer(generation, context={'request': request}).data)

class AIVideoListView(APIView):
    """
    List all AI video generations for the authenticated dealer.
    Supports filtering:
      - ?unused=true (only returns completed videos that haven't been turned into a vehicle reel yet)
      - ?unused=false (only returns videos that have already been converted to a reel)
      - ?status=completed|pending|failed
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can access AI video generations."}, status=status.HTTP_403_FORBIDDEN)

        queryset = AIVideoGeneration.objects.filter(dealer=request.user)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param.lower())

        unused_param = request.query_params.get('unused')
        if unused_param is not None:
            if unused_param.lower() in ('true', '1', 'yes'):
                queryset = queryset.filter(status='completed', reels__isnull=True)
            elif unused_param.lower() in ('false', '0', 'no'):
                queryset = queryset.filter(reels__isnull=False)

        queryset = queryset.prefetch_related('reels', 'reels__vehicle').order_by('-created_at')
        serializer = AIVideoGenerationSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

class AIVideoWebhookView(APIView):
    """
    Receives the result push from the external car-video-agent service.
    Protected by a shared secret token (query param) instead of JWT, since
    the caller is a backend service, not a logged-in user.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        expected_token = getattr(settings, 'AI_VIDEO_WEBHOOK_TOKEN', '')
        if not expected_token or request.query_params.get('token') != expected_token:
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        job_id = request.data.get('job_id')
        result_status = request.data.get('status')
        video_url = request.data.get('video_url')
        error = request.data.get('error')

        try:
            generation = AIVideoGeneration.objects.get(job_id=job_id)
        except (AIVideoGeneration.DoesNotExist, DjangoValidationError, ValueError):
            # Acknowledge anyway so the caller doesn't keep retrying a job we don't know about.
            return Response({"status": "generation not found"}, status=status.HTTP_200_OK)

        if result_status == 'completed' and video_url:
            if download_generated_video(generation, video_url):
                generation.status = 'completed'
            else:
                generation.status = 'failed'
        else:
            generation.status = 'failed'
            generation.error_message = error or "AI video generation failed."

        generation.save()
        return Response({"status": "received"}, status=status.HTTP_200_OK)

class ReelCommentListView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)
        
        comments = reel.comments.all()
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
            
        try:
            reel = DealerVehicleReel.objects.get(pk=pk)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)
            
        text = request.data.get('text')
        if not text:
            return Response({"error": "Comment text is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        comment = Comment.objects.create(user=request.user, reel=reel, text=text)
        
        # Create notification for dealer
        if reel.dealer != request.user:
            Notification.objects.create(
                user=reel.dealer,
                title="New Comment on Your Reel",
                body=f"{request.user.full_name or request.user.email} commented on your {reel.vehicle.name} reel.",
                notification_type="comment",
                reference_id=str(reel.id),
                extra_data={"comment_id": comment.id}
            )
            
        serializer = CommentSerializer(comment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ReelCommentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request, comment_id):
        try:
            comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            return Response({"error": "Comment not found."}, status=status.HTTP_404_NOT_FOUND)
            
        if comment.user != request.user:
            return Response({"error": "You do not have permission to delete this comment."}, status=status.HTTP_403_FORBIDDEN)
            
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
