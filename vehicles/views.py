from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Music, Vehicle, DealerVehicleReel, Like, SavedReel
from .serializers import (
    MusicSerializer, VehicleSerializer, ReelNewsfeedSerializer, 
    ReelDetailSerializer
)

class NewsfeedView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        reels = DealerVehicleReel.objects.all().order_by('-created_at')
        serializer = ReelNewsfeedSerializer(reels, many=True, context={'request': request})
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
