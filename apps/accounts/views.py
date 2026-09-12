from rest_framework import generics, status, serializers, viewsets
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser, Address
from .serializers import (
    RegisterSerializer, UserSerializer, PasswordChangeSerializer,
    AddressSerializer, AddressListSerializer, SetDefaultShippingSerializer
)


class RegisterView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            raise serializers.ValidationError({"old_password": ["Old Password: Wrong password."]})
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


class AddressViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return AddressListSerializer
        return AddressSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_default_shipping:
            return Response(
                {"detail": "Cannot delete the default shipping address. Set another address as default first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], serializer_class=SetDefaultShippingSerializer)
    def set_default_shipping(self, request, pk=None):
        address = self.get_object()
        Address.objects.filter(user=request.user, is_default_shipping=True).update(is_default_shipping=False)
        address.is_default_shipping = True
        address.save(update_fields=["is_default_shipping"])
        return Response({"detail": "Default shipping address updated."}, status=status.HTTP_200_OK)
