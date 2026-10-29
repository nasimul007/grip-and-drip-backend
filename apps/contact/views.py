from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from .models import NewsletterSubscriber
from .serializers import (
    ContactMessageSerializer,
    NewsletterSubscribeSerializer,
    NewsletterUnsubscribeSerializer,
)


class ContactCreateView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ContactMessageSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "contact"


class NewsletterSubscribeView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = NewsletterSubscribeSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "newsletter"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        NewsletterSubscriber.objects.get_or_create(
            email=serializer.validated_data["email"],
            defaults={"is_active": True},
        )
        return Response(
            {"message": "Successfully subscribed."},
            status=status.HTTP_201_CREATED,
        )


class NewsletterUnsubscribeView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = NewsletterUnsubscribeSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "newsletter"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Same answer whether or not the address was subscribed.
        NewsletterSubscriber.objects.filter(
            email__iexact=serializer.validated_data["email"]
        ).update(is_active=False)
        return Response(
            {"message": "Successfully unsubscribed."},
            status=status.HTTP_200_OK,
        )
