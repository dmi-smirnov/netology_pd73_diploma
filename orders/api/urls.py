from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from api.views import (ProductsViewSet, UpdateShopView, UpdateUserView,
                       ForgotPasswordView, UserCartViewSet,
                       ForgotPasswordConfirmationCodeView,
                       CreateUserView, EmailVerification)


router = DefaultRouter()

router.register('products', ProductsViewSet)
router.register('cart', UserCartViewSet)

urlpatterns = [
    path('signup', CreateUserView.as_view()),
    path('verify_email', EmailVerification.as_view()),
    path('signin', obtain_auth_token),
    path('user', UpdateUserView.as_view()),
    path('forgot_password', ForgotPasswordView.as_view()),
    path('forgot_password/confirmation_code',
         ForgotPasswordConfirmationCodeView.as_view()),
    path('shop/update', UpdateShopView.as_view()),
    path('', include(router.urls)),
]