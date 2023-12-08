from django.core.mail import EmailMessage
from django.utils import timezone as django_timezone
from rest_framework.generics import CreateAPIView

from api.serializers import UserSerializer
from api.models import EmailVerificationCode, User


class UserView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def perform_create(self, serializer):
        result = super().perform_create(serializer)
        
        created_user = serializer.instance

        # Creating email verification code for created user
        created_user_evc = EmailVerificationCode(
            user=created_user,
            value=EmailVerificationCode.generate()
        )
        created_user_evc.save()

        # Sending email verification code
        email_msg = EmailMessage(
            subject=f'Код подтверждения email',
            body=created_user_evc.value,
            to=(created_user.email,)
        )
        if email_msg.send():
            created_user_evc.sent_at = django_timezone.now()
            created_user_evc.save()

        return result
