from django import forms
from django.core.mail import EmailMessage
from django.forms import Form
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

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


class EmailVerificationForm(Form):
    email = forms.EmailField()
    verification_code = forms.CharField(
        min_length=EmailVerificationCode.LENGTH,
        max_length=EmailVerificationCode.LENGTH
    )


class EmailVerification(APIView):
    def post(self, request):
        # Validating request data fields
        errors = EmailVerificationForm(request.data).errors
        if errors:
            raise ValidationError(errors)
        
        req_email = request.data['email']

        # Getting user from DB
        try:
            user = User.objects.get(email=req_email)
        except User.DoesNotExist:
            resp_data = {
                'email': ['User with this email was not found.']
            }
            return Response(resp_data, status.HTTP_404_NOT_FOUND)
        
        # Checking the need for verification
        if user.email_confirmed:
            resp_data = {
                'email': ['This email is already verified.']
            }
            return Response(resp_data, status.HTTP_400_BAD_REQUEST)

        # Getting email verification code from DB
        try:
            user_evc = EmailVerificationCode.objects.get(user=user)
        except EmailVerificationCode.DoesNotExist:
            resp_data = {
                'email': ['Verification code for this email was not found.']
            }
            return Response(resp_data, status.HTTP_404_NOT_FOUND)
        
        # Verification
        req_evc = str(request.data['verification_code'])
        if req_evc != user_evc.value:
            resp_data = {
                'verification_code': ['This code is invalid.']
            }
            return Response(resp_data, status.HTTP_400_BAD_REQUEST)
        user.email_confirmed = True
        user.is_active = True
        user.save()
        user_evc.delete()
        return Response()
