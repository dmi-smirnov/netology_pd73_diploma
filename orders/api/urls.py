from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from api.views import (ProductsViewSet, UpdateShopPositionsView,
                       UpdateUserView, ForgotPasswordView, UserCartViewSet,
                       ForgotPasswordConfirmationCodeView, UserShopsViewSet,
                       CreateUserView, EmailVerification, UserOrdersViewSet,
                       UserRecipientsViewSet, UserShopsOrdersViewSet)


router = DefaultRouter()

router.register('products', ProductsViewSet)
router.register('user/cart', UserCartViewSet)
router.register('user/recipients', UserRecipientsViewSet)
router.register('user/orders', UserOrdersViewSet)
router.register('user/shops/orders', UserShopsOrdersViewSet)
router.register('user/shops', UserShopsViewSet)


urlpatterns = [
    path('signup', CreateUserView.as_view()),
    path('verify_email', EmailVerification.as_view()),
    path('signin', obtain_auth_token),
    path('user', UpdateUserView.as_view()),
    path('forgot_password', ForgotPasswordView.as_view()),
    path('forgot_password/confirmation_code',
         ForgotPasswordConfirmationCodeView.as_view()),
    path('user/shops/update_positions', UpdateShopPositionsView.as_view()),
    path('', include(router.urls)),
]