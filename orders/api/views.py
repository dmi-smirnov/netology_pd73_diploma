from django import forms
from django.core.mail import EmailMessage
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import UserSerializer
from api.models import ConfirmationCode, User


class CreateUserView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def perform_create(self, serializer):
        result = super().perform_create(serializer)
        
        created_user = serializer.instance

        send_confirmation_code_by_email(
            user=created_user,
            email_subject='Код подтверждения email'
        )

        return result


class EmailVerificationForm(forms.Form):
    email = forms.EmailField()
    confirmation_code = forms.CharField(
        min_length=ConfirmationCode.LENGTH,
        max_length=ConfirmationCode.LENGTH
    )


class EmailVerification(APIView):
    def post(self, request):
        # Validating request data fields
        errors = EmailVerificationForm(request.data).errors
        if errors:
            raise ValidationError(errors)
        
        req_email = request.data['email']

        # Getting user from DB by email
        try:
            user = User.objects.get(email=req_email)
        except User.DoesNotExist:
            resp_data = {
                'email': ['User with this email was not found.']
            }
            return Response(resp_data, status.HTTP_404_NOT_FOUND)
        
        # Checking the need for verification
        if user.email_confirmed:
            errors = {
                'email': ['This email is already verified.']
            }
            raise ValidationError(errors)

        # Getting confirmation code from DB
        try:
            db_confirmation_code = ConfirmationCode.objects.get(user=user)
        except ConfirmationCode.DoesNotExist:
            errors = {
                'error': ['Confirmation code for this user was not found.']
            }
            raise ValidationError(errors, status.HTTP_404_NOT_FOUND)
        
        # Confirmation code verification
        req_confirmation_code = str(request.data['confirmation_code'])
        if req_confirmation_code != db_confirmation_code.value:
            errors = {
                'confirmation_code': ['This code is invalid.']
            }
            raise ValidationError(errors)
        user.email_confirmed = True
        user.is_active = True
        user.save()
        db_confirmation_code.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateUserView(UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    
class OnlyEmailForm(forms.Form):
    email = forms.EmailField()


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField()
    confirmation_code = forms.CharField(
        min_length=ConfirmationCode.LENGTH,
        max_length=ConfirmationCode.LENGTH
    )
    password = forms.CharField()


class ForgotPasswordConfirmationCodeView(APIView):
    def post(self, request):
        'Requesting password change confirmation code to email'
        # Validating request data fields
        errors = OnlyEmailForm(request.data).errors
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
        
        send_confirmation_code_by_email(
            user=user,
            email_subject='Код подтверждения смены пароля'
        )

        resp_data = {
            'result': f'Password change confirmation code sent to {req_email}.'
        }
        return Response(resp_data)


class ForgotPasswordView(APIView):
    def patch(self, request):
        'Password change with using confirmation code'
        # Validating request data fields
        errors = ForgotPasswordForm(request.data).errors
        if errors:
            raise ValidationError(errors)
        
        req_data = request.data
        req_email = req_data['email']

        # Getting user from DB by email
        try:
            user = User.objects.get(email=req_email)
        except User.DoesNotExist:
            errors = {
                'email': ['User with this email was not found.']
            }
            raise ValidationError(errors, status.HTTP_404_NOT_FOUND)
        
        # Getting confirmation code from DB
        try:
            db_confirmation_code =\
                ConfirmationCode.objects.get(user=user)
        except ConfirmationCode.DoesNotExist:
            errors = {
                'error': ['Confirmation code for this user was not found.']
            }
            raise ValidationError(errors, status.HTTP_404_NOT_FOUND)
        
        # Confirmation code verification
        req_confirmation_code = str(req_data['confirmation_code'])
        if req_confirmation_code != db_confirmation_code.value:
            errors = {
                'confirmation_code': ['This code is invalid.']
            }
            raise ValidationError(errors)

        # Password change
        serializer_data = {
            'password': req_data['password']
        }
        user_serializer =\
            UserSerializer(user, data=serializer_data, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user_serializer.save()

        db_confirmation_code.delete()

        resp_data = {
            'result': ['Password changed.']
        }
        return Response(resp_data)
        


def create_confirmation_code(user) -> ConfirmationCode:
    try:
        user.confirmation_code.delete()
    except User.confirmation_code.RelatedObjectDoesNotExist:
        pass
    
    confirmation_code = ConfirmationCode(
        user=user,
        value=ConfirmationCode.generate()
    )
    confirmation_code.save()

    return confirmation_code

def send_confirmation_code_by_email(user, email_subject: str):
    confirmation_code = create_confirmation_code(user)
    
    email_msg = EmailMessage(
        subject=email_subject,
        body=confirmation_code.value,
        to=(user.email,)
    )
    if email_msg.send():
        confirmation_code.sent_at = django_timezone.now()
        confirmation_code.save()
