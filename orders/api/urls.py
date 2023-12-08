from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import UserView


router = DefaultRouter()

urlpatterns = [
    path('signup', UserView.as_view()),
    path('', include(router.urls)),
]
