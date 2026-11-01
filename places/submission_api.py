"""Account-free, create-only place submissions from the employee form."""
from django.conf import settings
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from .management_api import PlaceSerializer, place_metadata

LINK_SALT = 'places.create-only.v1'


class SubmissionThrottle(AnonRateThrottle):
    scope = 'place-submissions'
    rate = '60/hour'


class SubmissionAccess:
    # This endpoint only creates places; management remains staff-only.
    authentication_classes = []
    permission_classes = [AllowAny]


class SubmissionMetadata(SubmissionAccess, APIView):
    def get(self, request):
        return Response({**place_metadata(), 'auto_publish': settings.PLACES_SUBMISSION_AUTO_PUBLISH})


class SubmitPlace(SubmissionAccess, generics.CreateAPIView):
    serializer_class = PlaceSerializer
    throttle_classes = [SubmissionThrottle]

    def perform_create(self, serializer):
        # Submitters cannot self-verify or change the owner's publication policy.
        serializer.save(is_verified=False, is_visible=settings.PLACES_SUBMISSION_AUTO_PUBLISH)
