from rest_framework import generics
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category
from .serializers import CategorySerializer, CategoryDetailSerializer


class CategoryTreeView(generics.ListAPIView):
    queryset = Category.objects.filter(parent=None, is_active=True)
    serializer_class = CategorySerializer


class CategoryDetailView(generics.RetrieveAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategoryDetailSerializer
    lookup_field = "slug"
