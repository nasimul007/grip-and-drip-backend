from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import NewsletterSubscriber
from .serializers import (
    ContactMessageSerializer,
    NewsletterSubscribeSerializer,
    NewsletterUnsubscribeSerializer,
)


class ContactCreateView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ContactMessageSerializer


class NewsletterSubscribeView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = NewsletterSubscribeSerializer

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

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sub = NewsletterSubscriber.objects.get(
            email=serializer.validated_data["email"]
        )
        sub.is_active = False
        sub.save()
        return Response(
            {"message": "Successfully unsubscribed."},
            status=status.HTTP_200_OK,
        )
