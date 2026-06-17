from django.urls import path
from . import views

urlpatterns = [
    path("", views.CategoryTreeView.as_view(), name="category-tree"),
    path("<slug:slug>/", views.CategoryDetailView.as_view(), name="category-detail"),
]
