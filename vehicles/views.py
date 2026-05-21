from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Case, When, Value, IntegerField, Q
from .models import Music, Vehicle, DealerVehicleReel, Like, SavedReel
from .serializers import (
    MusicSerializer, VehicleSerializer, ReelNewsfeedSerializer, 
    ReelDetailSerializer, VehicleInquirySerializer
)
from messaging.models import Conversation, Message

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
                fuel_q = Q(vehicle__fuel_type=prefs.fuel_preference) if prefs.fuel_preference else Q(pk__isnull=True)
                
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
                return Response({"message": "Removed from saved successfully."}, status=status.HTTP_200_OK)
            return Response({"message": "Saved successfully."}, status=status.HTTP_201_CREATED)
        except DealerVehicleReel.DoesNotExist:
            return Response({"error": "Reel not found."}, status=status.HTTP_404_NOT_FOUND)

class SavedReelsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        saved_reels = SavedReel.objects.filter(user=request.user).order_by('-created_at')
        # Extract the reel objects from the SavedReel relationships
        reels = [item.reel for item in saved_reels]
        serializer = ReelNewsfeedSerializer(reels, many=True, context={'request': request})
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
        serializer = MusicSerializer(musics, many=True)
        return Response(serializer.data)

class VehicleCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_dealer:
            return Response({"error": "Only dealers can post vehicle listings."}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = VehicleSerializer(data=request.data)
        if serializer.is_valid():
            is_draft = request.query_params.get('draft', 'false').lower() == 'true'
            vehicle = serializer.save(dealer=request.user, is_draft=is_draft)
            return Response(VehicleSerializer(vehicle).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VehiclePreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Temporary preview that doesn't save to DB.
        """
        serializer = VehicleSerializer(data=request.data)
        if serializer.is_valid():
            # Return validated data as a preview
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VehicleDraftPublishView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            vehicle = Vehicle.objects.get(pk=pk, dealer=request.user)
            vehicle.is_draft = False
            vehicle.save()
            return Response({"message": "Vehicle listing published successfully."}, status=status.HTTP_200_OK)
        except Vehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

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
