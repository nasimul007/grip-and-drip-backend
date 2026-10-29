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
