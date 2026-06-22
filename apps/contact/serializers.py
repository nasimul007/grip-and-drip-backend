from rest_framework import serializers
from .models import ContactMessage, NewsletterSubscriber


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message")


class NewsletterSubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        sub, created = NewsletterSubscriber.objects.get_or_create(
            email=value, defaults={"is_active": True}
        )
        if not created and sub.is_active:
            raise serializers.ValidationError("This email is already subscribed.")
        return value


class NewsletterUnsubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            sub = NewsletterSubscriber.objects.get(email=value)
            if not sub.is_active:
                raise serializers.ValidationError("This email is not subscribed.")
        except NewsletterSubscriber.DoesNotExist:
            raise serializers.ValidationError("This email is not subscribed.")
        return value
