from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_vendor = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email or self.username


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses"
    )
    address_name = models.CharField(max_length=250)
    division_id = models.CharField(max_length=50)
    division_name = models.CharField(max_length=100)
    city_id = models.CharField(max_length=50)
    city_name = models.CharField(max_length=100)
    area_id = models.CharField(max_length=50)
    area_name = models.CharField(max_length=100)
    address = models.TextField()
    is_default_shipping = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default_shipping=True),
                name='unique_default_shipping_per_user'
            )
        ]
        ordering = ['-is_default_shipping', '-created_at']

    def __str__(self):
        return f"{self.address_name} - {self.user.email}"
