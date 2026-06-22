from django.urls import path
from . import views

urlpatterns = [
    path("contact/", views.ContactCreateView.as_view(), name="contact-create"),
    path("newsletter/subscribe/", views.NewsletterSubscribeView.as_view(), name="newsletter-subscribe"),
    path("newsletter/unsubscribe/", views.NewsletterUnsubscribeView.as_view(), name="newsletter-unsubscribe"),
]
