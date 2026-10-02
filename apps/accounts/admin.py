from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Address


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "phone_number", "is_vendor", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("phone_number", "is_vendor")}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    model = Address
    list_display = ("user", "address_name")
    
