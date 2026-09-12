from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from .models import CustomUser, Address


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ("email", "full_name", "password", "password2", "phone_number")

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    @staticmethod
    def _make_unique_username(base):
        username = base
        i = 1
        while CustomUser.objects.filter(username=username).exists():
            i += 1
            username = f"{base}{i}"
        return username

    def create(self, validated_data):
        email = validated_data["email"]
        username = self._make_unique_username(email.split("@")[0])
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
            phone_number=validated_data.get("phone_number", ""),
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("id", "username", "full_name", "email", "phone_number", "is_vendor")
        read_only_fields = ("id",)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    confirm_new_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        if attrs["new_password"] == attrs["old_password"]:
            raise serializers.ValidationError({"new_password": "New password must be different from the old password."})
        return attrs


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id", "address_name", "division_id", "division_name",
            "city_id", "city_name", "area_id", "area_name",
            "address", "is_default_shipping", "created_at", "updated_at"
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        is_default = attrs.get("is_default_shipping", False)
        if is_default and self.instance and self.instance.is_default_shipping:
            return attrs
        if is_default:
            user = self.context["request"].user
            if Address.objects.filter(user=user, is_default_shipping=True).exists():
                raise serializers.ValidationError(
                    "A default shipping address already exists. Unset it first or edit the existing default."
                )
        return attrs


class AddressListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id", "address_name", "division_name", "city_name",
            "area_name", "address", "is_default_shipping", "created_at"
        )


class SetDefaultShippingSerializer(serializers.Serializer):
    pass
