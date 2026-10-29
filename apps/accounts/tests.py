from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()

ADDRESS = {
    "address_name": "Home", "recipient_name": "Rahim Uddin", "phone": "01712345678",
    "division_id": "3", "division_name": "Dhaka", "city_id": "1", "city_name": "Dhaka",
    "area_id": "9", "area_name": "Dhanmondi", "address": "House 1, Road 2",
}


class AddressApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a", email="a@example.com", password="pass12345")
        self.client.force_authenticate(self.user)

    def test_saved_address_keeps_recipient_and_phone(self):
        res = self.client.post("/api/auth/addresses/", ADDRESS, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        listing = self.client.get("/api/auth/addresses/").data
        rows = listing["results"] if isinstance(listing, dict) else listing
        self.assertEqual((rows[0]["recipient_name"], rows[0]["phone"]), ("Rahim Uddin", "01712345678"))

    def test_older_addresses_without_the_new_fields_still_save(self):
        body = {k: v for k, v in ADDRESS.items() if k not in ("recipient_name", "phone")}
        self.assertEqual(self.client.post("/api/auth/addresses/", body, format="json").status_code, 201)


class AccountSecurityTests(APITestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user(username="b", email="b@example.com", password="Strong-pass-77")

    def login(self, password):
        return self.client.post("/api/auth/login/", {"email": "b@example.com", "password": password}, format="json")

    def test_profile_cannot_grant_vendor_or_rename_username(self):
        self.client.force_authenticate(self.user)
        self.client.patch("/api/auth/profile/", {"is_vendor": True, "username": "admin"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual((self.user.is_vendor, self.user.username), (False, "b"))

    def test_changing_email_needs_current_password(self):
        self.client.force_authenticate(self.user)
        res = self.client.patch("/api/auth/profile/", {"email": "new@example.com"}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(
            "/api/auth/profile/",
            {"email": "new@example.com", "current_password": "Strong-pass-77"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)

    def test_weak_passwords_are_rejected(self):
        body = {"email": "c@example.com", "password": "12345678", "password2": "12345678"}
        self.assertEqual(self.client.post("/api/auth/register/", body, format="json").status_code, 400)

    def test_repeated_failed_logins_lock_the_account(self):
        for _ in range(5):
            self.assertEqual(self.login("wrong").status_code, 401)
        self.assertNotEqual(self.login("Strong-pass-77").status_code, 200)

    def test_logout_and_rotation_retire_refresh_tokens(self):
        refresh = self.login("Strong-pass-77").data["refresh"]
        rotated = self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(rotated.status_code, 200)
        self.assertEqual(
            self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json").status_code, 401
        )
        self.client.post("/api/auth/logout/", {"refresh": rotated.data["refresh"]}, format="json")
        self.assertEqual(
            self.client.post("/api/auth/token/refresh/", {"refresh": rotated.data["refresh"]}, format="json").status_code,
            401,
        )

    def test_password_change_signs_out_other_devices(self):
        other_device = self.login("Strong-pass-77").data["refresh"]
        self.client.force_authenticate(self.user)
        res = self.client.post(
            "/api/auth/password/change/",
            {"old_password": "Strong-pass-77", "new_password": "Another-pass-88", "confirm_new_password": "Another-pass-88"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.post("/api/auth/token/refresh/", {"refresh": other_device}, format="json").status_code, 401
        )
