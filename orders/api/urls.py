from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import UserView, EmailVerification


router = DefaultRouter()

urlpatterns = [
    path('signup', UserView.as_view()),
    path('verify_email', EmailVerification.as_view()),
    path('', include(router.urls)),
]
