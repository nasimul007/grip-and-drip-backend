from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register(r"addresses", views.AddressViewSet, basename="address")

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("profile/", views.UserProfileView.as_view(), name="auth-profile"),
    path("password/change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("", include(router.urls)),
]
